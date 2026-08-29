#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is made
 * available to you under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version. For more
 * information, see COPYING.
 */
#endregion

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using OpenRA.FileFormats;
using OpenRA.Network;

namespace OpenRA.Test
{
	[TestFixture]
	[Category("Subprocess")]
	[Parallelizable(ParallelScope.None)]
	sealed class ReplayVerificationSubprocessTest : AutomatedMatchSubprocessTestBase
	{
		[TestCase(TestName = "Launch.VerifyReplay classifies verified, desynced, incomplete, and missing replays")]
		public void ReplayVerificationProducesDeterministicEvidence()
		{
			var matchSupport = CreateSupportDir("match");
			SeedContentIntoSupportDir(matchSupport);
			var specification = WriteShortSpec(maxWorldTicks: 600);

			var matchExitCode = RunOpenRaExe(matchSupport, specification, wallClockTimeoutSeconds: 120);
			var generatedResult = Path.Combine(matchSupport, "match-result.json");
			Assert.That(matchExitCode, Is.EqualTo(4), $"Match failed. Artifacts: {tempRoot}");
			Assert.That(ReadStatus(generatedResult), Is.EqualTo("TIMED_OUT"));

			var replay = ReadReplayPath(generatedResult);
			Assert.That(File.Exists(replay), Is.True, $"Generated replay is missing: {replay}");

			var verifiedSupport = CreateSupportDir("verified");
			SeedContentIntoSupportDir(verifiedSupport);
			var verifiedExitCode = RunReplayVerification(verifiedSupport, replay, wallClockTimeoutSeconds: 120);
			var verifiedResult = Path.Combine(verifiedSupport, "replay-verification-result.json");
			AssertVerificationResult(verifiedResult, verifiedExitCode, 0, "VERIFIED");
			Assert.That(ReadIntField(verifiedResult, "recordedFinalWorldTick"), Is.EqualTo(600));
			Assert.That(ReadIntField(verifiedResult, "observedFinalWorldTick"), Is.EqualTo(600));
			Assert.That(ReadIntField(verifiedResult, "scheduledMatchTimeoutTick"), Is.EqualTo(600));
			Assert.That(ReadIntField(verifiedResult, "verificationTimestepMs"), Is.EqualTo(1));
			Assert.That(ReadIntField(verifiedResult, "lastValidatedSyncFrame"), Is.Not.Null);
			Assert.That(ReadIntField(verifiedResult, "outOfSyncFrame"), Is.Null);
			AssertNoStrategicDecisions(verifiedSupport);

			var desyncReplay = Path.Combine(tempRoot, "desynced.orarep");
			var expectedDesyncFrame = CopyWithMutatedSyncHash(replay, desyncReplay);
			var desyncSupport = CreateSupportDir("desynced");
			SeedContentIntoSupportDir(desyncSupport);
			var desyncExitCode = RunReplayVerification(desyncSupport, desyncReplay, wallClockTimeoutSeconds: 120);
			var desyncResult = Path.Combine(desyncSupport, "replay-verification-result.json");
			AssertVerificationResult(desyncResult, desyncExitCode, 3, "OUT_OF_SYNC");
			Assert.That(ReadIntField(desyncResult, "outOfSyncFrame"), Is.EqualTo(expectedDesyncFrame));

			var incompleteReplay = Path.Combine(tempRoot, "incomplete.orarep");
			CopyWithTruncatedOrderStream(replay, incompleteReplay, lastFrameToKeep: 100);
			var incompleteSupport = CreateSupportDir("incomplete");
			SeedContentIntoSupportDir(incompleteSupport);
			var incompleteExitCode = RunReplayVerification(incompleteSupport, incompleteReplay, wallClockTimeoutSeconds: 120);
			var incompleteResult = Path.Combine(incompleteSupport, "replay-verification-result.json");
			AssertVerificationResult(incompleteResult, incompleteExitCode, 4, "INCOMPLETE");

			var missingSupport = CreateSupportDir("missing");
			SeedContentIntoSupportDir(missingSupport);
			var missingExitCode = RunReplayVerification(
				missingSupport,
				Path.Combine(tempRoot, "missing.orarep"),
				wallClockTimeoutSeconds: 30);
			var missingResult = Path.Combine(missingSupport, "replay-verification-result.json");
			AssertVerificationResult(missingResult, missingExitCode, 1, "FAILED");
			Assert.That(ReadFailurePhase(missingResult), Is.EqualTo("PREFLIGHT"));
		}

