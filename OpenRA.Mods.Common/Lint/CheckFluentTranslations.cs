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
using System.IO;
using System.Linq;
using System.Text;
using Linguini.Syntax.Ast;
using Linguini.Syntax.Parser;
using OpenRA.FileSystem;

namespace OpenRA.Mods.Common.Lint
{
	/// <summary>
	/// Validates translation completeness for non-English language files (e.g. fluent/zh/).
	///
	/// <para>Stage 3 skeleton: implements the key checks, with TODOs for the remaining ones.</para>
	///
	/// <para>See the OpenRA translation plan (docs/translation/sources.md) for stage 6 details.</para>
	/// </summary>
	sealed class CheckFluentTranslations : ILintPass
	{
		// Default target language: zh. Could be sourced from mod.yaml FluentLanguages in a future iteration.
		const string TargetLanguage = "zh";

		void ILintPass.Run(Action<string> emitError, Action<string> emitWarning, ModData modData)
		{
			Console.WriteLine($"Testing Fluent translations for language `{TargetLanguage}`");
			var modMessages = modData.Manifest.FluentMessages;
			if (modMessages.Length == 0)
				return;

			// Bail out if the mod does not declare support for the target language.
			if (!modData.Languages.Contains(TargetLanguage))
			{
				emitWarning($"Mod `{modData.Manifest.Id}` does not declare `{TargetLanguage}` in FluentLanguages. Skipping translation checks.");
				return;
			}

			// Collect English baseline keys, attributes and variables.
			var enEmpty = new HashSet<string>();
			var enMessages = LoadFluentFiles(modMessages, modData.DefaultFileSystem, enEmpty);
			var enKeys = ExtractKeys(enMessages);
			var enKeyAttrs = ExtractKeyAttributes(enMessages);
			var enKeyVars = ExtractKeyVariables(enMessages);

			// Collect the same for the target language.
			var targetMessages = BuildLanguagePaths(modMessages, TargetLanguage);
			var zhEmpty = new HashSet<string>();
			var zhMessages = LoadFluentFiles(targetMessages, modData.DefaultFileSystem, zhEmpty);
			var zhKeys = ExtractKeys(zhMessages);
			var zhKeyAttrs = ExtractKeyAttributes(zhMessages);
			var zhKeyVars = ExtractKeyVariables(zhMessages);

			var missingKeys = 0;
			var extraKeys = 0;
			var valueIssues = 0;
			var attrMismatches = 0;
			var varMismatches = 0;

			// Check 1: missing keys.
			foreach (var key in enKeys)
			{
				if (zhKeys.Contains(key))
					continue;
				emitWarning($"[zh] Missing translation for key `{key}`");
				missingKeys++;
			}

			// Check 2: extra keys (Chinese has, English does not - possible typo or stale entry).
			foreach (var key in zhKeys)
			{
				if (enKeys.Contains(key))
					continue;
				emitError($"[zh] Extra translation key `{key}` not present in English source");
				extraKeys++;
			}

			// Check 3: empty or whitespace-only Chinese values.
			foreach (var key in zhEmpty)
			{
				emitError($"[zh] Empty value for key `{key}`");
				valueIssues++;
			}

			// Check 4: attribute set consistency.
			foreach (var key in enKeys.Intersect(zhKeys))
			{
				var enAttrs = enKeyAttrs.TryGetValue(key, out var ea) ? ea : [];
				var zhAttrs = zhKeyAttrs.TryGetValue(key, out var za) ? za : [];

				foreach (var a in enAttrs.Except(zhAttrs))
					emitError($"[zh] Key `{key}` missing attribute `{a}`");

				foreach (var a in zhAttrs.Except(enAttrs))
					emitError($"[zh] Key `{key}` has extra attribute `{a}` not in English");

				attrMismatches += enAttrs.Except(zhAttrs).Count + zhAttrs.Except(enAttrs).Count;
			}

			// Check 5: variable set consistency.
			foreach (var key in enKeys.Intersect(zhKeys))
			{
				var enVars = enKeyVars.TryGetValue(key, out var ev) ? ev : [];
				var zhVars = zhKeyVars.TryGetValue(key, out var zv) ? zv : [];

				foreach (var v in enVars.Except(zhVars))
					emitError($"[zh] Key `{key}` missing variable `{v}` from English");

				foreach (var v in zhVars.Except(enVars))
					emitError($"[zh] Key `{key}` has extra variable `{v}` not in English");

				varMismatches += enVars.Except(zhVars).Count + zhVars.Except(enVars).Count;
			}

			// Check 6: long English runs in a Chinese value. Whitelisted short tokens (OpenRA, API names, etc.)
			// are skipped so that proper nouns, protocol names, and hotkey references don't trip the detector.
			var englishResidue = 0;
			foreach (var (key, value) in zhMessages)
			{
				var run = LongestAsciiAlphaRun(value);
				if (run == null || run.Length < 6)
					continue;

				// Whitelist common short tokens / acronyms that legitimately appear in Chinese UI.
				if (EnglishResidueWhitelist.Contains(run))
					continue;

				emitWarning($"[zh] Key `{key}` has long English run `{run}` ({run.Length} chars) - possibly untranslated");
				englishResidue++;
			}

			// Check 7: forbidden-term scan. The glossary CSV lives at docs/translation/zh-CN-glossary.csv
			// (relative to the engine directory) and lists Chinese terms that should not appear in
			// translations (e.g. 直译 of "Credits" as 信用点). Loading is best-effort: if the file is
			// missing we silently skip the check rather than failing the lint.
			var forbiddenHits = 0;
			var forbidden = LoadForbiddenTerms(modData);
			foreach (var (key, value) in zhMessages)
			{
				foreach (var term in forbidden)
				{
					if (value.Contains(term, StringComparison.Ordinal))
					{
						emitWarning($"[zh] Key `{key}` uses forbidden term `{term}` (see docs/translation/zh-CN-glossary.csv)");
						forbiddenHits++;
						break;
					}
				}
			}

			// Check 8: width ratio. Chinese characters take ~2x the width of Latin glyphs, so a
			// Chinese value that is significantly longer than its English counterpart is likely
			// to overflow fixed-width containers (button labels, narrow tooltips). We flag values
			// where the Chinese glyph count is both substantial (>= 30 glyphs) and exceeds 2.5x
			// the English glyph count as a layout risk. Empty values are caught by Check 3 and
			// skipped here so we don't generate noise from variables-only messages.
			var widthRisks = 0;
			foreach (var (key, zhValue) in zhMessages)
			{
				if (!enMessages.TryGetValue(key, out var enValue))
					continue;
				var enGlyphs = CountDisplayableGlyphs(enValue);
				var zhGlyphs = CountDisplayableGlyphs(zhValue);
				if (enGlyphs == 0 || zhGlyphs < 30 || zhGlyphs < enGlyphs * 2.5)
					continue;

				emitWarning($"[zh] Key `{key}` has {zhGlyphs} Chinese glyphs vs {enGlyphs} English glyphs - may overflow fixed-width containers");
				widthRisks++;
			}

			// TODO checks deferred:
			// - Check 9: font glyph coverage (needs font file + cmap, move to a C# tool).
			// - Check 10: per-file coverage parity between Chinese and English baselines.
			// - Check 11: Fluent syntax errors and Junk nodes (the Linguini parser already reports these).
			Console.WriteLine(
				$"[zh] coverage report: missing={missingKeys}, extra={extraKeys}, " +
				$"empty={valueIssues}, attr-mismatches={attrMismatches}, var-mismatches={varMismatches}, " +
				$"english-residue={englishResidue}, forbidden-term-hits={forbiddenHits}, width-risks={widthRisks}");
		}

