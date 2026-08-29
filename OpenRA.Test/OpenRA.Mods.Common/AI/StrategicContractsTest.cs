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

using System.Linq;
using System.Reflection;
using NUnit.Framework;
using OpenRA.Mods.Common.AI;

namespace OpenRA.Test.OpenRA.Mods.Common.AI
{
	[TestFixture]
	sealed class StrategicContractsTest
	{
		[TestCase(TestName = "StrategicObservation serializes to canonical JSON")]
		public void ObservationSerializationMatchesExample()
		{
			var observation = new StrategicObservation(
				"1.0.0",
				worldTick: 750,
				playerId: "Multi0",
				modId: "ra",
				credits: 4200,
				availableGroundAttackUnits: 12,
				activeAssaultSquads: 0);

			const string Expected = "{\"schemaVersion\":\"1.0.0\",\"worldTick\":750," +
				"\"playerId\":\"Multi0\",\"modId\":\"ra\",\"credits\":4200," +
				"\"availableGroundAttackUnits\":12,\"activeAssaultSquads\":0}";

			Assert.That(StrategicJson.Serialize(observation), Is.EqualTo(Expected));
		}

		[TestCase(TestName = "StrategicAction ATTACK serializes to canonical JSON")]
		public void ActionSerializationMatchesExample()
		{
			var action = new StrategicAction("1.0.0", worldTick: 750, type: StrategicActionType.Attack);
			const string Expected = "{\"schemaVersion\":\"1.0.0\",\"worldTick\":750,\"type\":\"ATTACK\"}";

			Assert.That(StrategicJson.Serialize(action), Is.EqualTo(Expected));
		}

		[TestCase(TestName = "StrategicActionResult EXECUTED serializes to canonical JSON")]
		public void ActionResultSerializationMatchesExample()
		{
			var result = new StrategicActionResult(
				"1.0.0", 750,
				StrategicActionType.Attack,
				StrategicActionStatus.Executed,
				StrategicActionReason.None);

			const string Expected = "{\"schemaVersion\":\"1.0.0\",\"worldTick\":750," +
				"\"actionType\":\"ATTACK\",\"status\":\"EXECUTED\",\"reason\":\"NONE\"}";

			Assert.That(StrategicJson.Serialize(result), Is.EqualTo(Expected));
		}

		[TestCase(TestName = "All M1 action type strings are upper snake case")]
		public void ActionTypeStringsAreStable()
		{
			Assert.That(StrategicJson.ActionTypeString(StrategicActionType.NoOp), Is.EqualTo("NO_OP"));
			Assert.That(StrategicJson.ActionTypeString(StrategicActionType.Attack), Is.EqualTo("ATTACK"));
		}

		[TestCase(TestName = "All M1 status strings match schema enum")]
		public void StatusStringsAreStable()
		{
			Assert.That(StrategicJson.StatusString(StrategicActionStatus.NoOp), Is.EqualTo("NO_OP"));
			Assert.That(StrategicJson.StatusString(StrategicActionStatus.Executed), Is.EqualTo("EXECUTED"));
			Assert.That(StrategicJson.StatusString(StrategicActionStatus.Rejected), Is.EqualTo("REJECTED"));
			Assert.That(StrategicJson.StatusString(StrategicActionStatus.Failed), Is.EqualTo("FAILED"));
		}

