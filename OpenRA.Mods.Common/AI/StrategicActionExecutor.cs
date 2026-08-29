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
using System.Collections.Generic;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.AI
{
	/// <summary>
	/// Validates schema version and world tick, then delegates
	/// <see cref="StrategicActionType.Attack"/> to the enabled
	/// <see cref="IBotAttackController"/>. <see cref="StrategicActionType.NoOp"/>
	/// is short-circuited to a <c>NoOp</c> result without touching the
	/// attack controller.
	/// </summary>
	[Desc("Strategic AI action executor for the M1 rule coordinator.")]
	public sealed class StrategicActionExecutorInfo : ConditionalTraitInfo
	{
		public override object Create(ActorInitializer init) { return new StrategicActionExecutor(init.Self, this); }
	}

	public class StrategicActionExecutor : ConditionalTrait<StrategicActionExecutorInfo>, IStrategicActionExecutor
	{
		readonly Actor self;

		public StrategicActionExecutor(Actor self, StrategicActionExecutorInfo info)
			: base(info)
		{
			this.self = self;
		}

		StrategicActionResult IStrategicActionExecutor.Execute(IBot bot, in StrategicAction action)
		{
			ArgumentNullException.ThrowIfNull(bot);

			if (action.SchemaVersion != StrategicContract.SchemaVersion)
				return InvalidVersionResult(in action);

			var currentTick = GetCurrentWorldTick();
			if (action.WorldTick != currentTick)
				return StaleTickResult(in action, currentTick);

			if (action.Type == StrategicActionType.NoOp)
				return new StrategicActionResult(
					action.SchemaVersion, action.WorldTick,
					StrategicActionType.NoOp,
					StrategicActionStatus.NoOp,
					StrategicActionReason.None);

			if (action.Type != StrategicActionType.Attack)
				return new StrategicActionResult(
					action.SchemaVersion, action.WorldTick,
					action.Type,
					StrategicActionStatus.Rejected,
					StrategicActionReason.InvalidAction);

			var controller = FindAttackController(bot);
			if (controller == null)
				return new StrategicActionResult(
					action.SchemaVersion, action.WorldTick,
					StrategicActionType.Attack,
					StrategicActionStatus.Rejected,
					StrategicActionReason.ExecutorUnavailable);

			return controller.RequestAttack(bot, in action);
		}

		// Production seam: pick the unique enabled IBotAttackController
		// on the bot's player actor. The M1 player intentionally has
		// two SquadManagerBotModule instances (a disabled Normal one
		// and an enabled External one), both of which implement
		// IBotAttackController, so TraitOrDefault<IBotAttackController>
		// would throw. Tests can override this to inject a recording
		// controller without constructing a real Player.
		internal virtual IBotAttackController FindAttackController(IBot bot)
		{
			if (bot?.Player?.PlayerActor == null)
				return null;

			return PickEnabledAttackController(bot.Player.PlayerActor.TraitsImplementing<IBotAttackController>());
		}

		// Production seam: read the current world tick for the stale
		// action check. The default reads from the owning Actor's
		// World; tests can override this to drive the executor
		// without a real World.
		internal virtual int GetCurrentWorldTick() => self.World.WorldTick;

		// Pure selection rule extracted so it can be unit-tested
		// without a real Player. Returns the unique enabled
		// controller, or null if zero or more than one enabled
		// implementation is present.
		internal static IBotAttackController PickEnabledAttackController(IEnumerable<IBotAttackController> candidates)
		{
			IBotAttackController enabled = null;
			var enabledCount = 0;
			foreach (var t in candidates)
			{
				if (t is IDisabledTrait d && d.IsTraitDisabled)
					continue;
				enabled = t;
				enabledCount++;
			}

			return enabledCount == 1 ? enabled : null;
		}

		static StrategicActionResult InvalidVersionResult(in StrategicAction action)
		{
			// Version mismatches are recorded against the action's
			// declared type. The schema only allows INVALID_ACTION
			// rejections for NO_OP or ATTACK; we keep the type as-is
			// so the rejection is auditable.
			return new StrategicActionResult(
				action.SchemaVersion, action.WorldTick,
				action.Type,
				StrategicActionStatus.Rejected,
				StrategicActionReason.InvalidAction);
		}

		static StrategicActionResult StaleTickResult(in StrategicAction action, int currentTick)
		{
			// Stale-tick actions are still rejected, but the recorded
			// worldTick is the current world tick so the result pair
			// remains consistent with the executor's world state.
			return new StrategicActionResult(
				action.SchemaVersion, currentTick,
				action.Type,
				StrategicActionStatus.Rejected,
				StrategicActionReason.InvalidAction);
		}
	}
}
