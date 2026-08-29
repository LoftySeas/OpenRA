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
using System.Threading;
using OpenRA.Mods.Common.AI;

namespace OpenRA.Mods.AI
{
	/// <summary>
	/// One unsynchronized diagnostic record per decision. The event
	/// is the smallest amount of context the M1 quality gate
	/// requires: contract version, world tick, action, result and
	/// (when relevant) a bounded exception message. The record is
	/// never used as a synchronized game input.
	/// </summary>
	public sealed class StrategicDecisionLog
	{
		readonly Lock syncRoot = new();
		readonly List<StrategicDecisionEvent> events = [];

		public IReadOnlyList<StrategicDecisionEvent> Events
		{
			get
			{
				lock (syncRoot)
					return events.ToArray();
			}
		}

		public void Record(StrategicDecisionEvent decision)
		{
			lock (syncRoot)
				events.Add(decision);
		}

		public void Clear()
		{
			lock (syncRoot)
				events.Clear();
		}
	}

	public sealed class StrategicDecisionEvent
	{
		public string SchemaVersion { get; }
		public int WorldTick { get; }
		public string BotType { get; }
		public StrategicActionType ActionType { get; }
		public StrategicActionStatus Status { get; }
		public StrategicActionReason Reason { get; }
		public string ExceptionType { get; }
		public string ExceptionMessage { get; }

		public StrategicDecisionEvent(
			string schemaVersion,
			int worldTick,
			string botType,
			StrategicActionType actionType,
			StrategicActionStatus status,
			StrategicActionReason reason,
			Exception exception = null)
		{
			SchemaVersion = schemaVersion;
			WorldTick = worldTick;
			BotType = botType;
			ActionType = actionType;
			Status = status;
			Reason = reason;
			ExceptionType = exception?.GetType().FullName;
			ExceptionMessage = exception?.Message;
		}
	}
}
