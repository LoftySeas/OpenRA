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

namespace OpenRA.Mods.Common.AI
{
	/// <summary>
	/// The strategic AI contract schema version consumed by M1.
	/// Mismatched versions are fatal at initialization; no runtime
	/// best-effort conversion is supported.
	/// </summary>
	public static class StrategicContract
	{
		public const string SchemaVersion = "1.0.0";
		public const string ModId = "ra";
	}

	/// <summary>
	/// The complete M1 action space. Adding a value is a breaking
	/// schema change and must bump the contract major version.
	/// </summary>
	public enum StrategicActionType
	{
		NoOp,
		Attack,
	}

	/// <summary>
	/// The result of evaluating one action at one world tick.
	/// A result describes the request outcome, not the eventual
	/// squad or combat result.
	/// </summary>
	public enum StrategicActionStatus
	{
		NoOp,
		Executed,
		Rejected,
		Failed,
	}

	/// <summary>
	/// Why an action produced a particular status. The status /
	/// reason pair is validated by the canonical JSON schema and
	/// must agree with the action type.
	/// </summary>
	public enum StrategicActionReason
	{
		None,
		InsufficientUnits,
		AttackAlreadyActive,
		ExecutorUnavailable,
		InvalidAction,
		PolicyError,
	}

	/// <summary>
	/// SquadManager scheduling control. Autonomous preserves the
	/// current automatic scheduling behaviour. External suppresses
	/// the periodic ground assault and rush creation paths so that
	/// an external <see cref="StrategicActionType.Attack"/> request
	/// drives squad creation.
	/// </summary>
	public enum StrategyControl
	{
		Autonomous,
		External,
	}

	/// <summary>
	/// Immutable, in-process adapter value used by the state
	/// provider and attack controller. Not part of the JSON
	/// contract; just the two counts the M1 observation needs.
	/// The formation-size threshold lives on
	/// <c>SquadManagerBotModuleInfo</c> as the single configured
	/// source of truth; the rule policy and the controller both
	/// read it from the same trait info, and the commander
	/// cross-checks the two values at ruleset load so they
	/// cannot drift.
	/// </summary>
	public readonly struct BotAttackReadiness
	{
		public readonly int AvailableGroundAttackUnits;
		public readonly int ActiveAssaultSquads;

		public BotAttackReadiness(int availableGroundAttackUnits, int activeAssaultSquads)
		{
			AvailableGroundAttackUnits = availableGroundAttackUnits;
			ActiveAssaultSquads = activeAssaultSquads;
		}
	}

	/// <summary>
	/// Immutable observation captured for one bot at one world tick.
	/// Serializes to the canonical <c>StrategicObservation</c> record.
	/// The observation carries only the seven properties declared by
	/// the 1.0.0 JSON schema. The policy threshold is sourced from
	/// configuration (not from this struct) so two observations with
	/// identical JSON always produce identical actions.
	/// </summary>
	public sealed class StrategicObservation
	{
		public string SchemaVersion { get; }
		public int WorldTick { get; }
		public string PlayerId { get; }
		public string ModId { get; }
		public int Credits { get; }
		public int AvailableGroundAttackUnits { get; }
		public int ActiveAssaultSquads { get; }

		public StrategicObservation(
			string schemaVersion,
			int worldTick,
			string playerId,
			string modId,
			int credits,
			int availableGroundAttackUnits,
			int activeAssaultSquads)
		{
			SchemaVersion = schemaVersion;
			WorldTick = worldTick;
			PlayerId = playerId;
			ModId = modId;
			Credits = credits;
			AvailableGroundAttackUnits = availableGroundAttackUnits;
			ActiveAssaultSquads = activeAssaultSquads;
		}
	}

	/// <summary>
	/// Immutable action produced by a policy for a specific observation.
	/// M1 actions carry no target, confidence, priority, or parameters.
	/// </summary>
	public sealed class StrategicAction
	{
		public string SchemaVersion { get; }
		public int WorldTick { get; }
		public StrategicActionType Type { get; }

		public StrategicAction(string schemaVersion, int worldTick, StrategicActionType type)
		{
			SchemaVersion = schemaVersion;
			WorldTick = worldTick;
			Type = type;
		}
	}

	/// <summary>
	/// Immutable result of evaluating one action. Status and reason
	/// combinations are validated by the canonical JSON schema.
	/// </summary>
	public sealed class StrategicActionResult
	{
		public string SchemaVersion { get; }
		public int WorldTick { get; }
		public StrategicActionType ActionType { get; }
		public StrategicActionStatus Status { get; }
		public StrategicActionReason Reason { get; }

		public StrategicActionResult(
			string schemaVersion,
			int worldTick,
			StrategicActionType actionType,
			StrategicActionStatus status,
			StrategicActionReason reason)
		{
			SchemaVersion = schemaVersion;
			WorldTick = worldTick;
			ActionType = actionType;
			Status = status;
			Reason = reason;
		}
	}
}
