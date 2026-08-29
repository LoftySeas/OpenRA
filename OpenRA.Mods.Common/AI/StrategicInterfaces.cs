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

using OpenRA.Traits;

namespace OpenRA.Mods.Common.AI
{
	/// <summary>
	/// Captures a single immutable observation for the owning bot at the
	/// current world tick. The state provider must be side-effect free:
	/// no orders, no trait mutation, no random consumption, no retained
	/// mutable Actor references.
	/// </summary>
	[RequireExplicitImplementation]
	public interface IStrategicStateProvider
	{
		StrategicObservation Capture(IBot bot);
	}

	/// <summary>
	/// Produces exactly one action for a captured observation. M1 policies
	/// are deterministic for a fixed observation and must not throw on
	/// any valid input.
	/// </summary>
	[RequireExplicitImplementation]
	public interface IStrategicPolicy
	{
		StrategicAction Decide(in StrategicObservation observation);
	}

	/// <summary>
	/// Executes a single validated action. The executor is responsible
	/// for rejecting actions whose schema version or world tick does not
	/// match the observation that produced them.
	/// </summary>
	[RequireExplicitImplementation]
	public interface IStrategicActionExecutor
	{
		StrategicActionResult Execute(IBot bot, in StrategicAction action);
	}

	/// <summary>
	/// Adapter interface implemented by the bot module that owns squad
	/// creation. The state provider reads readiness from this controller
	/// so that observation and execution use the same eligibility rules.
	/// </summary>
	[RequireExplicitImplementation]
	public interface IBotAttackController
	{
		BotAttackReadiness GetAttackReadiness();

		StrategicActionResult RequestAttack(IBot bot, in StrategicAction action);
	}
}
