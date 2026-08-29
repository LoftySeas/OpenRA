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

using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using OpenRA.FileFormats;
using OpenRA.Network;

namespace OpenRA.Test
{
	// Real OpenRA.exe evidence for the M2 batch 2 ScheduleMatchTimeout contract.
	// One worker supplies all coupled assertions so the gate cannot accidentally compare
	// artifacts from different runs and does not pay for three identical 600-tick matches.
	[TestFixture]
	[Category("Subprocess")]
	[Parallelizable(ParallelScope.None)]
	sealed class AutomatedMatchScheduleTimeoutSubprocessTest : AutomatedMatchSubprocessTestBase
	{
		[TestCase(TestName = "600-tick worker records and applies one server ScheduleMatchTimeout Order")]
		public void SixHundredTickWorkerRecordsAndAppliesScheduleMatchTimeout()
		{
			SeedContentIntoSupportDir();
			var specification = WriteShortSpec(maxWorldTicks: 600);

			var exitCode = RunOpenRaExe(tempRoot, specification, wallClockTimeoutSeconds: 120);

			Assert.That(exitCode, Is.EqualTo(4),
				$"Expected exit 4 (TimedOut); got {exitCode}. Artifacts: {tempRoot}");
			Assert.That(File.Exists(matchResultPath), Is.True,
				$"match-result.json was not written. Artifacts: {tempRoot}");
			Assert.That(ReadStatus(matchResultPath), Is.EqualTo("TIMED_OUT"));
			Assert.That(ReadFailurePhase(matchResultPath), Is.Null.Or.Empty);
			Assert.That(ReadIntField(matchResultPath, "finalWorldTick"), Is.EqualTo(600));

			var replay = ReadReplayPath(matchResultPath);
			Assert.That(replay, Is.Not.Null.And.Not.Empty,
				"match-result.json did not record a replayPath.");
			Assert.That(File.Exists(replay), Is.True,
				$"Replay file does not exist: {replay}");

			var metadata = ReplayMetadata.Read(replay);
			Assert.That(metadata, Is.Not.Null,
				$"Could not read replay metadata from {replay}.");
			Assert.That(metadata.GameInfo.FinalGameTick, Is.EqualTo(600),
				$"Replay trailer FinalGameTick must be 600; got {metadata.GameInfo.FinalGameTick}.");

			var scheduleOrders = new List<(int FromClient, int Frame, string TargetString)>();
			foreach (var entry in ScanOrderStream(replay))
			{
				if (entry.Order.OrderString == "ScheduleMatchTimeout")
					scheduleOrders.Add((entry.FromClient, entry.Frame, entry.Order.TargetString));
			}

			Assert.That(scheduleOrders, Has.Count.EqualTo(1),
				$"Expected exactly one ScheduleMatchTimeout Order; found {scheduleOrders.Count}: " +
				$"{string.Join(", ", scheduleOrders)}");

			var (fromClient, frame, targetString) = scheduleOrders[0];
			Assert.That(fromClient, Is.EqualTo(0),
				$"ScheduleMatchTimeout must be server-dispatched; got From == {fromClient}.");
			Assert.That(frame, Is.EqualTo(0),
				$"ScheduleMatchTimeout must be recorded in a frame-0 setup packet; got Frame == {frame}.");
			Assert.That(targetString, Is.EqualTo("600"));
		}

		// Mirrors ReplayConnection's packet loop. The network packet frame is deliberately
		// used only to prove setup-order placement; it is not treated as a WorldTick.
		static IEnumerable<(int FromClient, int Frame, Order Order)> ScanOrderStream(string replayPath)
		{
			using var stream = File.OpenRead(replayPath);
			while (stream.Position < stream.Length)
			{
				var client = stream.ReadInt32();
				if (client == ReplayMetadata.MetaStartMarker)
					yield break;

				var packetLength = stream.ReadInt32();
				var packet = stream.ReadBytes(packetLength);
				if (!OrderIO.TryParseOrderPacket(packet, out var data))
					continue;

				foreach (var order in data.Orders.GetOrders(null))
				{
					if (order != null)
						yield return (client, data.Frame, order);
				}
			}
		}
	}
}
