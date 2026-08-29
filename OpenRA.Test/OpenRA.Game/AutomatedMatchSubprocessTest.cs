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

using System.IO;
using NUnit.Framework;

namespace OpenRA.Test
{
	// Real OpenRA.exe subprocess tests for the Launch.Match runner exit-code contract.
	// These tests start the actual game binary in a private SupportDir, observe the
	// real process exit code, and read the real match-result.json that the runner
	// writes into that SupportDir.
	//
	// The unit tests in AutomatedMatchExitCodeTest cover the pure ExitCode() mapping
	// only. The user's M2 batch 1 correction explicitly forbids substituting those
	// pure-mapping assertions for subprocess evidence:
	//   "不得再用纯 GetExitCode() 映射测试代替进程级退出码证据"
	// The three cases below match the three scenarios required by that correction:
	//   1. missing spec -> exit 1, match-result.json exists with PREFLIGHT failure
	//   2. fresh SupportDir + Content tree -> no slot race, world starts
	//   3. 600 tick maxWorldTicks -> exit 4, replay file exists
	//
	// The tests are opt-in because they require bin\OpenRA.exe, a populated Content
	// tree, and several seconds of wall-clock per run. Set OPENRA_SUBPROCESS_TESTS=1
	// to run them; otherwise they are ignored so `make.ps1 tests` stays fast and
	// free of GPU/audio dependencies.
	[TestFixture]
	[Category("Subprocess")]
	[Parallelizable(ParallelScope.None)]
	sealed class AutomatedMatchSubprocessTest : AutomatedMatchSubprocessTestBase
	{
		// Scenario 1: missing spec -> runner records a preflight failure and exits 1.
		[TestCase(TestName = "Missing specification produces exit 1 and a PREFLIGHT result")]
		public void MissingSpecExitsOne()
		{
			if (!optIn)
				Assert.Ignore($"Set {OptInEnvVar}=1 to enable real OpenRA.exe subprocess tests.");

			SeedContentIntoSupportDir();

			var missingSpec = Path.Combine(tempRoot, "does-not-exist.json");
			var exit = RunOpenRaExe(tempRoot, missingSpec, wallClockTimeoutSeconds: 60);

			Assert.That(exit, Is.EqualTo(1),
				$"Expected exit code 1 (PreflightFailure) for a missing spec; got {exit}. " +
				$"See logs at {tempRoot}.");
			Assert.That(File.Exists(matchResultPath), Is.True,
				"Preflight failure must still produce a match-result.json artifact.");
			var status = ReadStatus(matchResultPath);
			Assert.That(status, Is.EqualTo("FAILED"));
			var phase = ReadFailurePhase(matchResultPath);
			Assert.That(phase, Is.EqualTo("PREFLIGHT"),
				$"Expected failurePhase PREFLIGHT; got '{phase}'.");
		}

		// Scenario 2: fresh SupportDir + pre-populated Content tree -> no slot race;
		// the runner activates both bots, sync_lobby succeeds, and startgame runs.
		// We assert by looking for the strategic + normal bot players in match-result.json
		// and by ensuring the process reached a non-preflight, non-setup state.
		[TestCase(TestName = "Fresh support directory with Content tree reaches RUNNING without slot race")]
		public void FreshSupportDirWithContentStartsWorld()
		{
			if (!optIn)
				Assert.Ignore($"Set {OptInEnvVar}=1 to enable real OpenRA.exe subprocess tests.");

			SeedContentIntoSupportDir();

			// Use the canonical example spec at its real location; the SupportDir override
			// is what makes the worker's content path unique. Cap at 200 ticks so the
			// scenario finishes in well under the wall-clock timeout.
			var shortSpec = WriteShortSpec(maxWorldTicks: 200);

			var exit = RunOpenRaExe(tempRoot, shortSpec, wallClockTimeoutSeconds: 90);

			Assert.That(File.Exists(matchResultPath), Is.True,
				$"match-result.json was not written. exit={exit}.");

			// A successful startgame (no slot race) means the runner reached at minimum
			// SETUP, and the absence of a SETUP/RUN failure phase proves both bots joined.
			var phase = ReadFailurePhase(matchResultPath);
			var status = ReadStatus(matchResultPath);
			Assert.That(phase, Is.Null.Or.Empty,
				$"Fresh support dir with Content should not hit a failure phase; got '{phase}' (status '{status}', exit {exit}).");
			Assert.That(status, Is.EqualTo("TIMED_OUT").Or.EqualTo("COMPLETED"),
				$"Expected TIMED_OUT or COMPLETED after a 200-tick run; got '{status}' (exit {exit}).");

			// Both configured bot types must appear in the captured player list.
			var playersJson = ReadJsonField(matchResultPath, "players");
			Assert.That(playersJson, Does.Contain("\"strategic\""),
				"Strategic bot player missing from match-result.json; the lobby never filled both bot slots.");
			Assert.That(playersJson, Does.Contain("\"normal\""),
				"Normal bot player missing from match-result.json; the lobby never filled both bot slots.");
		}

		// Scenario 3: 600 tick maxWorldTicks -> exit 4 and a replay file exists.
		[TestCase(TestName = "600 tick maxWorldTicks produces exit 4 and a non-empty replay file")]
		public void SixHundredTickTimeoutExitsFour()
		{
			if (!optIn)
				Assert.Ignore($"Set {OptInEnvVar}=1 to enable real OpenRA.exe subprocess tests.");

			SeedContentIntoSupportDir();

			var shortSpec = WriteShortSpec(maxWorldTicks: 600);

			var exit = RunOpenRaExe(tempRoot, shortSpec, wallClockTimeoutSeconds: 120);

			Assert.That(exit, Is.EqualTo(4),
				$"Expected exit code 4 (TimedOut) for 600-tick limit; got {exit}. See {tempRoot}.");
			Assert.That(File.Exists(matchResultPath), Is.True,
				"match-result.json was not written for the timeout case.");
			Assert.That(ReadStatus(matchResultPath), Is.EqualTo("TIMED_OUT"),
				"Expected status TIMED_OUT after the local world-tick limit fired.");
			Assert.That(ReadFailurePhase(matchResultPath), Is.Null.Or.Empty,
				"Timeout should not record a failure phase.");

			var replay = ReadReplayPath(matchResultPath);
			Assert.That(replay, Is.Not.Null.And.Not.Empty,
				"match-result.json did not record a replayPath for the TIMED_OUT case.");
			Assert.That(File.Exists(replay), Is.True,
				$"Replay file recorded in match-result.json does not exist on disk: {replay}");
			var info = new FileInfo(replay);
			Assert.That(info.Length, Is.GreaterThan(0),
				$"Replay file at {replay} is empty.");
		}
	}
}
