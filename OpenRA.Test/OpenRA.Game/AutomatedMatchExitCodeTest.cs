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
	sealed class AutomatedMatchExitCodeTest
	{
		[TearDown]
		public void TearDown()
		{
			AutomatedMatchRunner.ResetForTest();
		}

		static void SetResult(string status, string failurePhase, bool timedOutFlag)
		{
			// MatchResult is internal; we use a fresh instance because GetExitCode()
			// only reads Status and FailurePhase. Other fields are left at their defaults.
			var result = new AutomatedMatchRunner.MatchResult
			{
				Status = status,
				FailurePhase = failurePhase,
			};
			AutomatedMatchRunner.SetResultForTest(result, timedOutFlag);
		}

		[TestCase(TestName = "Exit code 0 when no automated match is active")]
		public void NoMatchReturnsSuccess()
		{
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(0));
		}

		[TestCase(TestName = "Exit code 0 when status is COMPLETED")]
		public void CompletedReturnsSuccess()
		{
			SetResult("COMPLETED", null, false);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(0));
		}

		[TestCase(TestName = "Exit code 4 when status is TIMED_OUT")]
		public void TimedOutReturnsTimedOut()
		{
			SetResult("TIMED_OUT", null, true);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(4));
		}

		[TestCase(TestName = "Exit code 1 when status is FAILED with PREFLIGHT phase")]
		public void PreflightFailureReturnsPreflight()
		{
			SetResult("FAILED", "PREFLIGHT", false);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(1));
		}

		[TestCase(TestName = "Exit code 2 when status is FAILED with SETUP phase")]
		public void SetupFailureReturnsSetup()
		{
			SetResult("FAILED", "SETUP", false);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(2));
		}

		[TestCase(TestName = "Exit code 3 when status is FAILED with RUN phase")]
		public void RuntimeFailureReturnsRuntime()
		{
			SetResult("FAILED", "RUN", false);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(3));
		}

		[TestCase(TestName = "Exit code 5 when status is ABORTED")]
		public void AbortedReturnsAborted()
		{
			SetResult("ABORTED", null, false);
			Assert.That(AutomatedMatchRunner.GetExitCode(), Is.EqualTo(5));
		}
	}
}
