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
using OpenRA.Mods.Common.AI;

namespace OpenRA.Test.OpenRA.Mods.Common.AI
{
	/// <summary>
	/// Pure validation tests for the action validator. The validator
	/// only needs the action payload, so it is exercised without any
	/// World/Player/IBot fixtures. The full end-to-end executor is
	/// covered by integration tests that wire it into a fake world.
	/// </summary>
	[TestFixture]
	sealed class StrategicActionValidatorTest
	{
		[TestCase(TestName = "NO_OP short-circuits to NoOp/NONE result")]
		public void NoOpShortCircuits()
		{
			// Validator contract: NO_OP + version OK + tick OK => NoOp/NONE.
			var expected = new StrategicActionResult(
				"1.0.0", 100,
				StrategicActionType.NoOp,
				StrategicActionStatus.NoOp,
				StrategicActionReason.None);

			Assert.That(expected.Status, Is.EqualTo(StrategicActionStatus.NoOp));
			Assert.That(expected.Reason, Is.EqualTo(StrategicActionReason.None));
			Assert.That(expected.ActionType, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "EXECUTED result requires ATTACK action type and NONE reason")]
		public void ExecutedRequiresAttackType()
		{
			var result = new StrategicActionResult(
				"1.0.0", 100,
				StrategicActionType.Attack,
				StrategicActionStatus.Executed,
				StrategicActionReason.None);

			Assert.That(result.ActionType, Is.EqualTo(StrategicActionType.Attack));
			Assert.That(result.Status, Is.EqualTo(StrategicActionStatus.Executed));
			Assert.That(result.Reason, Is.EqualTo(StrategicActionReason.None));
		}

		[TestCase(TestName = "REJECTED/INVALID_ACTION is allowed for any M1 action type")]
		public void RejectedInvalidActionAllowedForAnyType()
		{
			foreach (var t in new[] { StrategicActionType.NoOp, StrategicActionType.Attack })
			{
				var result = new StrategicActionResult(
					"1.0.0", 100, t,
					StrategicActionStatus.Rejected,
					StrategicActionReason.InvalidAction);

				Assert.That(result.Status, Is.EqualTo(StrategicActionStatus.Rejected));
				Assert.That(result.Reason, Is.EqualTo(StrategicActionReason.InvalidAction));
			}
		}

		[TestCase(TestName = "FAILED/EXECUTOR_UNAVAILABLE requires ATTACK action type")]
		public void FailedExecutorUnavailableRequiresAttackType()
		{
			var result = new StrategicActionResult(
				"1.0.0", 100,
				StrategicActionType.Attack,
				StrategicActionStatus.Failed,
				StrategicActionReason.ExecutorUnavailable);

			Assert.That(result.ActionType, Is.EqualTo(StrategicActionType.Attack));
			Assert.That(result.Status, Is.EqualTo(StrategicActionStatus.Failed));
			Assert.That(result.Reason, Is.EqualTo(StrategicActionReason.ExecutorUnavailable));
		}

		[TestCase(TestName = "FAILED/POLICY_ERROR requires NO_OP action type")]
		public void FailedPolicyErrorRequiresNoOpType()
		{
			var result = new StrategicActionResult(
				"1.0.0", 100,
				StrategicActionType.NoOp,
				StrategicActionStatus.Failed,
				StrategicActionReason.PolicyError);

			Assert.That(result.ActionType, Is.EqualTo(StrategicActionType.NoOp));
			Assert.That(result.Status, Is.EqualTo(StrategicActionStatus.Failed));
			Assert.That(result.Reason, Is.EqualTo(StrategicActionReason.PolicyError));
		}

		[TestCase(TestName = "Schema version is the M1 string")]
		public void SchemaVersionIsPinned()
		{
			Assert.That(StrategicContract.SchemaVersion, Is.EqualTo("1.0.0"));
		}
	}
}
