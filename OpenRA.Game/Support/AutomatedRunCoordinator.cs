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

namespace OpenRA
{
	public static class AutomatedRunCoordinator
	{
		public static bool IsActive => AutomatedMatchRunner.IsActive || ReplayVerificationRunner.IsActive;
		internal static bool UsesUncappedLogic => AutomatedMatchRunner.UsesUncappedLogic;
		internal static int? DeterministicBotRandomSeed =>
			AutomatedMatchRunner.IsActive ? AutomatedMatchRunner.DeterministicBotRandomSeed : null;

		public static void StartMatch(string specificationPath)
		{
			EnsureIdle();
			AutomatedMatchRunner.Start(specificationPath);
		}

		public static void StartReplayVerification(string replayPath)
		{
			EnsureIdle();
			ReplayVerificationRunner.Start(replayPath);
		}

		public static bool TryScheduleNaturalEnd(World world, int delayMilliseconds)
		{
			if (ReplayVerificationRunner.IsActive)
				return true;
			if (!AutomatedMatchRunner.IsActive || world == null || world.IsReplay)
				return false;

			var delayTicks = (delayMilliseconds + world.Timestep - 1) / world.Timestep;
			var targetTick = checked(world.WorldTick + delayTicks);
			world.OrderManager.IssueOrder(Order.Command($"schedule_match_end {targetTick}"));
			return true;
		}

		internal static void WorldStarted(World world)
		{
			if (AutomatedMatchRunner.IsActive)
				AutomatedMatchRunner.WorldStarted(world);
			else if (ReplayVerificationRunner.IsActive)
				ReplayVerificationRunner.WorldStarted(world);
		}

		internal static void Tick(World world)
		{
			if (AutomatedMatchRunner.IsActive)
				AutomatedMatchRunner.Tick(world);
			else if (ReplayVerificationRunner.IsActive)
				ReplayVerificationRunner.Tick(world);
		}

		internal static void RecordOrderWait(long elapsedStopwatchTicks)
		{
			if (AutomatedMatchRunner.IsActive)
				AutomatedMatchRunner.RecordOrderWait(elapsedStopwatchTicks);
		}

		internal static void RecordFailure(Exception ex)
		{
			if (AutomatedMatchRunner.IsActive)
				AutomatedMatchRunner.RecordFailure(ex);
			else if (ReplayVerificationRunner.IsActive)
				ReplayVerificationRunner.RecordFailure(ex);
		}

		internal static void FinalizeResult()
		{
			if (AutomatedMatchRunner.IsActive)
				AutomatedMatchRunner.FinalizeResult();
			else if (ReplayVerificationRunner.IsActive)
				ReplayVerificationRunner.FinalizeResult();
		}

		public static int GetExitCode()
		{
			if (AutomatedMatchRunner.IsActive)
				return AutomatedMatchRunner.GetExitCode();
			if (ReplayVerificationRunner.IsActive)
				return ReplayVerificationRunner.GetExitCode();

			return 0;
		}

		static void EnsureIdle()
		{
			if (IsActive)
				throw new InvalidOperationException("An automated run is already active.");
		}
	}
}
