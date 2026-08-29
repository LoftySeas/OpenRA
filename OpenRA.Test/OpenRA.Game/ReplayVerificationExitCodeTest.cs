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

using NUnit.Framework;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class ReplayVerificationExitCodeTest
	{
		[TearDown]
		public void TearDown()
		{
			ReplayVerificationRunner.ResetForTest();
			AutomatedMatchRunner.ResetForTest();
		}

		static void SetResult(string status, string failurePhase = null)
		{
			ReplayVerificationRunner.SetResultForTest(new ReplayVerificationRunner.VerificationResult
			{
				Status = status,
				FailurePhase = failurePhase,
			});
		}

		[TestCase("VERIFIED", null, 0)]
		[TestCase("FAILED", "PREFLIGHT", 1)]
		[TestCase("FAILED", "SETUP", 2)]
		[TestCase("OUT_OF_SYNC", null, 3)]
		[TestCase("INCOMPLETE", null, 4)]
		[TestCase("FINAL_TICK_MISMATCH", null, 4)]
		[TestCase("FAILED", "RUN", 5)]
		[TestCase("ABORTED", null, 5)]
		public void StatusMapsToStableExitCode(string status, string failurePhase, int expected)
		{
			SetResult(status, failurePhase);

			Assert.That(ReplayVerificationRunner.GetExitCode(), Is.EqualTo(expected));
		}

		[TestCase(TestName = "Automated run coordinator routes replay verification exit codes")]
		public void CoordinatorRoutesReplayExitCode()
		{
			SetResult("OUT_OF_SYNC");

			Assert.That(AutomatedRunCoordinator.IsActive, Is.True);
			Assert.That(AutomatedRunCoordinator.GetExitCode(), Is.EqualTo(3));
		}

		[TestCase(TestName = "Automated run coordinator routes match exit codes")]
		public void CoordinatorRoutesMatchExitCode()
		{
			AutomatedMatchRunner.SetResultForTest(new AutomatedMatchRunner.MatchResult
			{
				Status = "TIMED_OUT",
			}, timedOutFlag: true);

			Assert.That(AutomatedRunCoordinator.IsActive, Is.True);
			Assert.That(AutomatedRunCoordinator.GetExitCode(), Is.EqualTo(4));
		}

		[TestCase("LOADING", false)]
		[TestCase("VERIFYING", true)]
		[TestCase("VERIFIED", false)]
		public void CoordinatorUsesUncappedLogicOnlyWhileReplayIsVerifying(string status, bool expected)
		{
			ReplayVerificationRunner.SetResultForTest(new ReplayVerificationRunner.VerificationResult
			{
				Status = status,
			}, finalizedFlag: false);

			Assert.That(AutomatedRunCoordinator.UsesUncappedLogic, Is.EqualTo(expected));
		}
	}
}
