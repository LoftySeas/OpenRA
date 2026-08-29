#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is
 * made available to you under the terms of the GNU General Public
 * License as published by the Free Software Foundation, either
 * version 3 of the License, or (at your option) any later version.
 * For more information, see COPYING.
 */
#endregion

using NUnit.Framework;
using OpenRA.Mods.AI;
using OpenRA.Mods.Common.AI;

namespace OpenRA.Test.OpenRA.Mods.AI
{
	[TestFixture]
	sealed class RuleAttackPolicyTest
	{
		const int SquadSize = 40;

		static StrategicObservation MakeObservation(int availableUnits, int activeSquads)
		{
			return new StrategicObservation(
				"1.0.0", 750, "Multi0", "ra", 0, availableUnits, activeSquads);
		}

		[TestCase(TestName = "Emits ATTACK when available units meet squad size and no active squad")]
		public void EmitsAttackWhenReady()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = MakeObservation(availableUnits: 40, activeSquads: 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.Attack));
			Assert.That(action.SchemaVersion, Is.EqualTo("1.0.0"));
			Assert.That(action.WorldTick, Is.EqualTo(750));
		}

		[TestCase(TestName = "Emits ATTACK when available units exceed squad size")]
		public void EmitsAttackAboveSquadSize()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = MakeObservation(availableUnits: 50, activeSquads: 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.Attack));
		}

		[TestCase(TestName = "Emits NO_OP when available units are below squad size")]
		public void EmitsNoOpBelowSquadSize()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = MakeObservation(availableUnits: 39, activeSquads: 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "Emits NO_OP at exactly squad size minus one")]
		public void EmitsNoOpAtSquadSizeMinusOne()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = MakeObservation(availableUnits: SquadSize - 1, activeSquads: 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "Emits NO_OP when an active assault squad already exists")]
		public void EmitsNoOpWhenSquadActive()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = MakeObservation(availableUnits: 60, activeSquads: 1);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "Emits NO_OP when observation schema version mismatches")]
		public void EmitsNoOpOnVersionMismatch()
		{
			var policy = new RuleAttackPolicy(SquadSize);
			var observation = new StrategicObservation(
				"0.9.0", 750, "Multi0", "ra", 0, 12, 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "Emits NO_OP when the configured squad size is zero or negative")]
		public void EmitsNoOpWhenSquadSizeNotConfigured()
		{
			// A zero-threshold policy must never emit ATTACK: the
			// observation's available count would trivially satisfy
			// the threshold and silently trigger a request. The
			// commander passes SquadSize from configuration; the
			// guard here is the policy-side safety net.
			var policy = new RuleAttackPolicy(squadSize: 0);
			var observation = MakeObservation(availableUnits: 50, activeSquads: 0);

			var action = policy.Decide(in observation);

			Assert.That(action.Type, Is.EqualTo(StrategicActionType.NoOp));
		}

		[TestCase(TestName = "SquadSize threshold is taken from the constructor, not from the observation")]
		public void ThresholdSourcedFromConstructor()
		{
			// Two policies with different thresholds must produce
			// different actions for the same observation. The
			// observation no longer carries a hidden squadSize
			// field, so the only source of the threshold is the
			// constructor argument.
			var lenient = new RuleAttackPolicy(squadSize: 4);
			var strict = new RuleAttackPolicy(squadSize: 100);
			var observation = MakeObservation(availableUnits: 8, activeSquads: 0);

			Assert.That(lenient.Decide(in observation).Type, Is.EqualTo(StrategicActionType.Attack));
			Assert.That(strict.Decide(in observation).Type, Is.EqualTo(StrategicActionType.NoOp));
		}
	}
}
