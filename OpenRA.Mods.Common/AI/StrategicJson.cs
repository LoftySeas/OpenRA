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

using System.Globalization;
using System.Text;

namespace OpenRA.Mods.Common.AI
{
	/// <summary>
	/// Hand-rolled JSON serializer for the M1 strategic contract.
	/// Uses the canonical property names and enum values declared
	/// by the schema. Awaits the post-M1 switch to a real JSON
	/// library; the contract tests pin the exact wire format.
	/// </summary>
	public static class StrategicJson
	{
		static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;

		public static string Serialize(StrategicObservation o)
		{
			var w = new StringBuilder();
			WriteStartObject(w);
			WriteProperty(w, "schemaVersion", o.SchemaVersion); w.Append(',');
			WriteIntProperty(w, "worldTick", o.WorldTick); w.Append(',');
			WriteProperty(w, "playerId", o.PlayerId); w.Append(',');
			WriteProperty(w, "modId", o.ModId); w.Append(',');
			WriteIntProperty(w, "credits", o.Credits); w.Append(',');
			WriteIntProperty(w, "availableGroundAttackUnits", o.AvailableGroundAttackUnits); w.Append(',');
			WriteIntProperty(w, "activeAssaultSquads", o.ActiveAssaultSquads);
			WriteEndObject(w);
			return w.ToString();
		}

		public static string Serialize(StrategicAction a)
		{
			var w = new StringBuilder();
			WriteStartObject(w);
			WriteProperty(w, "schemaVersion", a.SchemaVersion); w.Append(',');
			WriteIntProperty(w, "worldTick", a.WorldTick); w.Append(',');
			WriteProperty(w, "type", ActionTypeString(a.Type));
			WriteEndObject(w);
			return w.ToString();
		}

		public static string Serialize(StrategicActionResult r)
		{
			var w = new StringBuilder();
			WriteStartObject(w);
			WriteProperty(w, "schemaVersion", r.SchemaVersion); w.Append(',');
			WriteIntProperty(w, "worldTick", r.WorldTick); w.Append(',');
			WriteProperty(w, "actionType", ActionTypeString(r.ActionType)); w.Append(',');
			WriteProperty(w, "status", StatusString(r.Status)); w.Append(',');
			WriteProperty(w, "reason", ReasonString(r.Reason));
			WriteEndObject(w);
			return w.ToString();
		}

		public static string ActionTypeString(StrategicActionType t) => t switch
		{
			StrategicActionType.NoOp => "NO_OP",
			StrategicActionType.Attack => "ATTACK",
			_ => "NO_OP",
		};

		public static string StatusString(StrategicActionStatus s) => s switch
		{
			StrategicActionStatus.NoOp => "NO_OP",
			StrategicActionStatus.Executed => "EXECUTED",
			StrategicActionStatus.Rejected => "REJECTED",
			StrategicActionStatus.Failed => "FAILED",
			_ => "NO_OP",
		};

		public static string ReasonString(StrategicActionReason r) => r switch
		{
			StrategicActionReason.None => "NONE",
			StrategicActionReason.InsufficientUnits => "INSUFFICIENT_UNITS",
			StrategicActionReason.AttackAlreadyActive => "ATTACK_ALREADY_ACTIVE",
			StrategicActionReason.ExecutorUnavailable => "EXECUTOR_UNAVAILABLE",
			StrategicActionReason.InvalidAction => "INVALID_ACTION",
			StrategicActionReason.PolicyError => "POLICY_ERROR",
			_ => "NONE",
		};

		public static string StrategyControlString(StrategyControl c) => c switch
		{
			StrategyControl.Autonomous => "Autonomous",
			StrategyControl.External => "External",
			_ => "Autonomous",
		};

		static void WriteStartObject(StringBuilder w) => w.Append('{');

		static void WriteEndObject(StringBuilder w) => w.Append('}');

		static void WriteProperty(StringBuilder w, string name, string value)
		{
			w.Append('"').Append(name).Append("\":");
			WriteString(w, value);
		}

		static void WriteIntProperty(StringBuilder w, string name, int value)
		{
			w.Append('"').Append(name).Append("\":");
			w.Append(value.ToString(Invariant));
		}

		static void WriteString(StringBuilder w, string value)
		{
			w.Append('"');
			foreach (var c in value)
			{
				switch (c)
				{
					case '\\': w.Append("\\\\"); break;
					case '"': w.Append("\\\""); break;
					case '\b': w.Append("\\b"); break;
					case '\f': w.Append("\\f"); break;
					case '\n': w.Append("\\n"); break;
					case '\r': w.Append("\\r"); break;
					case '\t': w.Append("\\t"); break;
					default:
						if (c < 0x20)
							w.AppendFormat(Invariant, "\\u{0:x4}", (int)c);
						else
							w.Append(c);
						break;
				}
			}

			w.Append('"');
		}
	}
}
