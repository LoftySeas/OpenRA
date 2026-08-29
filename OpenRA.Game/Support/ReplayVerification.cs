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
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using OpenRA.FileFormats;
using OpenRA.Network;

namespace OpenRA
{
	public static class ReplayVerificationRunner
	{
		public const string CurrentSchemaVersion = "1.0.0";

		internal static class ExitCode
		{
			public const int Verified = 0;
			public const int PreflightFailure = 1;
			public const int SetupFailure = 2;
			public const int OutOfSync = 3;
			public const int Incomplete = 4;
			public const int RuntimeFailure = 5;
		}

		internal sealed class VerificationResult
		{
			public string SchemaVersion { get; set; } = CurrentSchemaVersion;
			public string Status { get; set; }
			public string FailurePhase { get; set; }
			public string Failure { get; set; }
			public string EngineVersion { get; set; }
			public string ModId { get; set; }
			public string ModVersion { get; set; }
			public string MapUid { get; set; }
			public string ReplayPath { get; set; }
			public long? ReplaySizeBytes { get; set; }
			public string ReplaySha256 { get; set; }
			public int? RecordedFinalWorldTick { get; set; }
			public int? ObservedFinalWorldTick { get; set; }
			public int? FinalNetworkFrame { get; set; }
			public int? LastValidatedSyncFrame { get; set; }
			public int? OutOfSyncFrame { get; set; }
			public int? ScheduledMatchTimeoutTick { get; set; }
			public int? VerificationTimestepMs { get; set; }
			public DateTime StartedUtc { get; set; }
			public DateTime EndedUtc { get; set; }
		}

		static VerificationResult result;
		static ReplayConnection connection;
		static bool finalized;
		static string pendingReplayPath;

		public static bool IsActive => pendingReplayPath != null;

		public static void Start(string replayPath)
		{
			if (IsActive)
				throw new InvalidOperationException("A replay verification is already active.");

			var fullPath = Path.GetFullPath(replayPath);
			pendingReplayPath = fullPath;
			result = new VerificationResult
			{
				Status = "STARTING",
				EngineVersion = Game.EngineVersion,
				ReplayPath = fullPath,
				StartedUtc = DateTime.UtcNow,
			};

			ReplayMetadata metadata;
			try
			{
				if (!File.Exists(fullPath))
					throw new FileNotFoundException("Replay file was not found.", fullPath);

				var file = new FileInfo(fullPath);
				result.ReplaySizeBytes = file.Length;
				result.ReplaySha256 = Sha256(fullPath);
				metadata = ReplayMetadata.Read(fullPath) ??
					throw new InvalidDataException("Replay metadata is missing or invalid.");

				result.ModId = metadata.GameInfo.Mod;
				result.ModVersion = metadata.GameInfo.Version;
				result.MapUid = metadata.GameInfo.MapUid;
				result.RecordedFinalWorldTick = metadata.GameInfo.FinalGameTick;

				if (metadata.GameInfo.Mod != Game.ModData.Manifest.Id)
					throw new InvalidDataException(
						$"Replay mod '{metadata.GameInfo.Mod}' does not match the loaded mod '{Game.ModData.Manifest.Id}'.");

				if (metadata.GameInfo.Version != Game.ModData.Manifest.Metadata.Version)
					throw new InvalidDataException(
						$"Replay mod version '{metadata.GameInfo.Version}' does not match the loaded version " +
						$"'{Game.ModData.Manifest.Metadata.Version}'.");

				var compatibility = ReplayCompatibility.Check(metadata, Game.ModData);
				if (compatibility != ReplayCompatibilityStatus.Compatible)
					throw new InvalidDataException($"Replay compatibility check failed: {compatibility}.");

				if (metadata.GameInfo.FinalGameTick <= 0)
					throw new InvalidDataException("Replay metadata must define a positive final game tick.");
			}
			catch (Exception ex)
			{
				FailAndExit("PREFLIGHT", ex);
				return;
			}

			try
			{
				connection = new ReplayConnection(fullPath);
				if (!connection.IsValid || connection.LobbyInfo == null)
					throw new InvalidDataException("Replay order stream does not contain a valid StartGame setup.");

				result.Status = "LOADING";
				Game.JoinReplay(connection);
			}
			catch (Exception ex)
			{
				FailAndExit("SETUP", ex);
			}
		}

		internal static void WorldStarted(World world)
		{
			if (!IsActive || finalized)
				return;

			if (world == null || world.Type != WorldType.Regular || !world.IsReplay)
			{
				FailAndExit("SETUP", new InvalidOperationException("Replay verification did not start a regular replay world."));
				return;
			}

			world.ReplayTimestep = 1;
			result.VerificationTimestepMs = 1;
			result.Status = "VERIFYING";
		}