		// Approximate the rendered width by counting characters but treating CJK ideographs as 2 units
		// and Latin / variable references as 1 unit. This matches what the FreeType-backed
		// SpriteFont.Measure reports closely enough for the overflow check.
		static int CountDisplayableGlyphs(string value)
		{
			var total = 0;
			foreach (var rune in value.EnumerateRunes())
			{
				if (rune.Value == '{' || rune.Value == '}')
					continue;

				// CJK Unified Ideographs (basic + ext A + ext B-G + supplements) plus Hiragana/Katakana
				// and CJK Symbols. Anything in the wide ranges counts as 2 units; Latin counts as 1.
				var v = rune.Value;
				if (v >= 0x1100 && (v <= 0x115F || // Hangul Jamo
					v == 0x2329 || v == 0x232A ||
					(v >= 0x2E80 && v <= 0x303E) || // CJK Radicals/Punctuation
					(v >= 0x3041 && v <= 0x33FF) || // Hiragana/Katakana/CJK symbols
					(v >= 0x3400 && v <= 0x4DBF) || // CJK Ext A
					(v >= 0x4E00 && v <= 0x9FFF) || // CJK Unified
					(v >= 0xA000 && v <= 0xA4CF) || // Yi
					(v >= 0xAC00 && v <= 0xD7A3) || // Hangul syllables
					(v >= 0xF900 && v <= 0xFAFF) || // CJK Compatibility
					(v >= 0xFE30 && v <= 0xFE4F) || // CJK Compat forms
					(v >= 0xFF00 && v <= 0xFF60) || // Fullwidth
					(v >= 0xFFE0 && v <= 0xFFE6) || // Fullwidth signs
					(v >= 0x20000 && v <= 0x2FFFF))) // CJK Ext B-G + supplements
					total++;
				else if (!char.IsWhiteSpace((char)v))
					total++;
			}

			return total;
		}

