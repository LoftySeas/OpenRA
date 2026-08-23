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

using System.Collections.Frozen;
using System.Collections.Generic;

namespace OpenRA
{
	public class FontData
	{
		public readonly string Font;
		public readonly int Size;
		public readonly int Ascender;
	}

	public class Fonts : IGlobalModData
	{
		[FieldLoader.LoadUsing(nameof(LoadFonts))]
		public readonly FrozenDictionary<string, FontData> FontList;

		// Per-language font overrides. A mod can declare a `LanguageFonts:` block
		// alongside `Fonts:` to substitute CJK-capable fonts when the current
		// language would otherwise render missing-glyph boxes. The renderer reads
		// this when Game.Settings.Game.Language matches a key; entries missing from
		// the override fall back to the default FontList.
		[FieldLoader.LoadUsing(nameof(LoadLanguageFonts))]
		public readonly FrozenDictionary<string, FrozenDictionary<string, FontData>> LanguageFonts;

		static object LoadFonts(MiniYaml y)
		{
			var ret = new Dictionary<string, FontData>(y.Nodes.Length);
			foreach (var node in y.Nodes)
				ret.Add(node.Key, FieldLoader.Load<FontData>(node.Value));

			return ret.ToFrozenDictionary();
		}

		static object LoadLanguageFonts(MiniYaml y)
		{
			var ret = new Dictionary<string, FrozenDictionary<string, FontData>>(y.Nodes.Length);
			foreach (var langNode in y.Nodes)
			{
				var perLang = new Dictionary<string, FontData>(langNode.Value.Nodes.Length);
				foreach (var fontNode in langNode.Value.Nodes)
					perLang.Add(fontNode.Key, FieldLoader.Load<FontData>(fontNode.Value));

				ret.Add(langNode.Key, perLang.ToFrozenDictionary());
			}

			return ret.ToFrozenDictionary();
		}
	}
}
