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

using OpenRA.Mods.Common.AI;

namespace OpenRA.Mods.AI
{
	/// <summary>
	/// M1 reference policy. Emits <see cref="StrategicActionType.Attack"/>
	/// when the available ground set is at or above the configured
	/// squad formation size and no active assault squad is in flight;
	/// otherwise emits <see cref="StrategicActionType.NoOp"/>. Pure
	/// function of the observation, no side effects, no random
	/// consumption. The decision threshold is taken from the
	/// configuration supplied at construction time so the policy
	/// stays consistent with the controller that will actually form
	/// the squad without smuggling the threshold through the
	/// observation struct.
	/// </summary>
	public sealed class RuleAttackPolicy : IStrategicPolicy
	{
		/// <summary>
		/// Configured assault squad formation size. Must match the
		/// <c>SquadManagerBotModule@strategic.SquadSize</c> field in
		/// the active mod so the rule policy and the controller agree
		/// on the formation threshold.
		/// </summary>
		public int SquadSize { get; }

		public RuleAttackPolicy(int squadSize)
		{
			SquadSize = squadSize;
		}

		public StrategicAction Decide(in StrategicObservation observation)
		{
			if (observation.SchemaVersion != StrategicContract.SchemaVersion)
				return new StrategicAction(observation.SchemaVersion, observation.WorldTick, StrategicActionType.NoOp);

			if (SquadSize > 0
				&& observation.AvailableGroundAttackUnits >= SquadSize
				&& observation.ActiveAssaultSquads == 0)
				return new StrategicAction(observation.SchemaVersion, observation.WorldTick, StrategicActionType.Attack);

			return new StrategicAction(observation.SchemaVersion, observation.WorldTick, StrategicActionType.NoOp);
		}
	}
}
