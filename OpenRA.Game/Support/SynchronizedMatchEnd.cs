#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is
 * made available to you under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at your option) any later
 * version. For more information, see COPYING.
 */
#endregion

namespace OpenRA
{
	static class SynchronizedMatchEnd
	{
		public static bool TryEnd(World world)
		{
			if (world == null || world.Type != WorldType.Regular || world.IsGameOver)
				return false;

			var target = world.OrderManager?.ScheduledMatchEndTick;
			if (target == null || world.WorldTick < target.Value)
				return false;

			world.EndGame();
			return true;
		}
	}
}