		[TestCase(TestName = "All M1 reason strings match schema enum")]
		public void ReasonStringsAreStable()
		{
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.None), Is.EqualTo("NONE"));
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.InsufficientUnits), Is.EqualTo("INSUFFICIENT_UNITS"));
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.AttackAlreadyActive), Is.EqualTo("ATTACK_ALREADY_ACTIVE"));
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.ExecutorUnavailable), Is.EqualTo("EXECUTOR_UNAVAILABLE"));
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.InvalidAction), Is.EqualTo("INVALID_ACTION"));
			Assert.That(StrategicJson.ReasonString(StrategicActionReason.PolicyError), Is.EqualTo("POLICY_ERROR"));
		}

		[TestCase(TestName = "Contract schema version is the M1 string")]
		public void SchemaVersionIsPinned()
		{
			Assert.That(StrategicContract.SchemaVersion, Is.EqualTo("1.0.0"));
			Assert.That(StrategicContract.ModId, Is.EqualTo("ra"));
		}

		[TestCase(TestName = "StrategyControl strings are stable")]
		public void StrategyControlStringsAreStable()
		{
			Assert.That(StrategicJson.StrategyControlString(StrategyControl.Autonomous), Is.EqualTo("Autonomous"));
			Assert.That(StrategicJson.StrategyControlString(StrategyControl.External), Is.EqualTo("External"));
		}

		[TestCase(TestName = "StrategicObservation exposes only the seven schema-declared properties")]
		public void StrategicObservationHasOnlySchemaProperties()
		{
			// The 1.0.0 JSON schema lists exactly seven observation
			// properties (schemaVersion, worldTick, playerId, modId,
			// credits, availableGroundAttackUnits, activeAssaultSquads).
			// Any extra C# property would either be silently dropped
			// during serialization (hidden in-process state that
			// affects the policy decision) or be rejected by a
			// strict consumer. This guard prevents reintroducing
			// hidden fields.
			var propertyNames = typeof(StrategicObservation)
				.GetProperties(BindingFlags.Public | BindingFlags.Instance)
				.Select(p => p.Name)
				.ToArray();

			var expected = new[]
			{
				"SchemaVersion",
				"WorldTick",
				"PlayerId",
				"ModId",
				"Credits",
				"AvailableGroundAttackUnits",
				"ActiveAssaultSquads",
			};

			Assert.That(propertyNames, Is.EquivalentTo(expected),
				"StrategicObservation must expose only the seven properties declared by the 1.0.0 JSON schema.");
		}

		[TestCase(TestName = "StrategicObservation has no SquadSize property")]
		public void StrategicObservationHasNoSquadSizeProperty()
		{
			// The SquadSize threshold was historically a hidden
			// field on the C# DTO. The M1 spec requires the
			// threshold to be sourced from configuration so two
			// JSON-identical observations always produce the
			// same action. Re-adding the property would silently
			// violate the canonical contract; this test is a
			// tripwire.
			var squadSize = typeof(StrategicObservation).GetProperty(
				"SquadSize",
				BindingFlags.Public | BindingFlags.Instance);

			Assert.That(squadSize, Is.Null,
				"StrategicObservation must not expose SquadSize: the threshold is a configured policy parameter, not a hidden observation field.");
		}

		[TestCase(TestName = "BotAttackReadiness exposes only the two in-process counts")]
		public void BotAttackReadinessExposesOnlyTwoCounts()
		{
			// contracts.md line 73 is explicit: BotAttackReadiness
			// is an in-process adapter value, not a JSON contract,
			// and provides the two counts needed to construct the
			// M1 observation. Historically the struct also carried
			// SquadSize, which created a third copy of the
			// threshold in addition to SquadManagerBotModuleInfo
			// and StrategicCommanderBotModuleInfo; the
			// commander now cross-checks the two configs at
			// ruleset load and BotAttackReadiness is reduced to
			// the two counts the spec names. The struct exposes
			// public readonly fields (not properties), so this
			// guard walks fields.
			var fieldNames = typeof(BotAttackReadiness)
				.GetFields(BindingFlags.Public | BindingFlags.Instance)
				.Select(f => f.Name)
				.ToArray();

			var expected = new[] { "AvailableGroundAttackUnits", "ActiveAssaultSquads" };

			Assert.That(fieldNames, Is.EquivalentTo(expected),
				"BotAttackReadiness must expose only the two counts named by contracts.md (no SquadSize).");
		}

		[TestCase(TestName = "BotAttackReadiness constructor takes only two arguments")]
		public void BotAttackReadinessConstructorHasTwoParameters()
		{
			// A second tripwire: if anyone re-adds SquadSize to
			// the struct without re-adding it to the ctor, the
			// readonly field would be silently uninitialised.
			// The ctor signature is the contract.
			var ctor = typeof(BotAttackReadiness).GetConstructors()
				.SingleOrDefault(c => c.GetParameters().Length == 2);

			Assert.That(ctor, Is.Not.Null,
				"BotAttackReadiness must have a two-parameter constructor (no SquadSize parameter).");
			var paramNames = ctor.GetParameters().Select(p => p.Name).ToArray();
			Assert.That(paramNames, Is.EquivalentTo(["availableGroundAttackUnits", "activeAssaultSquads"]));
		}
	}
}
