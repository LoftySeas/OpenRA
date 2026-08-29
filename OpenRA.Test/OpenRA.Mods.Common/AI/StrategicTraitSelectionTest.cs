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
using OpenRA.Traits;

namespace OpenRA.Test.OpenRA.Mods.Common.AI
{
	/// <summary>
	/// Tests for the "pick the unique enabled trait" selection rule
	/// used by both the executor and the state provider. The M1
	/// player intentionally has two IBotAttackController instances
	/// (a disabled Normal SquadManager and an enabled External
	/// SquadManager), so the trait dictionary contains multiple
	/// matches and TraitOrDefault would throw. These tests pin the
	/// selection rule against synthetic sequences.
	/// </summary>
	[TestFixture]
	sealed class StrategicTraitSelectionTest
	{
		class FakeController : IBotAttackController
		{
			public readonly string Name;
			public FakeController(string name) { Name = name; }

			BotAttackReadiness IBotAttackController.GetAttackReadiness() => new(0, 0);
			StrategicActionResult IBotAttackController.RequestAttack(IBot bot, in StrategicAction action)
				=> new(
					action.SchemaVersion, action.WorldTick,
					StrategicActionType.Attack, StrategicActionStatus.Executed, StrategicActionReason.None);
		}

		sealed class DisabledFakeController : FakeController, IDisabledTrait
		{
			public bool IsTraitDisabled => true;
			public DisabledFakeController(string name)
				: base(name)
			{
			}
		}

		[TestCase(TestName = "Returns null when no candidates are present")]
		public void ReturnsNullForEmptySequence()
		{
			Assert.That(
				StrategicStateProvider.PickEnabledAttackController([]),
				Is.Null);
		}

		[TestCase(TestName = "Returns the single enabled controller when no disabled ones are present")]
		public void ReturnsSingleEnabled()
		{
			var only = new FakeController("only");
			Assert.That(
				StrategicStateProvider.PickEnabledAttackController([only]),
				Is.SameAs(only));
		}

		[TestCase(TestName = "Returns the unique enabled controller when one enabled and one disabled are present")]
		public void SkipsDisabledAndReturnsEnabled()
		{
			var enabled = new FakeController("enabled");
			var disabled = new DisabledFakeController("disabled");

			Assert.That(
				StrategicStateProvider.PickEnabledAttackController(
					[disabled, enabled]),
				Is.SameAs(enabled),
				"Must skip the disabled controller and return the enabled one.");
		}

		[TestCase(TestName = "Returns null when two enabled controllers would match (ambiguous)")]
		public void ReturnsNullWhenAmbiguous()
		{
			var first = new FakeController("first");
			var second = new FakeController("second");

			Assert.That(
				StrategicStateProvider.PickEnabledAttackController(
					[first, second]),
				Is.Null,
				"Multiple enabled IBotAttackController instances would cause TraitOrDefault to throw; the state provider must refuse to choose.");
		}

		[TestCase(TestName = "Returns null when every candidate is disabled")]
		public void ReturnsNullWhenAllDisabled()
		{
			var a = new DisabledFakeController("a");
			var b = new DisabledFakeController("b");

			Assert.That(
				StrategicStateProvider.PickEnabledAttackController(
					[a, b]),
				Is.Null);
		}

		[TestCase(TestName = "Executor and state provider share the same selection rule")]
		public void ExecutorAndStateProviderAgree()
		{
			var enabled = new FakeController("enabled");
			var disabled = new DisabledFakeController("disabled");
			var candidates = new[] { disabled, enabled };

			Assert.That(
				StrategicStateProvider.PickEnabledAttackController(candidates),
				Is.SameAs(StrategicActionExecutor.PickEnabledAttackController(candidates)),
				"Both lookups must agree so the state provider observes the same controller the executor dispatches to.");
		}
	}
}
