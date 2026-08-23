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

			// TODO checks for stage 6:
			// - Check 6: long English runs in a Chinese value (whitelist: proper nouns, protocols, hotkeys).
			// - Check 7: forbidden-term scan (read the `avoid` column from docs/translation/zh-CN-glossary.csv).
			// - Check 8: font glyph coverage (needs font file + cmap, move to a C# tool).
			// - Check 9: per-file coverage parity between Chinese and English baselines.
			// - Check 10: Fluent syntax errors and Junk nodes (the Linguini parser already reports these).
			Console.WriteLine(
				$"[zh] coverage report: missing={missingKeys}, extra={extraKeys}, " +
				$"empty={valueIssues}, attr-mismatches={attrMismatches}, var-mismatches={varMismatches}");
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
