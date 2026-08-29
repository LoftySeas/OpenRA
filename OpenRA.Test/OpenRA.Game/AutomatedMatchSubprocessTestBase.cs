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
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using NUnit.Framework;
using NUnit.Framework.Interfaces;

namespace OpenRA.Test
{
	abstract class AutomatedMatchSubprocessTestBase
	{
		protected const string OptInEnvVar = "OPENRA_SUBPROCESS_TESTS";
		const string ContentEnvVar = "OPENRA_TEST_CONTENT_DIR";
		const string KeepArtifactsEnvVar = "OPENRA_SUBPROCESS_KEEP_ARTIFACTS";

		protected static readonly string EngineDir = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, ".."));
		protected static readonly string CanonicalSpecPath =
			Path.Combine(EngineDir, "docs", "ai", "examples", "automated-match.json");
		static readonly string OpenRaExecutable = Path.Combine(
			EngineDir,
			"bin",
			RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "OpenRA.exe" : "OpenRA");

		string contentDirectory;
		protected bool optIn;
		protected string tempRoot;
		protected string matchResultPath;

		[OneTimeSetUp]
		public void SubprocessFixtureOneTimeSetUp()
		{
			var value = Environment.GetEnvironmentVariable(OptInEnvVar);
			optIn = IsEnabled(value);
			if (!optIn)
			{
				Assert.Ignore($"Set {OptInEnvVar}=1 to enable real OpenRA.exe subprocess tests.");
				return;
			}

			if (!File.Exists(OpenRaExecutable))
				Assert.Ignore($"OpenRA executable not found at {OpenRaExecutable}. Build the game first.");
			if (!File.Exists(CanonicalSpecPath))
				Assert.Ignore($"Canonical automated-match specification not found at {CanonicalSpecPath}.");

			contentDirectory = ResolveContentDirectory();
			if (contentDirectory == null)
				Assert.Ignore(
					$"Red Alert content was not found. Set {ContentEnvVar} to a Content directory " +
					"containing ra/v2/allies.mix.");

			TestContext.Progress.WriteLine($"Automated-match subprocess content source: {contentDirectory}");
		}

		[SetUp]
		public void SubprocessFixtureSetUp()
		{
			if (!optIn)
				return;

			tempRoot = Path.Combine(Path.GetTempPath(), "OpenRA-AutomatedMatch-" + Guid.NewGuid().ToString("N"));
			Directory.CreateDirectory(tempRoot);
			matchResultPath = Path.Combine(tempRoot, "match-result.json");
		}

		[TearDown]
		public void SubprocessFixtureTearDown()
		{
			if (!optIn || string.IsNullOrEmpty(tempRoot) || !Directory.Exists(tempRoot))
				return;

			var keepArtifacts = IsEnabled(Environment.GetEnvironmentVariable(KeepArtifactsEnvVar));
			var failed = TestContext.CurrentContext.Result.Outcome.Status == TestStatus.Failed;
			if (keepArtifacts || failed)
			{
				TestContext.Progress.WriteLine($"Automated-match subprocess artifacts preserved at {tempRoot}");
				return;
			}

			try
			{
				Directory.Delete(tempRoot, recursive: true);
			}
			catch (Exception ex)
			{
				TestContext.Progress.WriteLine($"Could not remove subprocess artifacts at {tempRoot}: {ex.Message}");
			}
		}

		protected void SeedContentIntoSupportDir(string supportDir = null)
		{
			CopyDirectoryRecursive(contentDirectory, Path.Combine(supportDir ?? tempRoot, "Content"));
		}

		protected static int RunOpenRaExe(string supportDir, string specificationPath, int wallClockTimeoutSeconds)
		{
			return RunOpenRaEntryPoint(
				supportDir,
				$"Launch.Match={specificationPath}",
				wallClockTimeoutSeconds);
		}

		protected static int RunReplayVerification(string supportDir, string replayPath, int wallClockTimeoutSeconds)
		{
			return RunOpenRaEntryPoint(
				supportDir,
				$"Launch.VerifyReplay={replayPath}",
				wallClockTimeoutSeconds);
		}

		static int RunOpenRaEntryPoint(string supportDir, string launchArgument, int wallClockTimeoutSeconds)
		{
			var startInfo = new ProcessStartInfo
			{
				FileName = OpenRaExecutable,
				WorkingDirectory = EngineDir,
				UseShellExecute = false,
				RedirectStandardOutput = true,
				RedirectStandardError = true,
				CreateNoWindow = true,
			};
			startInfo.ArgumentList.Add($"Engine.EngineDir={EngineDir}");
			startInfo.ArgumentList.Add($"Engine.SupportDir={supportDir}");
			startInfo.ArgumentList.Add("Game.Mod=ra");
			startInfo.ArgumentList.Add("Graphics.Mode=Windowed");
			startInfo.ArgumentList.Add("Graphics.WindowedSize=1024,768");
			startInfo.ArgumentList.Add("Graphics.VSync=false");
			startInfo.ArgumentList.Add(launchArgument);
			startInfo.Environment["OPENRA_BACKGROUND_WINDOW"] = "1";

			using var process = Process.Start(startInfo);
			Assert.That(process, Is.Not.Null, "Failed to start OpenRA subprocess.");

			var stdout = process.StandardOutput.ReadToEndAsync();
			var stderr = process.StandardError.ReadToEndAsync();

			if (!process.WaitForExit(wallClockTimeoutSeconds * 1000))
			{
				try { process.Kill(entireProcessTree: true); }
				catch (Exception ex) { TestContext.Progress.WriteLine($"Failed to kill timed-out worker: {ex.Message}"); }

				Assert.Fail(
					$"OpenRA did not exit within {wallClockTimeoutSeconds}s; killed. " +
					$"stdout (tail): {Truncate(stdout.Result, 4000)} stderr (tail): {Truncate(stderr.Result, 4000)}");
			}

			_ = stdout.Result;
			_ = stderr.Result;
			return process.ExitCode;
		}

		protected string WriteShortSpec(int maxWorldTicks)
		{
			return WriteSpec(maxWorldTicks, null, "spec.json");
		}

		protected string WriteSpec(int maxWorldTicks, string executionMode, string filename)
		{
			using var document = JsonDocument.Parse(File.ReadAllText(CanonicalSpecPath));
			using var output = new MemoryStream();
			using (var writer = new Utf8JsonWriter(output, new JsonWriterOptions { Indented = true }))
			{
				writer.WriteStartObject();
				foreach (var property in document.RootElement.EnumerateObject())
				{
					if (property.Name != "maxWorldTicks" &&
						(executionMode == null || property.Name != "executionMode"))
						property.WriteTo(writer);
				}

				writer.WriteNumber("maxWorldTicks", maxWorldTicks);
				if (executionMode != null)
					writer.WriteString("executionMode", executionMode);
				writer.WriteEndObject();
			}

			var target = Path.Combine(tempRoot, filename);
			File.WriteAllBytes(target, output.ToArray());
			return target;
		}

		protected static string ReadJsonField(string path, string field)
		{
			using var document = JsonDocument.Parse(File.ReadAllText(path));
			return document.RootElement.TryGetProperty(field, out var element) ? element.GetRawText() : null;
		}

		protected static string ReadStringField(string path, string field)
		{
			using var document = JsonDocument.Parse(File.ReadAllText(path));
			if (!document.RootElement.TryGetProperty(field, out var element) || element.ValueKind == JsonValueKind.Null)
				return null;

			return element.GetString();
		}

		protected static int? ReadIntField(string path, string field)
		{
			using var document = JsonDocument.Parse(File.ReadAllText(path));
			if (!document.RootElement.TryGetProperty(field, out var element) || element.ValueKind == JsonValueKind.Null)
				return null;

			return element.GetInt32();
		}

		protected static double? ReadDoubleField(string path, string field)
		{
			using var document = JsonDocument.Parse(File.ReadAllText(path));
			if (!document.RootElement.TryGetProperty(field, out var element) || element.ValueKind == JsonValueKind.Null)
				return null;

			return element.GetDouble();
		}

		protected static string ReadStatus(string path) => ReadStringField(path, "status");
		protected static string ReadFailurePhase(string path) => ReadStringField(path, "failurePhase");
		protected static string ReadReplayPath(string path) => ReadStringField(path, "replayPath");

		static string ResolveContentDirectory()
		{
			var configured = Environment.GetEnvironmentVariable(ContentEnvVar);
			if (!string.IsNullOrWhiteSpace(configured))
			{
				var fullPath = Path.GetFullPath(configured);
				return IsRaContentDirectory(fullPath) ? fullPath : null;
			}

			var candidates = new[]
			{
				Path.Combine(EngineDir, "Support", "Content"),
				Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "OpenRA", "Content"),
			};
			var candidate = candidates.FirstOrDefault(IsRaContentDirectory);
			if (candidate != null)
				return candidate;

			var supportRoot = Path.Combine(EngineDir, "Support");
			if (!Directory.Exists(supportRoot))
				return null;

			return Directory.EnumerateDirectories(supportRoot, "Content", SearchOption.AllDirectories)
				.FirstOrDefault(IsRaContentDirectory);
		}

		static bool IsRaContentDirectory(string path)
		{
			return !string.IsNullOrWhiteSpace(path) && File.Exists(Path.Combine(path, "ra", "v2", "allies.mix"));
		}

		static bool IsEnabled(string value)
		{
			return value == "1" || string.Equals(value, "true", StringComparison.OrdinalIgnoreCase);
		}

		static void CopyDirectoryRecursive(string sourceDir, string destinationDir)
		{
			Directory.CreateDirectory(destinationDir);
			foreach (var directory in Directory.EnumerateDirectories(sourceDir, "*", SearchOption.AllDirectories))
			{
				var relativePath = Path.GetRelativePath(sourceDir, directory);
				Directory.CreateDirectory(Path.Combine(destinationDir, relativePath));
			}

			foreach (var file in Directory.EnumerateFiles(sourceDir, "*", SearchOption.AllDirectories))
			{
				var relativePath = Path.GetRelativePath(sourceDir, file);
				var target = Path.Combine(destinationDir, relativePath);
				Directory.CreateDirectory(Path.GetDirectoryName(target));
				File.Copy(file, target, overwrite: true);
			}
		}

		static string Truncate(string value, int max)
		{
			if (string.IsNullOrEmpty(value))
				return string.Empty;

			return value.Length <= max ? value : value[^max..];
		}
	}
}