		internal static void Tick(World world)
		{
			if (!IsActive || finalized || result.Status != "VERIFYING")
				return;

			if (world == null || world.Type != WorldType.Regular || !world.IsReplay)
			{
				FailAndExit("RUN", new InvalidOperationException("The active replay world became unavailable."));
				return;
			}

			var orderManager = world.OrderManager;
			if (orderManager.IsOutOfSync)
			{
				CaptureWorld(world);
				result.Status = "OUT_OF_SYNC";
				result.Failure = $"Replay diverged at network frame {orderManager.OutOfSyncFrame}.";
				FinalizeAndExit();
				return;
			}

			SynchronizedMatchEnd.TryEnd(world);
			SynchronizedMatchTimeout.TryEnd(world);

			if (world.IsGameOver)
			{
				CaptureWorld(world);
				if (result.ObservedFinalWorldTick != result.RecordedFinalWorldTick)
				{
					result.Status = "FINAL_TICK_MISMATCH";
					result.Failure =
						$"Replay ended at world tick {result.ObservedFinalWorldTick}; metadata records {result.RecordedFinalWorldTick}.";
				}
				else if (!result.LastValidatedSyncFrame.HasValue)
				{
					result.Status = "INCOMPLETE";
					result.Failure = "Replay ended without a validated synchronization hash.";
				}
				else
					result.Status = "VERIFIED";

				FinalizeAndExit();
				return;
			}

			if (world.WorldTick > 0 && connection.IsExhausted && orderManager.IsWaitingForOrders)
			{
				CaptureWorld(world);
				result.Status = "INCOMPLETE";
				result.Failure = "Replay order stream was exhausted before the world reached a terminal state.";
				FinalizeAndExit();
			}
		}

		internal static void RecordFailure(Exception ex)
		{
			if (!IsActive || finalized)
				return;

			result.Status = "FAILED";
			result.FailurePhase = "RUN";
			result.Failure = ex.GetType().Name + ": " + ex.Message;
		}

		internal static int GetExitCode()
		{
			if (result == null)
				return ExitCode.Verified;

			return result.Status switch
			{
				"VERIFIED" => ExitCode.Verified,
				"OUT_OF_SYNC" => ExitCode.OutOfSync,
				"INCOMPLETE" or "FINAL_TICK_MISMATCH" => ExitCode.Incomplete,
				"FAILED" => result.FailurePhase switch
				{
					"PREFLIGHT" => ExitCode.PreflightFailure,
					"SETUP" => ExitCode.SetupFailure,
					_ => ExitCode.RuntimeFailure,
				},
				_ => ExitCode.RuntimeFailure,
			};
		}

		internal static void FinalizeResult()
		{
			if (result == null || finalized)
				return;

			finalized = true;
			result.EndedUtc = DateTime.UtcNow;
			if (result.Status is "STARTING" or "LOADING" or "VERIFYING")
				result.Status = "ABORTED";

			var resultPath = Path.Combine(Platform.SupportDir, "replay-verification-result.json");
			var temporaryPath = resultPath + ".tmp";
			File.WriteAllText(
				temporaryPath,
				JsonSerializer.Serialize(result, AutomatedMatchRunner.JsonOptions) + Environment.NewLine);
			File.Move(temporaryPath, resultPath, true);
			Console.WriteLine($"Replay verification result written to {resultPath}");
		}

		static void CaptureWorld(World world)
		{
			var orderManager = world.OrderManager;
			result.ObservedFinalWorldTick = world.WorldTick;
			result.FinalNetworkFrame = orderManager.NetFrameNumber;
			result.LastValidatedSyncFrame = orderManager.LastValidatedSyncFrame;
			result.OutOfSyncFrame = orderManager.OutOfSyncFrame;
			result.ScheduledMatchTimeoutTick = orderManager.ScheduledMatchTimeoutTick;
		}

		static void FailAndExit(string phase, Exception ex)
		{
			result.Status = "FAILED";
			result.FailurePhase = phase;
			result.Failure = ex.GetType().Name + ": " + ex.Message;
			FinalizeAndExit();
		}

		static void FinalizeAndExit()
		{
			FinalizeResult();
			Game.Exit();
		}

		static string Sha256(string path)
		{
			using var stream = File.OpenRead(path);
			return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
		}

		internal static void ResetForTest()
		{
			result = null;
			connection = null;
			finalized = false;
			pendingReplayPath = null;
		}

		internal static void SetResultForTest(VerificationResult verificationResult)
		{
			result = verificationResult;
			pendingReplayPath = "test.orarep";
			finalized = true;
		}
	}
}
