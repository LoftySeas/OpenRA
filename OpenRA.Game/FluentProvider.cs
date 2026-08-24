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
using System.Collections.Immutable;
using System.Text;
using System.Threading;
using OpenRA.FileSystem;

namespace OpenRA
{
	public static class FluentProvider
	{
		// Ensure thread-safety.
		static readonly Lock SyncObject = new();
		static FluentBundle modFluentBundle;
		static FluentBundle mapFluentBundle;

		public static void Initialize(Manifest manifest, IReadOnlyFileSystem fileSystem, string language = "en")
		{
			lock (SyncObject)
			{
				var basePaths = manifest.FluentMessages;
				var allPaths = BuildLanguagePaths(basePaths, fileSystem, language);
				modFluentBundle = new FluentBundle(language, allPaths, fileSystem);
				if (fileSystem is Map map && map.FluentMessageDefinitions != null)
				{
					var files = ImmutableArray<string>.Empty;
					if (map.FluentMessageDefinitions.Value != null)
						files = FieldLoader.GetValue<ImmutableArray<string>>("value", map.FluentMessageDefinitions.Value);

					string text = null;
					if (map.FluentMessageDefinitions.Nodes.Length > 0)
					{
						var builder = new StringBuilder();
						foreach (var node in map.FluentMessageDefinitions.Nodes)
							if (node.Key == "base64")
								builder.Append(Encoding.UTF8.GetString(Convert.FromBase64String(node.Value.Value)));

						text = builder.ToString();
					}

					mapFluentBundle = new FluentBundle(language, files, fileSystem, text);
				}
			}
		}

		// Visible to the test project so the campaign-briefing language-path regression test can
		// exercise this helper directly. The smoke-test paths in `OpenRA.Test` already reference
		// `OpenRA.Mods.Common` internals via its csproj's <ProjectReference> so no separate
		// InternalsVisibleTo entry is needed there.
		internal static ImmutableArray<string> BuildLanguagePaths(ImmutableArray<string> basePaths, IReadOnlyFileSystem fileSystem, string language)
		{
			if (language == "en")
				return basePaths;

			var paths = new List<string>(basePaths);
			foreach (var basePath in basePaths)
			{
				// Map-level `map.ftl` lives at the map's root (no `/` in the path) - the language
				// variant is a sibling directory: `zh/map.ftl`. Mod-level paths always have a `/`
				// after the package separator, so they go through the `parent/` branch as before.
				var slash = basePath.LastIndexOf('/');
				var langPath = slash < 0
					? language + "/" + basePath
					: basePath[..(slash + 1)] + language + "/" + basePath[(slash + 1)..];

				if (fileSystem.Exists(langPath))
					paths.Add(langPath);
			}

			return paths.ToImmutableArray();
		}

		public static string GetMessage(string key, params object[] args)
		{
			lock (SyncObject)
			{
				// By prioritizing mod-level fluent bundles we prevent maps from overwriting string keys. We do not want to
				// allow maps to change the UI nor any other strings not exposed to the map.
				if (modFluentBundle.TryGetMessage(key, out var message, args))
					return message;

				if (mapFluentBundle != null)
					return mapFluentBundle.GetMessage(key, args);

				return key;
			}
		}

		public static bool TryGetMessage(string key, out string message, params object[] args)
		{
			lock (SyncObject)
			{
				// By prioritizing mod-level bundle we prevent maps from overwriting string keys. We do not want to
				// allow maps to change the UI nor any other strings not exposed to the map.
				if (modFluentBundle.TryGetMessage(key, out message, args))
					return true;

				if (mapFluentBundle != null && mapFluentBundle.TryGetMessage(key, out message, args))
					return true;

				return false;
			}
		}

		/// <summary>Should only be used by <see cref="MapPreview"/>.</summary>
		internal static bool TryGetModMessage(string key, out string message, params object[] args)
		{
			lock (SyncObject)
			{
				return modFluentBundle.TryGetMessage(key, out message, args);
			}
		}
	}
}
