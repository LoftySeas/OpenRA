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

using System;
using OpenRA.Mods.Common.AI;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.AI
{
	/// <summary>
	/// M1 strategic decision loop. Runs on the host through the
	/// existing <see cref="IBotTick"/> lifecycle. Captures one
	/// observation, asks the policy for one action, executes it,
	/// and records an unsynchronized diagnostic event.
	/// </summary>
	[TraitLocation(SystemActors.Player)]
	[Desc("Strategic AI commander that drives a rule policy against the existing bot modules.")]
	public sealed class StrategicCommanderBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Number of world ticks between strategic decisions. Must be greater than zero at ruleset load.")]
		public int DecisionIntervalTicks = 75;

		[Desc("Configured assault squad formation size. Must match the SquadManagerBotModule.SquadSize on the same " +
			"player actor whose StrategyControl is External (the M1 controller the commander dispatches to) so the " +
			"rule policy and the controller agree on the formation threshold. At ruleset load the commander " +
			"requires exactly one such External SquadManagerBotModuleInfo and throws a YamlException if the " +
			"SquadSize mismatches, the External controller is missing, or there are multiple.")]
		public int SquadSize = 40;

		public override object Create(ActorInitializer init) { return new StrategicCommanderBotModule(init.Self, this); }

		public override void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			base.RulesetLoaded(rules, ai);
			if (DecisionIntervalTicks <= 0)
				throw new YamlException("StrategicCommanderBotModule.DecisionIntervalTicks must be greater than zero.");

			if (SquadSize <= 0)
				throw new YamlException("StrategicCommanderBotModule.SquadSize must be greater than zero.");

			// Cross-check the configured threshold against the
			// single SquadManagerBotModuleInfo on the same actor
			// whose StrategyControl is External. The rule policy
			// (constructed from this SquadSize) and the External
			// controller (which gates TryCreateAssaultSquad on
			// Info.SquadSize) must agree. Mismatches are fatal
			// at load time so the discrepancy cannot silently
			// desynchronise observation and execution. Other
			// SquadManagerBotModuleInfo instances on the same
			// actor with different SquadSizes are intentionally
			// ignored here: they belong to other bot types
			// (Rush, Normal, Turtle, Naval) and are gated by
			// their own RequiresCondition at runtime; the
			// commander's rule is the unique-External pairing,
			// not a global "every SquadManager matches" check.
			ValidateSquadSizeConsistency(SquadSize, ai);
		}

		// Test seam: the same cross-check RulesetLoaded performs,
		// exposed for unit tests that cannot stand up a full
		// Ruleset/ActorInfo graph. Production RulesetLoaded passes
		// the same actor's info (the one the commander lives on)
		// and looks for the single External SquadManager on it.
		internal static void ValidateSquadSizeConsistency(int commanderSquadSize, ActorInfo ai)
		{
			if (ai == null)
				throw new YamlException(
					"StrategicCommanderBotModule.RulesetLoaded received a null ActorInfo; the commander must live on a player actor.");

			// The M1 commander is wired to a single External
			// SquadManager on the same player. Find the unique
			// enabled-by-config candidate. Any other count
			// (zero, two, or more) is a misconfiguration.
			SquadManagerBotModuleInfo external = null;
			var externalCount = 0;
			foreach (var sm in ai.TraitInfos<SquadManagerBotModuleInfo>())
			{
				if (sm.StrategyControl != StrategyControl.External)
					continue;
				external = sm;
				externalCount++;
			}

			if (externalCount == 0)
				throw new YamlException(
					"StrategicCommanderBotModule on actor '" + ai.Name +
					"' requires exactly one SquadManagerBotModuleInfo with StrategyControl: External; found 0.");

			if (externalCount > 1)
				throw new YamlException(
					"StrategicCommanderBotModule on actor '" + ai.Name +
					"' requires exactly one SquadManagerBotModuleInfo with StrategyControl: External; found " +
					externalCount + ".");

			if (external.SquadSize != commanderSquadSize)
				throw new YamlException(
					"StrategicCommanderBotModule.SquadSize (" + commanderSquadSize + ") must match " +
					"SquadManagerBotModule.SquadSize (" + external.SquadSize + ") on actor '" + ai.Name + "'.");
		}
	}

	public class StrategicCommanderBotModule : ConditionalTrait<StrategicCommanderBotModuleInfo>, IBotTick
	{
		readonly Actor self;
		readonly IStrategicPolicy policy;
		StrategicDecisionLog DecisionLogBacking { get; } = new();
		int enabledAtTick;

		public StrategicDecisionLog DecisionLog => DecisionLogBacking;
		public bool InitFailed { get; private set; }
		public int InitFailureTick { get; private set; }

		public StrategicCommanderBotModule(Actor self, StrategicCommanderBotModuleInfo info)
			: base(info)
		{
			this.self = self;
			policy = new RuleAttackPolicy(ResolveSquadSize(info.SquadSize, AutomatedMatchRunner.StrategicSquadSizeOverride));

			// The init-failure check is deferred to TraitEnabled
			// so that subclasses (e.g. tests) can finish
			// initializing their state before the production
			// class reads the virtual GetStateProvider() seam.
		}

		internal static int ResolveSquadSize(int configuredSquadSize, int? candidateSquadSize) =>
			candidateSquadSize ?? configuredSquadSize;

		protected override void TraitEnabled(Actor self)
		{
			base.TraitEnabled(self);

			// The first decision fires DecisionIntervalTicks world
			// ticks after this callback, regardless of the absolute
			// world tick value. This is the "75 world ticks of
			// enabled bot operation" semantic from m1-implementation.md.
			enabledAtTick = self.World.WorldTick;

			// Initialization-time controller validation. The spec
			// requires the commander to fail loudly at startup if
			// the wiring is incomplete rather than running silently
			// with a missing state provider. The state provider's
			// own Capture() still throws when the attack controller
			// is missing; the per-decision path records that as a
			// PolicyError so the failure is visible in the log.
			EnsureInitialized();
		}

		// Idempotent init check. Production reaches this via
		// TraitEnabled; tests that need to drive the check
		// without a real World call it directly. Both the
		// IStrategicStateProvider presence and the unique
		// enabled IBotAttackController presence are checked
		// here so the loop short-circuits permanently if the
		// wiring is incomplete.
		internal void EnsureInitialized()
		{
			if (InitFailed)
				return;

			if (GetStateProvider() == null)
			{
				InitFailed = true;
				RecordInitFailure("IStrategicStateProvider");
				return;
			}

			// Reuse the same selection rule as StrategicStateProvider:
			// a controller is acceptable only if exactly one
			// IBotAttackController on the player is enabled. Zero
			// enabled (missing) or two or more (ambiguous) is
			// fatal at init time so every BotTick permanently
			// short-circuits with a single init-failure event.
			var controller = FindEnabledAttackController();
			if (controller == null)
			{
				InitFailed = true;
				RecordInitFailure("IBotAttackController");
			}
		}

		// Virtual state-access seam. The production path reads these
		// values off the owning Actor and its World; tests can
		// override the seam to drive the production evaluation loop
		// against synthetic state without spinning up a real World.
		internal virtual IStrategicStateProvider GetStateProvider()
		{
			return self.Owner.PlayerActor?.TraitOrDefault<IStrategicStateProvider>();
		}

		internal virtual IStrategicActionExecutor GetExecutor()
		{
			return self.Owner.PlayerActor?.TraitOrDefault<IStrategicActionExecutor>();
		}

		// Virtual seam for the unique-enabled-attack-controller
		// selection. The production path delegates to the same
		// PickEnabledAttackController rule used by the state
		// provider; tests override this seam to inject null
		// (missing) or a custom controller. Defined as a separate
		// seam (rather than re-deriving the rule inline) so the
		// commander and the state provider cannot drift.
		internal virtual IBotAttackController FindEnabledAttackController()
		{
			var player = self?.Owner;
			if (player?.PlayerActor == null)
				return null;

			return StrategicStateProvider.PickEnabledAttackController(
				player.PlayerActor.TraitsImplementing<IBotAttackController>());
		}

		// Production policy seam. Tests override this to inject a
		// throwing or otherwise instrumented policy without touching
		// the production class.
		internal virtual IStrategicPolicy GetPolicy() => policy;

		internal virtual int GetWorldTick() => self.World.WorldTick;

		internal virtual bool GetIsReplay() => self.World.IsReplay;

		// Internal hooks used by tests to drive the lifecycle without
		// a real World/Actor. The enabled-at tick defaults to 0 so
		// the existing 75-tick cadence tests keep their assumption
		// that the trait was enabled at the start of the world.
		internal void SetEnabledAtTickForTest(int tick) { enabledAtTick = tick; }
		internal void ResetInitFailureForTest() { InitFailed = false; }

		void IBotTick.BotTick(IBot bot)
		{
			// Replays must not evaluate the policy: the existing
			// ModularBot activation guard prevents BotTick from
			// running during replay playback, but we double-check
			// the world state here as a defence in depth.
			if (GetIsReplay())
				return;

			// Init-time controller failure short-circuits all
			// subsequent decisions. The init failure is already
			// recorded once at construction; do not spam the log.
			if (InitFailed)
				return;

			var tick = GetWorldTick();
			if (tick < enabledAtTick)
				return;

			var ticksSinceEnabled = tick - enabledAtTick;
			if (ticksSinceEnabled < Info.DecisionIntervalTicks)
				return;

			if ((ticksSinceEnabled - Info.DecisionIntervalTicks) % Info.DecisionIntervalTicks != 0)
				return;

			EvaluateDecision(bot);
		}

		internal void EvaluateDecision(IBot bot)
		{
			StrategicObservation observation;
			try
			{
				var stateProvider = GetStateProvider();
				if (stateProvider == null)
				{
					RecordFailure(bot);
					return;
				}

				observation = stateProvider.Capture(bot);
			}
			catch (Exception ex)
			{
				RecordFailure(bot, ex);
				return;
			}

			StrategicAction action;
			try
			{
				action = GetPolicy().Decide(in observation);
			}
			catch (Exception ex)
			{
				// Policy exceptions are caught and recorded. The
				// decision tick degrades to a structured failure
				// with no retry, per architecture.md.
				var failure = new StrategicActionResult(
					observation.SchemaVersion,
					observation.WorldTick,
					StrategicActionType.NoOp,
					StrategicActionStatus.Failed,
					StrategicActionReason.PolicyError);
				RecordActionResult(bot, StrategicActionType.NoOp, failure, ex);
				return;
			}

			if (action.WorldTick != observation.WorldTick || action.SchemaVersion != observation.SchemaVersion)
			{
				// Defensive: the policy contract is that actions
				// share the observation's tick and version. A
				// mismatch is treated as an invalid action and
				// recorded, never silently retried.
				var invalid = new StrategicActionResult(
					observation.SchemaVersion,
					observation.WorldTick,
					action.Type,
					StrategicActionStatus.Rejected,
					StrategicActionReason.InvalidAction);
				RecordActionResult(bot, action.Type, invalid, null);
				return;
			}

			if (action.Type == StrategicActionType.NoOp)
			{
				var noop = new StrategicActionResult(
					action.SchemaVersion,
					action.WorldTick,
					StrategicActionType.NoOp,
					StrategicActionStatus.NoOp,
					StrategicActionReason.None);
				RecordActionResult(bot, StrategicActionType.NoOp, noop, null);
				return;
			}

			StrategicActionResult result;
			try
			{
				var executor = GetExecutor();
				if (executor == null)
				{
					result = new StrategicActionResult(
						action.SchemaVersion,
						action.WorldTick,
						StrategicActionType.Attack,
						StrategicActionStatus.Rejected,
						StrategicActionReason.ExecutorUnavailable);
					RecordActionResult(bot, StrategicActionType.Attack, result, null);
					return;
				}

				result = executor.Execute(bot, in action);
			}
			catch (Exception ex)
			{
				result = new StrategicActionResult(
					action.SchemaVersion,
					action.WorldTick,
					StrategicActionType.Attack,
					StrategicActionStatus.Failed,
					StrategicActionReason.ExecutorUnavailable);
				RecordActionResult(bot, StrategicActionType.Attack, result, ex);
				return;
			}

			RecordActionResult(bot, action.Type, result, null);
		}

		void RecordInitFailure(string component)
		{
			InitFailureTick = GetWorldTick();
			var evt = new StrategicDecisionEvent(
				StrategicContract.SchemaVersion,
				InitFailureTick,
				self?.Owner?.PlayerActor?.Info?.Name,
				StrategicActionType.NoOp,
				StrategicActionStatus.Failed,
				StrategicActionReason.PolicyError,
				new InvalidOperationException("StrategicAI init failure: missing " + component));
			DecisionLogBacking.Record(evt);
			Log.Write("strategic",
				"init-failure tick=" + InitFailureTick + " component=" + component);
		}

		void RecordFailure(IBot bot, Exception ex)
		{
			// State-capture failures are recorded as a NO_OP
			// policy failure so the diagnostic surface stays
			// consistent with the schema.
			var evt = new StrategicDecisionEvent(
				StrategicContract.SchemaVersion,
				GetWorldTick(),
				bot?.Info?.Type,
				StrategicActionType.NoOp,
				StrategicActionStatus.Failed,
				StrategicActionReason.PolicyError,
				ex);
			DecisionLogBacking.Record(evt);
			Log.Write("strategic",
				"decision tick=" + evt.WorldTick + " bot=" + bot?.Info?.Type + " " +
				"action=" + evt.ActionType + " status=" + evt.Status + " reason=" + evt.Reason + " " +
				"exception=" + ex.GetType().Name);
		}

		void RecordFailure(IBot bot)
		{
			var evt = new StrategicDecisionEvent(
				StrategicContract.SchemaVersion,
				GetWorldTick(),
				bot?.Info?.Type,
				StrategicActionType.NoOp,
				StrategicActionStatus.Failed,
				StrategicActionReason.PolicyError);
			DecisionLogBacking.Record(evt);
			Log.Write("strategic",
				"decision tick=" + evt.WorldTick + " bot=" + bot?.Info?.Type + " " +
				"action=" + evt.ActionType + " status=" + evt.Status + " reason=" + evt.Reason);
		}

		void RecordActionResult(IBot bot, StrategicActionType actionType, StrategicActionResult result, Exception ex)
		{
			var evt = new StrategicDecisionEvent(
				result.SchemaVersion,
				result.WorldTick,
				bot?.Info?.Type,
				actionType,
				result.Status,
				result.Reason,
				ex);
			DecisionLogBacking.Record(evt);

			// Diagnostic mirror: emit one line per decision to the
			// "strategic" log channel so matches and replays can be
			// inspected without re-running the policy. The line is
			// deliberately minimal and unsynchronized.
			var exceptionSuffix = ex == null ? string.Empty : " exception=" + ex.GetType().Name;
			Log.Write("strategic",
				"decision tick=" + result.WorldTick + " bot=" + bot?.Info?.Type + " " +
				"action=" + actionType + " status=" + result.Status + " reason=" + result.Reason + exceptionSuffix);
		}
	}
}
