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
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA
{
	public sealed class AutomatedMatchPlayerSpecification
	{
		public string Slot { get; set; }
		public string BotType { get; set; }
		public string Faction { get; set; }
		public string Color { get; set; }
		public int SpawnPoint { get; set; }
		public int Team { get; set; }
		public int Handicap { get; set; }
	}

	public sealed class AutomatedMatchSpecification
	{
		public const string LegacySchemaVersion = "1.0.0";
		public const string UncappedSchemaVersion = "1.1.0";
		public const string CurrentSchemaVersion = "1.2.0";
		public const string PacedExecutionMode = "PACED";
		public const string UncappedExecutionMode = "UNCAPPED";

		public string SchemaVersion { get; set; }
		public string ModId { get; set; }
		public string MapUid { get; set; }
		public int RandomSeed { get; set; }
		public Dictionary<string, string> Options { get; set; } = [];
		public List<AutomatedMatchPlayerSpecification> Players { get; set; } = [];
		public int MaxWorldTicks { get; set; }
		public bool RecordReplay { get; set; } = true;
		public string ExecutionMode { get; set; }
		public string CandidatePath { get; set; }

		internal string EffectiveExecutionMode => SchemaVersion == LegacySchemaVersion ? PacedExecutionMode : ExecutionMode;

		internal static AutomatedMatchSpecification Parse(string json, string source)
		{
			try
			{
				var specification = JsonSerializer.Deserialize<AutomatedMatchSpecification>(json, AutomatedMatchRunner.JsonOptions);
				if (specification == null)
					throw new InvalidDataException($"Automated match specification '{source}' is empty.");

				specification.Validate(source);
				return specification;
			}
			catch (JsonException ex)
			{
				throw new InvalidDataException($"Automated match specification '{source}' is invalid JSON: {ex.Message}", ex);
			}
		}

		internal void Validate(string source)
		{
			if (SchemaVersion != LegacySchemaVersion && SchemaVersion != UncappedSchemaVersion && SchemaVersion != CurrentSchemaVersion)
				throw new InvalidDataException(
					$"Automated match specification '{source}' uses unsupported schemaVersion '{SchemaVersion}'. " +
					$"Expected '{LegacySchemaVersion}', '{UncappedSchemaVersion}', or '{CurrentSchemaVersion}'.");

			if (SchemaVersion == LegacySchemaVersion && ExecutionMode != null)
				throw new InvalidDataException(
					$"Automated match specification '{source}' cannot define executionMode with schemaVersion '{LegacySchemaVersion}'.");

			if (SchemaVersion != LegacySchemaVersion &&
				ExecutionMode is not (PacedExecutionMode or UncappedExecutionMode))
				throw new InvalidDataException(
					$"Automated match specification '{source}' must set executionMode to PACED or UNCAPPED.");

			if (SchemaVersion != CurrentSchemaVersion && CandidatePath != null)
				throw new InvalidDataException(
					$"Automated match specification '{source}' requires schemaVersion '{CurrentSchemaVersion}' to define candidatePath.");

			if (SchemaVersion == CurrentSchemaVersion && CandidatePath != null && string.IsNullOrWhiteSpace(CandidatePath))
				throw new InvalidDataException($"Automated match specification '{source}' candidatePath cannot be empty.");

			if (string.IsNullOrWhiteSpace(ModId))
				throw new InvalidDataException($"Automated match specification '{source}' must define modId.");
			if (ModId != "ra")
				throw new InvalidDataException($"Automated match specification '{source}' only supports modId 'ra'.");

			if (string.IsNullOrWhiteSpace(MapUid))
				throw new InvalidDataException($"Automated match specification '{source}' must define mapUid.");

			if (MaxWorldTicks <= 0)
				throw new InvalidDataException($"Automated match specification '{source}' must set maxWorldTicks above zero.");

			if (!RecordReplay)
				throw new InvalidDataException($"Automated match specification '{source}' must enable recordReplay.");

			if (Players == null || Players.Count < 2)
				throw new InvalidDataException($"Automated match specification '{source}' must define at least two bot players.");

			if (Options == null)
				throw new InvalidDataException($"Automated match specification '{source}' must define an options object.");

			var slots = new HashSet<string>(StringComparer.Ordinal);
			var colors = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
			foreach (var player in Players)
			{
				if (player == null || string.IsNullOrWhiteSpace(player.Slot) || string.IsNullOrWhiteSpace(player.BotType) ||
					string.IsNullOrWhiteSpace(player.Faction) || string.IsNullOrWhiteSpace(player.Color))
					throw new InvalidDataException(
						$"Automated match specification '{source}' has a player with a missing slot, botType, faction, or color.");

				if (!slots.Add(player.Slot))
					throw new InvalidDataException($"Automated match specification '{source}' uses slot '{player.Slot}' more than once.");

				if (!colors.Add(player.Color))
					throw new InvalidDataException($"Automated match specification '{source}' uses color '{player.Color}' more than once.");

				if (player.SpawnPoint < 0)
					throw new InvalidDataException($"Automated match specification '{source}' has a negative spawnPoint.");

				if (player.Team < 0)
					throw new InvalidDataException($"Automated match specification '{source}' has a negative team.");

				if (player.Handicap is < 0 or > 95)
					throw new InvalidDataException($"Automated match specification '{source}' has a handicap outside 0..95.");
			}
		}
	}

	public sealed class StrategicAiCandidate
	{
		public const string CurrentSchemaVersion = "1.0.0";

		public string SchemaVersion { get; set; }
		public string CandidateId { get; set; }
		public int SquadSize { get; set; }
		public string Notes { get; set; }

		internal static StrategicAiCandidate Parse(string json, string source)
		{
			try
			{
				var candidate = JsonSerializer.Deserialize<StrategicAiCandidate>(json, AutomatedMatchRunner.JsonOptions);
				if (candidate == null)
					throw new InvalidDataException($"StrategicAI candidate '{source}' is empty.");

				candidate.Validate(source);
				return candidate;
			}
			catch (JsonException ex)
			{
				throw new InvalidDataException($"StrategicAI candidate '{source}' is invalid JSON: {ex.Message}", ex);
			}
		}

		internal void Validate(string source)
		{
			if (SchemaVersion != CurrentSchemaVersion)
				throw new InvalidDataException(
					$"StrategicAI candidate '{source}' uses unsupported schemaVersion '{SchemaVersion}'. " +
					$"Expected '{CurrentSchemaVersion}'.");

			if (string.IsNullOrWhiteSpace(CandidateId) || CandidateId.Length > 80 ||
				!char.IsAsciiLetterOrDigit(CandidateId[0]) ||
				!CandidateId.All(c => char.IsAsciiLetterOrDigit(c) || c is '.' or '_' or '-'))
				throw new InvalidDataException(
					$"StrategicAI candidate '{source}' candidateId must contain 1..80 ASCII letters, digits, '.', '_', or '-'.");

			if (SquadSize is < 1 or > 1000)
				throw new InvalidDataException($"StrategicAI candidate '{source}' squadSize must be in the range 1..1000.");

			if (Notes == null)
				throw new InvalidDataException($"StrategicAI candidate '{source}' must define notes as a string.");
		}
	}

	public static class AutomatedMatchRunner
	{
		internal static readonly JsonSerializerOptions JsonOptions = new()
		{
			PropertyNameCaseInsensitive = false,
			PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
			UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
			WriteIndented = true,
		};

		// Process exit codes for the Launch.Match runner. Stable; do not renumber.
		// 0 is the historical success code and must remain so for existing CI smoke checks.
		internal static class ExitCode
		{
			public const int Success = 0;
			public const int PreflightFailure = 1;
			public const int SetupFailure = 2;
			public const int RuntimeFailure = 3;
			public const int TimedOut = 4;
			public const int Aborted = 5;
		}

		internal sealed class PlayerResult
		{
			public string Slot { get; set; }
			public string Name { get; set; }
			public string BotType { get; set; }
			public string Outcome { get; set; }
		}

		internal sealed class MatchResult
		{
			public string SchemaVersion { get; set; } = AutomatedMatchSpecification.CurrentSchemaVersion;
			public string Status { get; set; }
			public string FailurePhase { get; set; }
			public string Failure { get; set; }
			public string EngineVersion { get; set; }
			public string ModId { get; set; }
			public string ModVersion { get; set; }
			public string MapUid { get; set; }
			public int RandomSeed { get; set; }
			public int FinalWorldTick { get; set; }
			public int? FinalNetworkFrame { get; set; }
			public DateTime StartedUtc { get; set; }
			public DateTime EndedUtc { get; set; }
			public string SpecificationPath { get; set; }
			public string SpecificationSha256 { get; set; }
			public string StrategicLogPath { get; set; }
			public string ReplayPath { get; set; }
			public string ReplaySha256 { get; set; }
			public string ExecutionMode { get; set; }
			public long? StartupElapsedMs { get; set; }
			public long? SimulationElapsedMs { get; set; }
			public double? TicksPerSecond { get; set; }
			public long OrderWaitElapsedMs { get; set; }
			public long? PeakWorkingSetBytes { get; set; }
			public long? ReplaySizeBytes { get; set; }
			public int? FinalSyncHash { get; set; }
			public string OrderDigestSha256 { get; set; }
			public string StrategicDecisionDigestSha256 { get; set; }
			public string CandidateId { get; set; }
			public string CandidatePath { get; set; }
			public string CandidateSha256 { get; set; }
			public int? SquadSize { get; set; }
			public List<PlayerResult> Players { get; set; } = [];
		}

		static AutomatedMatchSpecification specification;
		static StrategicAiCandidate candidate;
		static MatchResult result;
		static HashSet<string> existingReplays;
		static bool timedOut;
		static bool finalized;
		static string pendingSpecificationPath;
		static long processStartedTimestamp;
		static long worldStartedTimestamp;
		static long orderWaitStopwatchTicks;
#pragma warning disable IDE0032 // Auto-implemented properties are not available for static state.
		static bool resultAlreadyRecorded;
#pragma warning restore IDE0032

		public static void Start(string specificationPath)
		{
			if (result != null)
				throw new InvalidOperationException("An automated match is already active.");

			var fullPath = Path.GetFullPath(specificationPath);
			processStartedTimestamp = Stopwatch.GetTimestamp();
			pendingSpecificationPath = fullPath;
			resultAlreadyRecorded = false;

			// Open + parse the specification here so the resulting exception
			// is caught and converted to a preflight match-result.json before
			// any further Initialize work runs. Empirically (2026-08-26, OpenRA
			// Launcher on .NET 10, Windows): when a File.ReadAllText /
			// JsonException on the spec path escaped this Start() method and
			// propagated up to Game.InitializeAndRun's catch, the .NET apphost
			// process still exited with 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN,
			// value -1073740791) instead of the documented exit code 1 the
			// launcher returned. Catching the exception here, recording the
			// preflight failure, and exiting the game loop normally is what
			// surfaces the documented exit code on the worker path. The exact
			// .NET internal mechanism that produced 0xC0000409 in the original
			// path is not isolated; the comment records the observable behavior
			// and the worker-path fix, not a runtime-internals theory.
			string json;
			try
			{
				json = File.ReadAllText(fullPath);
			}
			catch (Exception ex)
			{
				RecordPreflightFailure(fullPath, ex);
				Game.Exit();
				return;
			}

			AutomatedMatchSpecification parsedSpecification;
			StrategicAiCandidate parsedCandidate = null;
			string candidateFullPath = null;
			try
			{
				parsedSpecification = AutomatedMatchSpecification.Parse(json, fullPath);
				if (parsedSpecification.CandidatePath != null)
				{
					candidateFullPath = Path.GetFullPath(
						parsedSpecification.CandidatePath,
						Path.GetDirectoryName(fullPath) ?? Environment.CurrentDirectory);
					parsedCandidate = StrategicAiCandidate.Parse(File.ReadAllText(candidateFullPath), candidateFullPath);
				}
			}
			catch (Exception ex)
			{
				RecordPreflightFailure(fullPath, ex);
				Game.Exit();
				return;
			}

			specification = parsedSpecification;
			candidate = parsedCandidate;
			result = new MatchResult
			{
				Status = "STARTING",
				EngineVersion = Game.EngineVersion,
				ModId = specification.ModId,
				ModVersion = Game.ModData.Manifest.Metadata.Version,
				MapUid = specification.MapUid,
				RandomSeed = specification.RandomSeed,
				StartedUtc = DateTime.UtcNow,
				SpecificationPath = fullPath,
				SpecificationSha256 = Sha256(fullPath),
				StrategicLogPath = Path.Combine(Platform.SupportDir, "Logs", "strategic-decisions.log"),
				ExecutionMode = specification.EffectiveExecutionMode,
				CandidateId = candidate?.CandidateId,
				CandidatePath = candidateFullPath,
				CandidateSha256 = candidateFullPath != null ? Sha256(candidateFullPath) : null,
				SquadSize = candidate?.SquadSize,
			};

			if (specification.ModId != Game.ModData.Manifest.Id)
				throw new InvalidDataException(
					$"Automated match modId '{specification.ModId}' does not match the loaded mod '{Game.ModData.Manifest.Id}'.");

			var map = Game.ModData.MapCache[specification.MapUid];
			if (map.Status != MapStatus.Available)
				throw new InvalidDataException($"Automated match map '{specification.MapUid}' is not available.");

			existingReplays = FindReplays().ToHashSet(StringComparer.OrdinalIgnoreCase);
			Game.CreateAndStartLocalServer(
				map.Uid,
				lobby => CreateSetupOrders(lobby, map, specification),
				isSkirmish: true);
		}

		internal static void WorldStarted(World world)
		{
			if (result == null)
				return;

			result.Status = "RUNNING";
			worldStartedTimestamp = Stopwatch.GetTimestamp();
			result.StartupElapsedMs =
				(long)Stopwatch.GetElapsedTime(processStartedTimestamp, worldStartedTimestamp).TotalMilliseconds;
			world.GameOver += () => OnGameOver(world);
		}

		internal static bool UsesUncappedLogic =>
			result?.Status == "RUNNING" &&
			!finalized &&
			specification?.EffectiveExecutionMode == AutomatedMatchSpecification.UncappedExecutionMode;

		// Bot modules use World.BotRandom for unsynchronized order selection.
		// Interactive matches alias that to the historical entropy-seeded LocalRandom,
		// while automated experiments bind it to the registered match seed so an
		// independent same-specification rerun produces the same recorded Orders.
		internal static int? DeterministicBotRandomSeed => specification?.RandomSeed;

		public static int? StrategicSquadSizeOverride => candidate?.SquadSize;

		internal static void RecordOrderWait(long elapsedStopwatchTicks)
		{
			if (elapsedStopwatchTicks > 0)
				orderWaitStopwatchTicks += elapsedStopwatchTicks;
		}

		internal static void Tick(World world)
		{
			if (result == null || finalized || timedOut)
				return;

			if (SynchronizedMatchEnd.TryEnd(world))
				return;

			SynchronizedMatchTimeout.TryEnd(world, () =>
			{
				timedOut = true;
				result.Status = "TIMED_OUT";
			});
		}

		static void OnGameOver(World world)
		{
			if (result == null || finalized)
				return;

			if (!timedOut)
				result.Status = "COMPLETED";

			CaptureWorld(world);
			Game.Exit();
		}

		internal static void RecordFailure(Exception ex)
		{
			if (result == null || finalized)
				return;

			result.Status = "FAILED";
			result.FailurePhase = result.FinalWorldTick > 0 ? "RUN" : "SETUP";
			result.Failure = ex.GetType().Name + ": " + ex.Message;
		}

		// Called by the preflight wrapper in Game.StartAutomatedMatch when the specification
		// cannot even be opened or parsed. The runner has no other diagnostic state at this
		// point, so we build a minimal MatchResult with FailurePhase = PREFLIGHT and write
		// it through the standard path so the supervisor can always observe an artifact.
		internal static void RecordPreflightFailure(string specificationPath, Exception ex)
		{
			if (finalized)
				return;

			try
			{
				var fullPath = Path.GetFullPath(specificationPath);
				pendingSpecificationPath = fullPath;
				result = new MatchResult
				{
					Status = "FAILED",
					FailurePhase = "PREFLIGHT",
					Failure = ex.GetType().Name + ": " + ex.Message,
					EngineVersion = Game.EngineVersion,
					ModId = "ra",
					StartedUtc = DateTime.UtcNow,
					EndedUtc = DateTime.UtcNow,
					SpecificationPath = fullPath,
					StrategicLogPath = Path.Combine(Platform.SupportDir, "Logs", "strategic-decisions.log"),
					ExecutionMode = AutomatedMatchSpecification.PacedExecutionMode,
				};
				resultAlreadyRecorded = true;
				FinalizeResult();
			}
			catch
			{
				// Preflight may run before Platform.SupportDir is ready; never throw from here.
			}
		}

		// Called by the setup wrapper in Game.StartAutomatedMatch when Start() throws
		// after the MatchResult was constructed but before WorldStarted was reached.
		// Mirrors RecordFailure for the SETUP phase but is also reachable when an
		// exception escapes the Start() body itself (no result fields populated yet).
		internal static void RecordFailureFromStart(Exception ex)
		{
			if (finalized)
				return;

			if (result == null)
			{
				RecordPreflightFailure(pendingSpecificationPath ?? "<unknown>", ex);
				return;
			}

			if (result.FinalWorldTick > 0)
			{
				RecordFailure(ex);
				return;
			}

			result.Status = "FAILED";
			result.FailurePhase = "SETUP";
			result.Failure = ex.GetType().Name + ": " + ex.Message;
			resultAlreadyRecorded = true;
		}

		// Pure mapping from current runner state to the documented process exit code.
		// Returns 0 when no automated match is active so the existing RunStatus path is
		// preserved for non-Launch.Match entry points.
		internal static int GetExitCode()
		{
			if (result == null)
				return ExitCode.Success;

			return result.Status switch
			{
				"COMPLETED" => ExitCode.Success,
				"TIMED_OUT" => ExitCode.TimedOut,
				"ABORTED" => ExitCode.Aborted,
				"FAILED" => result.FailurePhase switch
				{
					"PREFLIGHT" => ExitCode.PreflightFailure,
					"SETUP" => ExitCode.SetupFailure,
					_ => ExitCode.RuntimeFailure,
				},
				_ => ExitCode.Aborted,
			};
		}

		// True when the runner has been activated for the current process:
		// either a specification was opened (PendingSpecificationPath is set) or a
		// preflight failure has already been recorded. Game.InitializeAndRun and
		// OpenRA.Launcher.Program.Main use this to decide between returning the
		// documented runner exit code on the Launch.Match path and falling back to
		// the historical rethrow or RunStatus.Error on every other entry point.
		public static bool IsActive => pendingSpecificationPath != null || resultAlreadyRecorded;

		internal static bool ResultAlreadyRecorded => resultAlreadyRecorded;

		// Test seam: clears the static runner state so unit tests can drive ExitCode()
		// against a known prior status without spinning up the full game loop.
		internal static void ResetForTest()
		{
			specification = null;
			candidate = null;
			result = null;
			existingReplays = null;
			timedOut = false;
			finalized = false;
			pendingSpecificationPath = null;
			resultAlreadyRecorded = false;
			processStartedTimestamp = 0;
			worldStartedTimestamp = 0;
			orderWaitStopwatchTicks = 0;
		}

		// Test seam: lets unit tests assert the pure ExitCode() mapping by writing
		// a synthetic MatchResult into the runner without going through Start().
		internal static void SetResultForTest(MatchResult r, bool timedOutFlag)
		{
			result = r;
			timedOut = timedOutFlag;
			finalized = true;
			resultAlreadyRecorded = true;
		}

		internal static void FinalizeResult()
		{
			if (result == null || finalized)
				return;

			finalized = true;
			result.EndedUtc = DateTime.UtcNow;
			result.OrderWaitElapsedMs =
				(long)Stopwatch.GetElapsedTime(0, orderWaitStopwatchTicks).TotalMilliseconds;
			result.PeakWorkingSetBytes = Process.GetCurrentProcess().PeakWorkingSet64;
			if (result.Status is "STARTING" or "RUNNING")
				result.Status = "ABORTED";

			try
			{
				// Strategic decisions are queued by the asynchronous logging thread.
				// Place a barrier before hashing so the digest represents every
				// decision made by the completed match.
				Log.Flush();

				var replay = FindReplays()
					.Where(path => existingReplays == null || !existingReplays.Contains(path))
					.OrderByDescending(File.GetLastWriteTimeUtc)
					.FirstOrDefault();
				if (replay != null)
				{
					result.ReplayPath = replay;
					result.ReplaySha256 = Sha256(replay);
					result.ReplaySizeBytes = new FileInfo(replay).Length;
					result.OrderDigestSha256 =
						AutomatedMatchEvidence.OrderStreamSha256(replay, result.FinalNetworkFrame);
				}

				result.StrategicDecisionDigestSha256 =
					AutomatedMatchEvidence.StrategicDecisionSha256(result.StrategicLogPath);
			}
			catch (Exception ex)
			{
				// Evidence is part of the scientific result contract. A digest failure
				// therefore fails the run, but it must never suppress the result artifact
				// that explains the failure to the supervising process.
				result.Status = "FAILED";
				result.FailurePhase = "RUN";
				result.Failure = "Evidence collection failed: " + ex.GetType().Name + ": " + ex.Message;
			}

			var resultPath = Path.Combine(Platform.SupportDir, "match-result.json");
			var temporaryPath = resultPath + ".tmp";
			File.WriteAllText(temporaryPath, JsonSerializer.Serialize(result, JsonOptions) + Environment.NewLine);
			File.Move(temporaryPath, resultPath, true);
			Console.WriteLine($"Automated match result written to {resultPath}");
		}

		static IEnumerable<Order> CreateSetupOrders(
			Session initialLobby, MapPreview map, AutomatedMatchSpecification match)
		{
			var lobby = Session.Deserialize(initialLobby.Serialize(), "AutomatedMatch");
			var admin = lobby.Clients.SingleOrDefault(c => c.IsAdmin) ??
				throw new InvalidDataException("Automated match local server did not create an admin client.");

			admin.Slot = null;
			admin.State = Session.ClientState.Ready;
			lobby.Clients.RemoveAll(c => c.IsBot);
			lobby.GlobalSettings.RandomSeed = match.RandomSeed;

			var bots = map.PlayerActorInfo.TraitInfos<IBotInfo>().ToDictionary(b => b.Type, StringComparer.Ordinal);
			var factions = map.WorldActorInfo.TraitInfos<FactionInfo>()
				.Where(f => f.Selectable)
				.Select(f => f.InternalName)
				.ToHashSet(StringComparer.Ordinal);
			var options = map.PlayerActorInfo.TraitInfos<ILobbyOptions>()
				.Concat(map.WorldActorInfo.TraitInfos<ILobbyOptions>())
				.SelectMany(t => t.LobbyOptions(map))
				.ToDictionary(o => o.Id, StringComparer.Ordinal);
			lobby.GlobalSettings.LobbyOptions = options.ToDictionary(
				kv => kv.Key,
				kv => new Session.LobbyOptionState
				{
					IsLocked = kv.Value.IsLocked,
					Value = kv.Value.DefaultValue,
					PreferredValue = kv.Value.DefaultValue,
				},
				StringComparer.Ordinal);

			foreach (var (id, value) in match.Options)
			{
				if (!options.TryGetValue(id, out var option))
					throw new InvalidDataException($"Automated match option '{id}' is not defined by map '{map.Uid}'.");

				var state = lobby.GlobalSettings.LobbyOptions[id];

				if (!option.Values.ContainsKey(value))
					throw new InvalidDataException($"Automated match option '{id}' does not allow value '{value}'.");

				if (option.IsLocked && state.Value != value)
					throw new InvalidDataException($"Automated match option '{id}' is locked to '{state.Value}', not '{value}'.");

				state.Value = state.PreferredValue = value;
			}

			var nextClientIndex = lobby.Clients.Max(c => c.Index) + 1;
			foreach (var player in match.Players)
			{
				if (!lobby.Slots.TryGetValue(player.Slot, out var slot) || slot.Closed || !slot.AllowBots)
					throw new InvalidDataException($"Automated match slot '{player.Slot}' is unavailable for bots.");

				if (!bots.TryGetValue(player.BotType, out var botInfo))
					throw new InvalidDataException($"Automated match botType '{player.BotType}' is not available on map '{map.Uid}'.");

				if (!factions.Contains(player.Faction))
					throw new InvalidDataException($"Automated match faction '{player.Faction}' is not selectable on map '{map.Uid}'.");

				Color color;
				try
				{
					color = FieldLoader.GetValue<Color>("color", player.Color);
				}
				catch (YamlException ex)
				{
					throw new InvalidDataException($"Automated match color '{player.Color}' is invalid.", ex);
				}

				var client = new Session.Client
				{
					Index = nextClientIndex++,
					Name = botInfo.Name,
					Bot = botInfo.Type,
					BotControllerClientIndex = admin.Index,
					Slot = player.Slot,
					State = Session.ClientState.NotReady,
					Color = color,
					PreferredColor = color,
					Faction = player.Faction,
					SpawnPoint = player.SpawnPoint,
					Team = player.Team,
					Handicap = player.Handicap,
				};

				Server.Server.SyncClientToPlayerReference(client, map.Players.Players[player.Slot]);
				lobby.Clients.Add(client);
			}

			var missingRequiredSlots = lobby.Slots
				.Where(kv => kv.Value.Required && lobby.ClientInSlot(kv.Key) == null)
				.Select(kv => kv.Key)
				.ToArray();
			if (missingRequiredSlots.Length > 0)
				throw new InvalidDataException(
					"Automated match does not fill required slots: " + string.Join(", ", missingRequiredSlots));

			return
			[
				Order.Command($"sync_lobby {lobby.Serialize()}"),

				// schedule_match_timeout must precede startgame: LobbyCommands.ValidateCommand rejects
				// ordinary lobby commands after the server has entered GameStarted, and the handler
				// dispatches the server-dispatched "ScheduleMatchTimeout" Order (frame-0) recorded
				// into the replay so replay playback ends at the same tick.
				Order.Command($"schedule_match_timeout {match.MaxWorldTicks}"),
				Order.Command("startgame"),
			];
		}

		static void CaptureWorld(World world)
		{
			result.FinalWorldTick = world.WorldTick;
			result.FinalNetworkFrame = world.OrderManager?.NetFrameNumber;
			result.FinalSyncHash = world.SyncHash();
			if (worldStartedTimestamp != 0)
			{
				var elapsed = Stopwatch.GetElapsedTime(worldStartedTimestamp);
				result.SimulationElapsedMs = (long)elapsed.TotalMilliseconds;
				result.TicksPerSecond = elapsed.TotalSeconds > 0 ? world.WorldTick / elapsed.TotalSeconds : null;
			}

			result.Players = world.Players
				.Where(p => p.Playable && !p.NonCombatant)
				.Select(p =>
				{
					var client = world.LobbyInfo.ClientWithIndex(p.ClientIndex);
					return new PlayerResult
					{
						Slot = client?.Slot,
						Name = p.PlayerName,
						BotType = p.BotType,
						Outcome = p.WinState.ToString().ToUpperInvariant(),
					};
				})
				.ToList();
		}

		static IEnumerable<string> FindReplays()
		{
			var replayRoot = Path.Combine(Platform.SupportDir, "Replays", Game.ModData.Manifest.Id);
			return Directory.Exists(replayRoot) ?
				Directory.EnumerateFiles(replayRoot, "*.orarep", SearchOption.AllDirectories) : [];
		}

		static string Sha256(string path)
		{
			using var stream = File.OpenRead(path);
			return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
		}
	}
}
