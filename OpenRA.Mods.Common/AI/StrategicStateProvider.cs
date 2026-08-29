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
	/// Default read-only state provider for the M1 strategic loop.
	/// Captures the owning player's credits and obtains attack counts
	/// from the enabled <see cref="IBotAttackController"/> trait.
	/// Throws during capture if no enabled attack controller is found
	/// for the bot: M1 must not manufacture zero readiness for a
	/// missing controller.
	/// </summary>
	[Desc("Strategic AI state provider for the M1 rule coordinator.")]
	public sealed class StrategicStateProviderInfo : ConditionalTraitInfo
	{
		public override object Create(ActorInitializer init) { return new StrategicStateProvider(init.Self, this); }
	}

	public class StrategicStateProvider : ConditionalTrait<StrategicStateProviderInfo>, IStrategicStateProvider
	{
		readonly Actor self;

		public StrategicStateProvider(Actor self, StrategicStateProviderInfo info)
			: base(info)
		{
			this.self = self;
		}

		StrategicObservation IStrategicStateProvider.Capture(IBot bot)
		{
			ArgumentNullException.ThrowIfNull(bot);

			var player = bot.Player;
			if (player == null)
				throw new InvalidOperationException("Bot player is not activated.");

			var controller = FindEnabledAttackController(player);
			if (controller == null)
				throw new InvalidOperationException(
					$"StrategicAI player '{player.InternalName}' has no enabled IBotAttackController trait.");

			var readiness = controller.GetAttackReadiness();
			var credits = player.PlayerActor.TraitOrDefault<PlayerResources>()?.GetCashAndResources() ?? 0;

			// The observation carries only the seven schema-declared
			// properties. The policy threshold is sourced from
			// configuration (Info.SquadSize) so two observations
			// with identical JSON always produce identical actions.
			return new StrategicObservation(
				StrategicContract.SchemaVersion,
				self.World.WorldTick,
				player.InternalName,
				StrategicContract.ModId,
				credits,
				readiness.AvailableGroundAttackUnits,
				readiness.ActiveAssaultSquads);
		}

		// Production seam: select the unique enabled IBotAttackController
		// on the player's actor. The M1 player intentionally has two
		// SquadManagerBotModule instances (disabled Normal, enabled
		// External) implementing IBotAttackController, so a naive
		// "first match" would silently return the disabled trait.
		// Disabled state is read through the IDisabledTrait interface,
		// which all ConditionalTrait<TInfo> implementations satisfy.
		internal virtual IBotAttackController FindEnabledAttackController(Player player)
		{
			if (player?.PlayerActor == null)
				return null;

			return PickEnabledAttackController(player.PlayerActor.TraitsImplementing<IBotAttackController>());
		}

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
	}
}
