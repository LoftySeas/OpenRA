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

using NUnit.Framework;
using OpenRA.FileFormats;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class ReplayCompatibilityTest
	{
		[TestCase(false, null, null, false, false, false, ReplayCompatibilityStatus.MissingMetadata)]
		[TestCase(true, null, "ra", true, true, true, ReplayCompatibilityStatus.UnknownVersion)]
		[TestCase(true, "version", null, true, true, true, ReplayCompatibilityStatus.UnknownMod)]
		[TestCase(true, "version", "ra", false, false, false, ReplayCompatibilityStatus.UnavailableMod)]
		[TestCase(true, "version", "ra", true, false, true, ReplayCompatibilityStatus.IncompatibleVersion)]
		[TestCase(true, "version", "ra", true, true, false, ReplayCompatibilityStatus.UnavailableMap)]
		[TestCase(true, "version", "ra", true, true, true, ReplayCompatibilityStatus.Compatible)]
		public void CompatibilityClassificationIsDeterministic(
			bool hasMetadata,
			string version,
			string mod,
			bool modAvailable,
			bool versionCompatible,
			bool mapAvailable,
			ReplayCompatibilityStatus expected)
		{
			Assert.That(
				ReplayCompatibility.Classify(
					hasMetadata,
					version,
					mod,
					modAvailable,
					versionCompatible,
					mapAvailable),
				Is.EqualTo(expected));
		}
	}
}