		string CreateSupportDir(string name)
		{
			var path = Path.Combine(tempRoot, name);
			Directory.CreateDirectory(path);
			return path;
		}

		static void AssertVerificationResult(string path, int actualExitCode, int expectedExitCode, string expectedStatus)
		{
			Assert.That(File.Exists(path), Is.True, $"Replay verification result was not written: {path}");
			Assert.That(actualExitCode, Is.EqualTo(expectedExitCode), $"Unexpected exit code. Result: {path}");
			Assert.That(ReadStatus(path), Is.EqualTo(expectedStatus), $"Unexpected status. Result: {path}");
		}

		static void AssertNoStrategicDecisions(string supportDir)
		{
			var path = Path.Combine(supportDir, "Logs", "strategic-decisions.log");
			if (!File.Exists(path))
				return;

			var lines = File.ReadLines(path).Where(line =>
				line.Contains("decision", StringComparison.Ordinal) ||
				line.Contains("init-failure", StringComparison.Ordinal));
			Assert.That(lines, Is.Empty, $"Replay verification reran StrategicAI policy. Log: {path}");
		}

		static int CopyWithMutatedSyncHash(string source, string destination)
		{
			var data = File.ReadAllBytes(source);
			foreach (var packet in ReadPackets(data))
			{
				var payload = data.AsSpan(packet.PayloadOffset, packet.PayloadLength);
				if (!OrderIO.TryParseSync(payload.ToArray(), out var sync) || sync.Frame <= 0)
					continue;

				data[packet.PayloadOffset + 5] ^= 0x01;
				File.WriteAllBytes(destination, data);
				return sync.Frame;
			}

			throw new InvalidDataException("Replay does not contain a mutable SyncHash packet.");
		}

		static void CopyWithTruncatedOrderStream(string source, string destination, int lastFrameToKeep)
		{
			var data = File.ReadAllBytes(source);
			var packets = ReadPackets(data).ToArray();
			var metadataOffset = FindMetadataOffset(data, packets);
			var cutOffset = packets
				.Where(packet => packet.Frame > lastFrameToKeep)
				.Select(packet => packet.RecordOffset)
				.DefaultIfEmpty(metadataOffset)
				.First();

			using var output = File.Create(destination);
			output.Write(data, 0, cutOffset);
			output.Write(data, metadataOffset, data.Length - metadataOffset);
		}

		static IEnumerable<ReplayPacket> ReadPackets(byte[] data)
		{
			var offset = 0;
			while (offset + 4 <= data.Length)
			{
				var recordOffset = offset;
				var client = BitConverter.ToInt32(data, offset);
				if (client == ReplayMetadata.MetaStartMarker)
					yield break;

				offset += 4;
				if (offset + 4 > data.Length)
					throw new InvalidDataException("Replay packet length is truncated.");

				var length = BitConverter.ToInt32(data, offset);
				offset += 4;
				if (length < 4 || offset + length > data.Length)
					throw new InvalidDataException("Replay packet payload is truncated.");

				var frame = BitConverter.ToInt32(data, offset);
				yield return new ReplayPacket(recordOffset, offset, length, frame);
				offset += length;
			}
		}

		static int FindMetadataOffset(byte[] data, IReadOnlyList<ReplayPacket> packets)
		{
			if (packets.Count == 0)
				throw new InvalidDataException("Replay order stream is empty.");

			var last = packets[^1];
			var offset = last.PayloadOffset + last.PayloadLength;
			if (offset + 4 > data.Length || BitConverter.ToInt32(data, offset) != ReplayMetadata.MetaStartMarker)
				throw new InvalidDataException("Replay metadata trailer was not found.");

			return offset;
		}

		readonly record struct ReplayPacket(int RecordOffset, int PayloadOffset, int PayloadLength, int Frame);
	}
}
