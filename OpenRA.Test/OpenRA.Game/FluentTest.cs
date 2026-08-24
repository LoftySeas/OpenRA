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
using System.Collections.Frozen;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using NUnit.Framework;
using OpenRA.FileSystem;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class FluentTest
	{
		readonly string pluralForms = @"
label-players = {$player ->
    [one] One player
   *[other] {$player} players
}
";

		[TestCase(TestName = "Fluent Plural Terms")]
		public void TestOne()
		{
			var bundle = new FluentBundle("en", pluralForms, e => Console.WriteLine(e.Message));
			var label = bundle.GetMessage("label-players", ["player", 1]);
			Assert.That("One player", Is.EqualTo(label));
			label = bundle.GetMessage("label-players", ["player", 2]);
			Assert.That("2 players", Is.EqualTo(label));
		}

		// In-memory IReadOnlyFileSystem used by the BuildLanguagePaths regression tests.
		// Only Exists is meaningful for the tested code path; the other members are stubbed.
		sealed class FakeFileSystem : IReadOnlyFileSystem
		{
			readonly FrozenSet<string> existing;
			public FakeFileSystem(IEnumerable<string> existing) { this.existing = existing.ToFrozenSet(); }
			public bool Exists(string filename) => existing.Contains(filename);
			public Stream Open(string filename) => throw new NotSupportedException();
			public bool TryGetPackageContaining(string path, out IReadOnlyPackage package, out string filename)
			{ package = null; filename = null; return false; }
			public bool TryOpen(string filename, out Stream s) { s = null; return false; }
			public bool IsExternalFile(string filename) => false;
		}

		// Regression: a map-level `map.ftl` must pick up the sibling `zh/map.ftl` when present.
		// Before the fix, the `slash < 0` branch returned early and the language variant was
		// never added to the bundle's path list, so campaign briefings always showed English.
		[TestCase(TestName = "BuildLanguagePaths picks up zh/map.ftl sibling for root-level map.ftl")]
		public void BuildLanguagePaths_PicksUpSiblingForRootMapFtl()
		{
			var fs = new FakeFileSystem(["map.ftl", "zh/map.ftl"]);
			var basePaths = ImmutableArray.Create("map.ftl");
			var paths = FluentProvider.BuildLanguagePaths(basePaths, fs, "zh");

			Assert.That(paths, Does.Contain("map.ftl"), "English base path should be retained");
			Assert.That(paths, Does.Contain("zh/map.ftl"), "zh sibling of root-level map.ftl must be added");
		}

		// English (en) must short-circuit and return the base paths unchanged - the original
		// behaviour; the new slash<0 branch only runs for non-English languages.
		[TestCase(TestName = "BuildLanguagePaths short-circuits for en")]
		public void BuildLanguagePaths_EnglishShortCircuits()
		{
			var fs = new FakeFileSystem(["map.ftl"]);
			var basePaths = ImmutableArray.Create("map.ftl");
			var paths = FluentProvider.BuildLanguagePaths(basePaths, fs, "en");

			Assert.That(paths, Is.EqualTo(basePaths), "en must return base paths unchanged");
		}

		// Mod-level paths (with `/` in the path) must still produce the same langPath they
		// always did - this guards against regressing the working case while fixing the broken one.
		[TestCase(TestName = "BuildLanguagePaths still handles parent/file.ftl -> parent/zh/file.ftl")]
		public void BuildLanguagePaths_ModLevelPathUnchanged()
		{
			var fs = new FakeFileSystem(["ra|fluent/ra.ftl", "ra|fluent/zh/ra.ftl"]);
			var basePaths = ImmutableArray.Create("ra|fluent/ra.ftl");
			var paths = FluentProvider.BuildLanguagePaths(basePaths, fs, "zh");

			Assert.That(paths, Does.Contain("ra|fluent/ra.ftl"));
			Assert.That(paths, Does.Contain("ra|fluent/zh/ra.ftl"));
		}

		// Mixed list: some paths are at the map's root (no slash) and some are mod-level. The
		// fix must handle both without losing either. Mirrors the real `FluentMessages:`
		// list in mods/ra/maps/allies-01/map.yaml.
		[TestCase(TestName = "BuildLanguagePaths handles mixed slash and no-slash paths")]
		public void BuildLanguagePaths_HandlesMixedPaths()
		{
			var fs = new FakeFileSystem([
				"ra|fluent/lua.ftl", "ra|fluent/zh/lua.ftl",
				"ra|fluent/campaign.ftl", "ra|fluent/zh/campaign.ftl",
				"map.ftl", "zh/map.ftl",
			]);
			var basePaths = ImmutableArray.Create("ra|fluent/lua.ftl", "ra|fluent/campaign.ftl", "map.ftl");
			var paths = FluentProvider.BuildLanguagePaths(basePaths, fs, "zh");

			Assert.That(paths, Does.Contain("ra|fluent/lua.ftl"));
			Assert.That(paths, Does.Contain("ra|fluent/zh/lua.ftl"));
			Assert.That(paths, Does.Contain("ra|fluent/campaign.ftl"));
			Assert.That(paths, Does.Contain("ra|fluent/zh/campaign.ftl"));
			Assert.That(paths, Does.Contain("map.ftl"));
			Assert.That(paths, Does.Contain("zh/map.ftl"));
		}

		// If the zh sibling does not exist on disk, the base path is still loaded - the
		// function only adds the language variant when it can be found, never replaces the
		// base. This matches the existing behaviour for mod-level paths.
		[TestCase(TestName = "BuildLanguagePaths silently drops missing zh sibling")]
		public void BuildLanguagePaths_MissingZhSiblingFallsBackToBase()
		{
			var fs = new FakeFileSystem(["map.ftl"]);   // no zh/map.ftl
			var basePaths = ImmutableArray.Create("map.ftl");
			var paths = FluentProvider.BuildLanguagePaths(basePaths, fs, "zh");

			Assert.That(paths, Is.EqualTo(basePaths), "Missing zh sibling must not produce a broken path entry");
		}
	}
}
