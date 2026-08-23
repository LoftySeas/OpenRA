#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is made available to you under the terms
 * of the GNU General Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later version. For
 * more information, see COPYING.
 */
#endregion

using System;
using System.Linq;

namespace OpenRA.Mods.Common.UtilityCommands
{
	sealed class CheckLanguageResolution : IUtilityCommand
	{
		string IUtilityCommand.Name => "--check-language";

		bool IUtilityCommand.ValidateArguments(string[] args)
		{
			return args.Length >= 3;
		}

		[Desc("LANG", "KEY [KEY ...]", "Resolve each KEY against the mod's Fluent bundle for the given language and print the rendered text.")]
		void IUtilityCommand.Run(Utility utility, string[] args)
		{
			var language = args[1];
			var keys = args.Skip(2);

			var modData = utility.ModData;
			var manifest = modData.Manifest;

			if (!manifest.FluentLanguages.Contains(language))
			{
				Console.WriteLine($"Language `{language}` is not declared in mod `{manifest.Id}` FluentLanguages.");
				Console.WriteLine($"Declared: {string.Join(", ", manifest.FluentLanguages)}");
				Environment.Exit(1);
				return;
			}

			// Load the mod's Fluent bundle for the requested language. This is the same code path
			// the game uses at startup, so the smoke test reflects what the UI will actually see.
			FluentProvider.Initialize(manifest, modData.DefaultFileSystem, language);

			var failures = 0;
			foreach (var key in keys)
			{
				if (FluentProvider.TryGetMessage(key, out var message))
					Console.WriteLine($"OK  {language} {key} = {message}");
				else
				{
					Console.WriteLine($"ERR {language} {key} (not found)");
					failures++;
				}
			}

			Environment.Exit(failures == 0 ? 0 : 1);
		}
	}
}
