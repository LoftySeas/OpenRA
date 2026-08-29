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
using System.IO;
using System.Security.Cryptography;
using System.Text;
using OpenRA.FileFormats;
using OpenRA.Network;

namespace OpenRA
{
	static class AutomatedMatchEvidence
	{
		public static string OrderStreamSha256(string replayPath, int? maxExclusiveFrame = null)
		{
			var recordedOrders = new List<(int Frame, int Client, byte[] Data)>();
			using var stream = File.OpenRead(replayPath);
			using var reader = new BinaryReader(stream, Encoding.UTF8, leaveOpen: true);
			while (stream.Position < stream.Length)
			{
				if (stream.Length - stream.Position < sizeof(int))
					throw new InvalidDataException("Replay order stream has a truncated client id.");

				var client = reader.ReadInt32();
				if (client == ReplayMetadata.MetaStartMarker)
					break;

				if (stream.Length - stream.Position < sizeof(int))
					throw new InvalidDataException("Replay order stream has a truncated packet length.");

				var length = reader.ReadInt32();
				if (length < sizeof(int) || length > stream.Length - stream.Position)
					throw new InvalidDataException("Replay order stream has an invalid packet length.");

				var packet = reader.ReadBytes(length);
				var frame = BitConverter.ToInt32(packet, 0);
				if (frame > 0 && maxExclusiveFrame.HasValue && frame >= maxExclusiveFrame.Value)
					continue;
				if (frame == 0)
				{
					if (OrderIO.TryParseOrderPacket(packet, out var orders))
					{
						foreach (var order in orders.Orders.GetOrders(null))
						{
							if (order.OrderString != "ScheduleMatchTimeout")
								continue;

							var canonical = Encoding.UTF8.GetBytes(
								$"{client}\n{order.OrderString}\n{order.TargetString}\n");
							recordedOrders.Add((frame, client, canonical));
						}
					}

					continue;
				}

				if (OrderIO.TryParseOrderPacket(packet, out _) && packet.Length > sizeof(int))
					recordedOrders.Add((frame, client, packet[sizeof(int)..]));
			}

			recordedOrders.Sort((a, b) =>
			{
				var frameComparison = a.Frame.CompareTo(b.Frame);
				if (frameComparison != 0)
					return frameComparison;

				var clientComparison = a.Client.CompareTo(b.Client);
				if (clientComparison != 0)
					return clientComparison;

				return a.Data.AsSpan().SequenceCompareTo(b.Data);
			});

			using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
			foreach (var (frame, client, data) in recordedOrders)
			{
				hash.AppendData(BitConverter.GetBytes(frame));
				hash.AppendData(BitConverter.GetBytes(client));
				hash.AppendData(BitConverter.GetBytes(data.Length));
				hash.AppendData(data);
			}

			return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
		}

		public static string StrategicDecisionSha256(string logPath)
		{
			using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
			if (File.Exists(logPath))
			{
				using var stream = new FileStream(
					logPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
				using var reader = new StreamReader(stream, Encoding.UTF8);
				while (reader.ReadLine() is { } rawLine)
				{
					var timestampEnd = rawLine.IndexOf("] ", StringComparison.Ordinal);
					var line = timestampEnd >= 0 ? rawLine[(timestampEnd + 2)..] : rawLine;
					if (!line.StartsWith("decision ", StringComparison.Ordinal) &&
						!line.StartsWith("init-failure ", StringComparison.Ordinal))
						continue;

					hash.AppendData(Encoding.UTF8.GetBytes(line + "\n"));
				}
			}

			return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
		}
	}
}
