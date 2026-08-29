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

namespace OpenRA.FileFormats
{
	public enum ReplayCompatibilityStatus
	{
		Compatible,
		MissingMetadata,
		UnknownVersion,
		UnknownMod,
		UnavailableMod,
		IncompatibleVersion,
		UnavailableMap,
	}

	public static class ReplayCompatibility
	{
		public static ReplayCompatibilityStatus Check(ReplayMetadata replayMetadata, ModData modData)
		{
			if (replayMetadata == null)
				return Classify(false, null, null, false, false, false);

			var version = replayMetadata.GameInfo.Version;
			var mod = replayMetadata.GameInfo.Mod;
			var modAvailable = mod != null && Game.Mods.ContainsKey(mod);
			var versionCompatible = modAvailable && Game.Mods[mod].Metadata.Version == version;
			var mapAvailable = versionCompatible &&
				replayMetadata.GameInfo.GetMapPreview(modData).Status == MapStatus.Available;
			return Classify(true, version, mod, modAvailable, versionCompatible, mapAvailable);
		}

		internal static ReplayCompatibilityStatus Classify(
			bool hasMetadata,
			string version,
			string mod,
			bool modAvailable,
			bool versionCompatible,
			bool mapAvailable)
		{
			if (!hasMetadata)
				return ReplayCompatibilityStatus.MissingMetadata;
			if (version == null)
				return ReplayCompatibilityStatus.UnknownVersion;
			if (mod == null)
				return ReplayCompatibilityStatus.UnknownMod;
			if (!modAvailable)
				return ReplayCompatibilityStatus.UnavailableMod;
			if (!versionCompatible)
				return ReplayCompatibilityStatus.IncompatibleVersion;
			return mapAvailable ? ReplayCompatibilityStatus.Compatible : ReplayCompatibilityStatus.UnavailableMap;
		}
	}
}
