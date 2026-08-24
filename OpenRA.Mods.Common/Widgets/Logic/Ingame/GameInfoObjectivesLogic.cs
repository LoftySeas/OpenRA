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

using System.Linq;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.Common.Widgets.Logic
{
	sealed class GameInfoObjectivesLogic : ChromeLogic
	{
		[FluentReference]
		const string InProgress = "label-mission-in-progress";

		[FluentReference]
		const string Accomplished = "label-mission-accomplished";

		[FluentReference]
		const string Failed = "label-mission-failed";

		readonly ContainerWidget template;

		[ObjectCreator.UseCtor]
		public GameInfoObjectivesLogic(Widget widget, World world)
		{
			var player = world.RenderPlayer ?? world.LocalPlayer;

			var objectivesPanel = widget.Get<ScrollPanelWidget>("OBJECTIVES_PANEL");
			template = objectivesPanel.Get<ContainerWidget>("OBJECTIVE_TEMPLATE");

			if (player == null)
			{
				objectivesPanel.RemoveChildren();
				return;
			}

			var mo = player.PlayerActor.TraitOrDefault<MissionObjectives>();
			if (mo == null)
			{
				objectivesPanel.RemoveChildren();
				return;
			}

			var missionStatus = widget.Get<LabelWidget>("MISSION_STATUS");
			var inProgress = FluentProvider.GetMessage(InProgress);
			var accomplished = FluentProvider.GetMessage(Accomplished);
			var failed = FluentProvider.GetMessage(Failed);
			missionStatus.GetText = () => player.WinState == WinState.Undefined ? inProgress :
				player.WinState == WinState.Won ? accomplished : failed;
			missionStatus.GetColor = () => player.WinState == WinState.Undefined ? Color.White :
				player.WinState == WinState.Won ? Color.LimeGreen : Color.Red;

			PopulateObjectivesList(mo, objectivesPanel, template);

			void RedrawObjectives(Player p, bool _)
			{
				if (p == player)
					PopulateObjectivesList(mo, objectivesPanel, template);
			}

			mo.ObjectiveAdded += RedrawObjectives;
		}

		static void PopulateObjectivesList(MissionObjectives mo, ScrollPanelWidget parent, ContainerWidget template)
		{
			parent.RemoveChildren();

			foreach (var objective in mo.Objectives.OrderBy(o => o.Type))
			{
				var widget = template.Clone();
				var label = widget.Get<LabelWidget>("OBJECTIVE_TYPE");

				// The Type is the literal "Primary"/"Secondary" string - the fluent file ships it
				// lowercase ("primary" / "secondary"), so look up the lowercased value. The raw
				// string is shown as a fallback if the translation is missing.
				label.GetText = () => FluentProvider.GetMessage(objective.Type.ToLowerInvariant());

				var checkbox = widget.Get<CheckboxWidget>("OBJECTIVE_STATUS");
				checkbox.IsChecked = () => objective.State != ObjectiveState.Incomplete;
				checkbox.GetCheckmark = () => objective.State == ObjectiveState.Completed ? "tick" : "cross";

				// The Description is the fluent key the mission script passed to AddObjective
				// (e.g. "find-einstein"). Resolve it through the fluent bundle so the panel shows
				// the localized text, not the raw key.
				checkbox.GetText = () => FluentProvider.GetMessage(objective.Description);

				parent.AddChild(widget);
			}
		}
	}
}
