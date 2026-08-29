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

using System.IO;
using NUnit.Framework;
using OpenRA.Network;
using OpenRA.Traits;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class OrderTest
	{
		static byte[] RoundTripOrder(byte[] bytes)
		{
			return Order.Deserialize(null, new BinaryReader(new MemoryStream(bytes))).Serialize();
		}

		static OrderManager NewOrderManager()
		{
			// EchoConnection keeps the OrderManager in-memory; tests do not need a real network.
			return new OrderManager(new EchoConnection());
		}

		[TestCase(TestName = "Order data persists over serialization (empty)")]
		public void SerializeEmpty()
		{
			var o = new Order().Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "Order data persists over serialization (unqueued)")]
		public void SerializeUnqueued()
		{
			var o = new Order("Test", null, false).Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "Order data persists over serialization (queued)")]
		public void SerializeQueued()
		{
			var o = new Order("Test", null, true).Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "Order data persists over serialization (pos target)")]
		public void SerializePos()
		{
			var o = new Order("Test", null, Target.FromPos(new WPos(int.MinValue, 0, int.MaxValue)), false).Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "Order data persists over serialization (invalid target)")]
		public void SerializeInvalid()
		{
			var o = new Order("Test", null, Target.Invalid, false).Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "Order data persists over serialization (extra fields)")]
		public void SerializeExtra()
		{
			var o = new Order("Test", null, Target.Invalid, true)
			{
				TargetString = "TargetString",
				ExtraLocation = new CPos(2047, 2047, 128),
				ExtraData = uint.MaxValue,
				IsImmediate = true,
			}.Serialize();
			Assert.That(RoundTripOrder(o), Is.EqualTo(o));
		}

		[TestCase(TestName = "OrderManager.ScheduledMatchTimeoutTick is null by default")]
		public void OrderManagerScheduledMatchTimeoutTickDefaultsToNull()
		{
			var om = NewOrderManager();
			Assert.That(om.ScheduledMatchTimeoutTick, Is.Null);
		}

		[TestCase(TestName = "OrderManager.TryScheduleMatchTimeout accepts the first positive target")]
		public void OrderManagerTryScheduleMatchTimeoutAcceptsFirstTarget()
		{
			var om = NewOrderManager();
			Assert.That(om.TryScheduleMatchTimeout(600), Is.True);
			Assert.That(om.ScheduledMatchTimeoutTick, Is.EqualTo(600));
		}

		[TestCase(TestName = "OrderManager.TryScheduleMatchTimeout rejects non-positive targets")]
		public void OrderManagerTryScheduleMatchTimeoutRejectsNonPositive()
		{
			var om = NewOrderManager();
			Assert.That(om.TryScheduleMatchTimeout(0), Is.False);
			Assert.That(om.TryScheduleMatchTimeout(-1), Is.False);
			Assert.That(om.TryScheduleMatchTimeout(int.MinValue), Is.False);
			Assert.That(om.ScheduledMatchTimeoutTick, Is.Null);
		}

		[TestCase(TestName = "OrderManager.TryScheduleMatchTimeout rejects duplicate registrations")]
		public void OrderManagerTryScheduleMatchTimeoutRejectsDuplicates()
		{
			var om = NewOrderManager();
			Assert.That(om.TryScheduleMatchTimeout(600), Is.True);
			Assert.That(om.TryScheduleMatchTimeout(900), Is.False);
			Assert.That(om.TryScheduleMatchTimeout(1), Is.False);
			Assert.That(om.ScheduledMatchTimeoutTick, Is.EqualTo(600));
		}

		[TestCase(TestName = "OrderManager state does not leak between OrderManager instances")]
		public void OrderManagerTryScheduleMatchTimeoutScopedToInstance()
		{
			var omA = NewOrderManager();
			omA.TryScheduleMatchTimeout(600);
			Assert.That(omA.ScheduledMatchTimeoutTick, Is.EqualTo(600));

			var omB = NewOrderManager();
			Assert.That(omB.ScheduledMatchTimeoutTick, Is.Null,
				"Each OrderManager must own its ScheduledMatchTimeoutTick; no cross-instance leakage.");
		}

		[TestCase(TestName = "OrderManager records matching replay sync evidence")]
		public void OrderManagerRecordsMatchingSyncEvidence()
		{
			using var om = new OrderManager(new EchoConnection());
			om.ReceiveSync((42, 1234, 0));
			om.ReceiveSync((42, 1234, 0));

			Assert.That(om.LastValidatedSyncFrame, Is.EqualTo(42));
			Assert.That(om.IsOutOfSync, Is.False);
		}

		[TestCase(TestName = "OrderManager preserves the first out-of-sync frame")]
		public void OrderManagerPreservesFirstOutOfSyncFrame()
		{
			using var om = new OrderManager(new EchoConnection());

			Assert.That(om.TryRecordOutOfSyncFrame(42), Is.True);
			Assert.That(om.TryRecordOutOfSyncFrame(84), Is.False);
			Assert.That(om.OutOfSyncFrame, Is.EqualTo(42));
			Assert.That(om.IsOutOfSync, Is.True);
		}

		[TestCase(TestName = "ScheduleMatchTimeout Order rejected when clientId is not zero")]
		public void ScheduleMatchTimeoutRejectedWhenClientIdIsNotZero()
		{
			var om = NewOrderManager();
			UnitOrders.ProcessOrder(om, world: null, clientId: 1, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "600" });
			Assert.That(om.ScheduledMatchTimeoutTick, Is.Null);
		}

		[TestCase(TestName = "ScheduleMatchTimeout Order accepted when clientId is zero and target is valid")]
		public void ScheduleMatchTimeoutAcceptedWhenClientIdIsZero()
		{
			var om = NewOrderManager();
			UnitOrders.ProcessOrder(om, world: null, clientId: 0, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "600" });
			Assert.That(om.ScheduledMatchTimeoutTick, Is.EqualTo(600));
		}

		[TestCase(TestName = "ScheduleMatchTimeout Order rejected for invalid or non-positive target strings")]
		public void ScheduleMatchTimeoutRejectedForInvalidTarget()
		{
			var om = NewOrderManager();
			UnitOrders.ProcessOrder(om, world: null, clientId: 0, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "0" });
			UnitOrders.ProcessOrder(om, world: null, clientId: 0, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "-1" });
			UnitOrders.ProcessOrder(om, world: null, clientId: 0, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "" });
			UnitOrders.ProcessOrder(om, world: null, clientId: 0, order: new Order("ScheduleMatchTimeout", null, false) { TargetString = "abc" });
			Assert.That(om.ScheduledMatchTimeoutTick, Is.Null);
		}

		[TestCase(TestName = "OrderManager.TryScheduleMatchEnd is positive, once-only, and instance scoped")]
		public void OrderManagerTryScheduleMatchEndContract()
		{
			var om = NewOrderManager();
			Assert.That(om.TryScheduleMatchEnd(75), Is.True);
			Assert.That(om.TryScheduleMatchEnd(150), Is.False);
			Assert.That(om.ScheduledMatchEndTick, Is.EqualTo(75));
			Assert.That(NewOrderManager().ScheduledMatchEndTick, Is.Null);
		}

		[TestCase(TestName = "ScheduleMatchEnd accepts only a valid server-dispatched target")]
		public void ScheduleMatchEndOrderValidation()
		{
			var om = NewOrderManager();
			UnitOrders.ProcessOrder(om, world: null, clientId: 1,
				order: new Order("ScheduleMatchEnd", null, false) { TargetString = "75" });
			UnitOrders.ProcessOrder(om, world: null, clientId: 0,
				order: new Order("ScheduleMatchEnd", null, false) { TargetString = "invalid" });
			Assert.That(om.ScheduledMatchEndTick, Is.Null);

			UnitOrders.ProcessOrder(om, world: null, clientId: 0,
				order: new Order("ScheduleMatchEnd", null, false) { TargetString = "75" });
			Assert.That(om.ScheduledMatchEndTick, Is.EqualTo(75));
		}
	}
}