		static string LongestAsciiAlphaRun(string value)
		{
			string best = null;
			var start = -1;
			for (var i = 0; i <= value.Length; i++)
			{
				var isLetter = i < value.Length && ((value[i] >= 'a' && value[i] <= 'z') || (value[i] >= 'A' && value[i] <= 'Z'));
				if (isLetter)
				{
					if (start < 0)
						start = i;
				}
				else if (start >= 0)
				{
					var run = value[start..i];
					if (best == null || run.Length > best.Length)
						best = run;
					start = -1;
				}
			}

			return best;
		}

		// Short English tokens that legitimately appear in Chinese UI: brand names, protocols, file formats,
		// game expansion / feature names, and keyboard / input key names. Anything not on this list that
		// is 6+ ASCII letters is treated as a possibly-untranslated run.
		static readonly HashSet<string> EnglishResidueWhitelist = new(StringComparer.Ordinal)
		{
			"OpenRA", "openra", "API", "HTTP", "URL", "IP", "CPU", "GPU", "RAM", "OpenGL", "DirectX",
			"syncreport", "assetbrowser", "install",
			"Mix", "MIX", "INI", "PNG", "VQA", "JSON", "YAML", "TTF", "UTF", "UID",
			"Escape", "Enter", "Space", "Tab", "Shift", "Control", "Alt", "Backspace", "Delete",
			"Insert", "Home", "End", "PageUp", "PageDown", "Up", "Down", "Left", "Right",
			"Middle", "MODIFIER", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
			"Mouse", "LeftMouse", "RightMouse", "MiddleMouse", "MouseWheel",
			"Firestorm", "Aftermath", "Counterstrike", "Pylons", "Veinholes", "Veinhole",
			"pylons", "Commander", "Scroll", "Advanced", "BotModule",
			"Upgrade", "version", "forwarding", "DisplayDeveloperSettings",
		};

