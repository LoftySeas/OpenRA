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
using OpenRA.FileFormats;

namespace OpenRA.Mods.Common.Widgets.Logic
{
	public static class ReplayUtils
	{
		[FluentReference]
		const string IncompatibleReplayTitle = "dialog-incompatible-replay.title";

		[FluentReference]
		const string IncompatibleReplayPrompt = "dialog-incompatible-replay.prompt";

		[FluentReference]
		const string IncompatibleReplayAccept = "dialog-incompatible-replay.confirm";

		[FluentReference]
		const string UnknownVersion = "dialog-incompatible-replay.prompt-unknown-version";

		[FluentReference]
		const string UnknownMod = "dialog-incompatible-replay.prompt-unknown-mod";

		[FluentReference("mod")]
		const string UnvailableMod = "dialog-incompatible-replay.prompt-unavailable-mod";

		[FluentReference("version")]
		const string IncompatibleVersion = "dialog-incompatible-replay.prompt-incompatible-version";

		[FluentReference("map")]
		const string UnvailableMap = "dialog-incompatible-replay.prompt-unavailable-map";

		static readonly Action DoNothing = () => { };

		public static bool PromptConfirmReplayCompatibility(ReplayMetadata replayMeta, ModData modData, Action onCancel = null)
		{
			onCancel ??= DoNothing;

			return ReplayCompatibility.Check(replayMeta, modData) switch
			{
				ReplayCompatibilityStatus.Compatible => true,
				ReplayCompatibilityStatus.MissingMetadata =>
					IncompatibleReplayDialog(modData, onCancel, IncompatibleReplayPrompt),
				ReplayCompatibilityStatus.UnknownVersion =>
					IncompatibleReplayDialog(modData, onCancel, UnknownVersion),
				ReplayCompatibilityStatus.UnknownMod =>
					IncompatibleReplayDialog(modData, onCancel, UnknownMod),
				ReplayCompatibilityStatus.UnavailableMod =>
					IncompatibleReplayDialog(modData, onCancel, UnvailableMod, "mod", replayMeta.GameInfo.Mod),
				ReplayCompatibilityStatus.IncompatibleVersion =>
					IncompatibleReplayDialog(modData, onCancel, IncompatibleVersion, "version", replayMeta.GameInfo.Version),
				ReplayCompatibilityStatus.UnavailableMap =>
					IncompatibleReplayDialog(modData, onCancel, UnvailableMap, "map", replayMeta.GameInfo.MapUid),
				_ => throw new InvalidOperationException("Unknown replay compatibility status."),
			};
		}

		static bool IncompatibleReplayDialog(ModData modData, Action onCancel, string text, params object[] args)
		{
			ConfirmationDialogs.ButtonPrompt(
				modData, IncompatibleReplayTitle, text, textArguments: args, onCancel: onCancel, cancelText: IncompatibleReplayAccept);
			return false;
		}
	}
}
