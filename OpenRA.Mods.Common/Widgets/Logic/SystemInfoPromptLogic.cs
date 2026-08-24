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
using System.Globalization;
using System.Linq;
using OpenRA.Widgets;

namespace OpenRA.Mods.Common.Widgets.Logic
{
	public class SystemInfoPromptLogic : ChromeLogic
	{
		// Increment the version number when adding new stats
		const int SystemInformationVersion = 6;

		[FluentReference]
		const string LabelAnonymousId = "label-system-info-anonymous-id";
		[FluentReference]
		const string LabelOsType = "label-system-info-os-type";
		[FluentReference]
		const string LabelOsVersion = "label-system-info-os-version";
		[FluentReference]
		const string LabelArchitecture = "label-system-info-architecture";
		[FluentReference]
		const string LabelDotnetRuntime = "label-system-info-dotnet-runtime";
		[FluentReference]
		const string LabelOpenglVersion = "label-system-info-opengl-version";
		[FluentReference]
		const string LabelWindowSize = "label-system-info-window-size";
		[FluentReference]
		const string LabelWindowScale = "label-system-info-window-scale";
		[FluentReference]
		const string LabelUiScale = "label-system-info-ui-scale";
		[FluentReference]
		const string LabelSystemLanguage = "label-system-info-system-language";

		static Dictionary<string, (string Label, string Value)> GetSystemInformation()
		{
			return new Dictionary<string, (string, string)>
			{
				{ "id", (FluentProvider.GetMessage(LabelAnonymousId), Game.Settings.Debug.UUID) },
				{ "platform", (FluentProvider.GetMessage(LabelOsType), Platform.CurrentPlatform.ToString()) },
				{ "os", (FluentProvider.GetMessage(LabelOsVersion), Platform.OperatingSystem) },
				{ "arch", (FluentProvider.GetMessage(LabelArchitecture), Platform.CurrentArchitecture.ToString()) },
				{ "runtime", (FluentProvider.GetMessage(LabelDotnetRuntime), Platform.RuntimeVersion) },
				{ "gl", (FluentProvider.GetMessage(LabelOpenglVersion), Game.Renderer.GLVersion) },
				{ "windowsize", (FluentProvider.GetMessage(LabelWindowSize), $"{Game.Renderer.NativeResolution.Width}x{Game.Renderer.NativeResolution.Height}") },
				{ "windowscale", (FluentProvider.GetMessage(LabelWindowScale), Game.Renderer.NativeWindowScale.ToString("F2", CultureInfo.InvariantCulture)) },
				{ "uiscale", (FluentProvider.GetMessage(LabelUiScale), Game.Settings.Graphics.UIScale.ToString("F2", CultureInfo.InvariantCulture)) },
				{ "lang", (FluentProvider.GetMessage(LabelSystemLanguage), CultureInfo.InstalledUICulture.TwoLetterISOLanguageName) }
			};
		}

		public static bool ShouldShowPrompt()
		{
			return Game.Settings.Debug.SystemInformationVersionPrompt < SystemInformationVersion;
		}

		public static string CreateParameterString()
		{
			if (!Game.Settings.Debug.SendSystemInformation)
				return "";

			return $"&sysinfoversion={SystemInformationVersion}&"
				+ GetSystemInformation()
					.Select(kv => kv.Key + "=" + Uri.EscapeDataString(kv.Value.Value))
					.JoinWith("&");
		}

		[ObjectCreator.UseCtor]
		public SystemInfoPromptLogic(Widget widget, Action onComplete)
		{
			var sysInfoCheckbox = widget.Get<CheckboxWidget>("SYSINFO_CHECKBOX");
			sysInfoCheckbox.IsChecked = () => Game.Settings.Debug.SendSystemInformation;
			sysInfoCheckbox.OnClick = () => Game.Settings.Debug.SendSystemInformation ^= true;

			var sysInfoData = widget.Get<ScrollPanelWidget>("SYSINFO_DATA");
			var template = sysInfoData.Get<LabelWidget>("DATA_TEMPLATE");
			sysInfoData.RemoveChildren();

			foreach (var (name, value) in GetSystemInformation().Values)
			{
				var label = template.Clone();
				var text = name + ": " + value;
				label.GetText = () => text;
				sysInfoData.AddChild(label);
			}

			widget.Get<ButtonWidget>("CONTINUE_BUTTON").OnClick = () =>
			{
				Game.Settings.Debug.SystemInformationVersionPrompt = SystemInformationVersion;
				Game.Settings.Save();
				Ui.CloseWindow();
				onComplete();
			};
		}
	}
}