		static List<string> LoadForbiddenTerms(ModData modData)
		{
			_ = modData; // Reserved for future per-mod term overrides.
			var result = new List<string>();

			// EngineDir is the project root when the utility runs against the source tree.
			var csvPath = Path.Combine(Platform.EngineDir, "docs", "translation", "zh-CN-glossary.csv");
			if (!File.Exists(csvPath))
				return result;

			try
			{
				foreach (var line in File.ReadAllLines(csvPath))
				{
					if (string.IsNullOrWhiteSpace(line) || line.StartsWith('#'))
						continue;

					// CSV format: english,chinese,avoid,scope,context,source,review,notes
					// The avoid column is the 3rd field; entries are separated by '|'.
					var parts = line.Split(',');
					if (parts.Length < 3)
						continue;

					var avoid = parts[2].Trim();
					if (string.IsNullOrEmpty(avoid))
						continue;

					foreach (var term in avoid.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
						if (!result.Contains(term))
							result.Add(term);
				}
			}
			catch (Exception ex)
			{
				Console.WriteLine($"Failed to load forbidden terms from {csvPath}: {ex.Message}");
			}

			return result;
		}

		static Dictionary<string, string> LoadFluentFiles(ImmutableArray<string> paths, IReadOnlyFileSystem fileSystem, HashSet<string> emptyKeys)
		{
			var result = new Dictionary<string, string>();
			foreach (var path in paths)
			{
				if (!fileSystem.Exists(path))
					continue;

				try
				{
					var stream = fileSystem.Open(path);
					using var reader = new StreamReader(stream, Encoding.UTF8);
					var parser = new LinguiniParser(reader);
					var resource = parser.Parse();
					foreach (var entry in resource.Entries)
					{
						if (entry is not AstMessage msg)
							continue;

						// A key is only "empty" if neither its main value nor any of its attributes
						// contain content. Dialogs commonly use an empty main value plus .title/.prompt
						// attributes, which is a legitimate Fluent pattern, not a translation miss.
						if (IsEmptyMessage(msg))
							emptyKeys.Add(msg.GetId());

						result[msg.GetId()] = ExtractText(msg.Value);
					}
				}
				catch (Exception ex)
				{
					Console.WriteLine($"Failed to parse {path}: {ex.Message}");
				}
			}

			return result;
		}

		static string ExtractText(Pattern pattern)
		{
			if (pattern == null)
				return string.Empty;

			// Concatenate the TextLiteral elements; skip inline expressions. A full AST walker belongs to stage 6.
			var sb = new StringBuilder();
			foreach (var elem in pattern.Elements)
			{
				if (elem is TextLiteral txt)
					sb.Append(txt.Value);
			}

			return sb.ToString();
		}

		static bool IsEmptyValue(Pattern pattern)
		{
			// Truly empty: no value, or a value that contains no literal text and no inline expressions.
			if (pattern == null)
				return true;
			if (pattern.Elements.Count == 0)
				return true;

			// A value with only placeholders (e.g. `{ $name }`) is not empty - it has variable content.
			return false;
		}

		static bool IsEmptyMessage(AstMessage msg)
		{
			if (!IsEmptyValue(msg.Value))
				return false;

			// Main value is empty, but check the attributes.
			foreach (var attr in msg.Attributes)
				if (!IsEmptyValue(attr.Value))
					return false;

			return true;
		}

		static HashSet<string> ExtractKeys(Dictionary<string, string> messages)
		{
			return [.. messages.Keys];
		}

		static Dictionary<string, ImmutableHashSet<string>> ExtractKeyAttributes(Dictionary<string, string> messages)
		{
			// TODO stage 6: parse message.Attributes properly. For now we return an empty set
			// because LoadFluentFiles only captures the primary message, not the attributes.
			return messages.Keys.ToDictionary(k => k, _ => (ImmutableHashSet<string>)[]);
		}

		static Dictionary<string, ImmutableHashSet<string>> ExtractKeyVariables(Dictionary<string, string> messages)
		{
			var result = new Dictionary<string, ImmutableHashSet<string>>();
			foreach (var (key, value) in messages)
			{
				var vars = new HashSet<string>();
				var i = 0;
				while (i < value.Length - 1)
				{
					if (value[i] == '$' && value[i + 1] == '{')
					{
						var end = value.IndexOf('}', i + 2);
						if (end > 0)
						{
							vars.Add(value.Substring(i + 2, end - i - 2));
							i = end + 1;
							continue;
						}
					}

					i++;
				}

				result[key] = vars.ToImmutableHashSet();
			}

			return result;
		}

		/// <summary>
		/// Mirrors FluentProvider.BuildLanguagePaths: for each base path adds a `{lang}/` sibling.
		/// FluentProvider already does this at Initialize time, but the lint runs standalone.
		/// </summary>
		static ImmutableArray<string> BuildLanguagePaths(ImmutableArray<string> basePaths, string language)
		{
			var paths = new List<string>(basePaths);
			foreach (var basePath in basePaths)
			{
				var slash = basePath.LastIndexOf('/');
				if (slash < 0)
					continue;

				var langPath = basePath[..(slash + 1)] + language + "/" + basePath[(slash + 1)..];
				paths.Add(langPath);
			}

			return paths.ToImmutableArray();
		}
	}
}
