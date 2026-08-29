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
using System.IO;
using System.Security.Cryptography;
using NUnit.Framework;
using OpenRA.FileFormats;
using OpenRA.Network;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class AutomatedMatchEvidenceTest
	{
		[TestCase(TestName = "Order digest covers the stream and excludes replay metadata")]
		public void OrderDigestIgnoresMetadataTrailer()
		{
			using var temporary = new TemporaryFile();
			var packet = new OrderPacket([Order.Command("evidence-test")]).Serialize(7);
			using (var writer = new BinaryWriter(File.Create(temporary.Path)))
			{
				writer.Write(3);
				writer.Write(packet.Length);
				writer.Write(packet);
				writer.Write(ReplayMetadata.MetaStartMarker);
				writer.Write(123456);
			}

			var payload = packet[sizeof(int)..];
			var expectedBytes = new byte[3 * sizeof(int) + payload.Length];
			BitConverter.GetBytes(7).CopyTo(expectedBytes, 0);
			BitConverter.GetBytes(3).CopyTo(expectedBytes, 4);
			BitConverter.GetBytes(payload.Length).CopyTo(expectedBytes, 8);
			payload.CopyTo(expectedBytes, 12);
			var expected = Convert.ToHexString(SHA256.HashData(expectedBytes)).ToLowerInvariant();
			Assert.That(AutomatedMatchEvidence.OrderStreamSha256(temporary.Path), Is.EqualTo(expected));
		}

		[TestCase(TestName = "Strategic digest ignores timestamps and unrelated lines")]
		public void StrategicDigestNormalizesLogLines()
		{
			using var first = new TemporaryFile();
			using var second = new TemporaryFile();
			File.WriteAllText(first.Path, "[2026-01-01T00:00:00] decision tick=75 bot=strategic\nignored\n");
			File.WriteAllText(second.Path, "[2030-02-02T01:02:03] decision tick=75 bot=strategic\n");

			Assert.That(
				AutomatedMatchEvidence.StrategicDecisionSha256(first.Path),
				Is.EqualTo(AutomatedMatchEvidence.StrategicDecisionSha256(second.Path)));
		}

		[TestCase(TestName = "Order digest normalizes network packet interleaving and excludes sync packets")]
		public void OrderDigestNormalizesPacketInterleaving()
		{
			using var first = new TemporaryFile();
			using var second = new TemporaryFile();
			var frameSeven = new OrderPacket([Order.Command("first")]).Serialize(7);
			var frameEight = new OrderPacket([Order.Command("second")]).Serialize(8);
			var sync = OrderIO.SerializeSync((7, 123456, 0));

			WriteReplay(first.Path, [(3, frameSeven), (3, sync), (3, frameEight)]);
			WriteReplay(second.Path, [(3, frameEight), (3, frameSeven), (3, sync)]);

			Assert.That(
				AutomatedMatchEvidence.OrderStreamSha256(first.Path),
				Is.EqualTo(AutomatedMatchEvidence.OrderStreamSha256(second.Path)));
		}

		[TestCase(TestName = "Order digest excludes projected frames that were not processed before termination")]
		public void OrderDigestStopsAtFinalNetworkFrame()
		{
			using var withFuture = new TemporaryFile();
			using var appliedOnly = new TemporaryFile();
			var applied = new OrderPacket([Order.Command("applied")]).Serialize(7);
			var projected = new OrderPacket([Order.Command("projected")]).Serialize(8);
			WriteReplay(withFuture.Path, [(3, applied), (3, projected)]);
			WriteReplay(appliedOnly.Path, [(3, applied)]);

			Assert.That(
				AutomatedMatchEvidence.OrderStreamSha256(withFuture.Path, maxExclusiveFrame: 8),
				Is.EqualTo(AutomatedMatchEvidence.OrderStreamSha256(appliedOnly.Path, maxExclusiveFrame: 8)));
		}

		static void WriteReplay(string path, (int Client, byte[] Packet)[] packets)
		{
			using var writer = new BinaryWriter(File.Create(path));
			foreach (var (client, packet) in packets)
			{
				writer.Write(client);
				writer.Write(packet.Length);
				writer.Write(packet);
			}

			writer.Write(ReplayMetadata.MetaStartMarker);
			writer.Write(123456);
		}

		sealed class TemporaryFile : IDisposable
		{
			public string Path { get; } = System.IO.Path.GetTempFileName();
			public void Dispose() { File.Delete(Path); }
		}
	}
}
