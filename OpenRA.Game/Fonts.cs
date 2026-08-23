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

		static object LoadFonts(MiniYaml y)
		{
			var ret = new Dictionary<string, FontData>(y.Nodes.Length);
			foreach (var node in y.Nodes)
				ret.Add(node.Key, FieldLoader.Load<FontData>(node.Value));

			return ret.ToFrozenDictionary();
		}
	}

	// Per-language font overrides declared via the `LanguageFonts:` block in mod.yaml.
	// Each top-level key is a language code (e.g. "zh"); its value is a font-name -> FontData
	// map applied on top of the default `Fonts:` list at render time so CJK-capable fonts
	// can substitute for FreeSans when the current language has CJK glyphs the default
	// font cannot render.
	public class LanguageFonts : IGlobalModData
	{
		[FieldLoader.LoadUsing(nameof(LoadLanguageFonts))]
		public readonly FrozenDictionary<string, FrozenDictionary<string, FontData>> Overrides;

		public LanguageFonts() { Overrides = FrozenDictionary<string, FrozenDictionary<string, FontData>>.Empty; }

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
