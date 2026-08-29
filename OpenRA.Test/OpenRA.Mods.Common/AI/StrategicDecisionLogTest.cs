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
using NUnit.Framework;
using OpenRA.Mods.AI;
using OpenRA.Mods.Common.AI;

namespace OpenRA.Test.OpenRA.Mods.AI
{
	[TestFixture]
	sealed class StrategicDecisionLogTest
	{
		[TestCase(TestName = "Records decision events with full context")]
		public void RecordsDecisionEvents()
		{
			var log = new StrategicDecisionLog();
			var evt = new StrategicDecisionEvent(
				"1.0.0", 750, "strategic",
				StrategicActionType.Attack,
				StrategicActionStatus.Executed,
				StrategicActionReason.None);

			log.Record(evt);

			Assert.That(log.Events, Has.Count.EqualTo(1));
			var recorded = log.Events[0];
			Assert.That(recorded.SchemaVersion, Is.EqualTo("1.0.0"));
			Assert.That(recorded.WorldTick, Is.EqualTo(750));
			Assert.That(recorded.BotType, Is.EqualTo("strategic"));
			Assert.That(recorded.ActionType, Is.EqualTo(StrategicActionType.Attack));
			Assert.That(recorded.Status, Is.EqualTo(StrategicActionStatus.Executed));
			Assert.That(recorded.Reason, Is.EqualTo(StrategicActionReason.None));
			Assert.That(recorded.ExceptionType, Is.Null);
			Assert.That(recorded.ExceptionMessage, Is.Null);
		}

		[TestCase(TestName = "Records exception type and message for contained failures")]
		public void RecordsExceptionContext()
		{
			var log = new StrategicDecisionLog();
			var ex = new InvalidOperationException("policy failed");

			log.Record(new StrategicDecisionEvent(
				"1.0.0", 750, "strategic",
				StrategicActionType.NoOp,
				StrategicActionStatus.Failed,
				StrategicActionReason.PolicyError,
				ex));

			var recorded = log.Events[0];
			Assert.That(recorded.ExceptionType, Is.EqualTo(typeof(InvalidOperationException).FullName));
			Assert.That(recorded.ExceptionMessage, Is.EqualTo("policy failed"));
		}

		[TestCase(TestName = "Clear removes all events")]
		public void ClearRemovesAllEvents()
		{
			var log = new StrategicDecisionLog();
			log.Record(new StrategicDecisionEvent(
				"1.0.0", 1, "strategic",
				StrategicActionType.NoOp,
				StrategicActionStatus.NoOp,
				StrategicActionReason.None));
			log.Clear();

			Assert.That(log.Events, Is.Empty);
		}
	}
}
