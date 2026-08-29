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

using System.IO;
using NUnit.Framework;

namespace OpenRA.Test
{
	[TestFixture]
	[Category("Subprocess")]
	[Parallelizable(ParallelScope.None)]
	sealed class AutomatedMatchUncappedSubprocessTest : AutomatedMatchSubprocessTestBase
	{
		static readonly string NaturalSpecPath =
			Path.Combine(EngineDir, "docs", "ai", "examples", "automated-match-natural.json");
		static readonly string CandidateSpecPath =
			Path.Combine(EngineDir, "docs", "ai", "examples", "automated-match-m3-candidate.json");

		[TestCase(TestName = "UNCAPPED preserves paced synchronized evidence and improves tick throughput")]
		public void UncappedMatchesPacedEvidence()
		{
			var pacedSpecification = WriteSpec(600, "PACED", "paced.json");
			var uncappedSpecification = WriteSpec(600, "UNCAPPED", "uncapped.json");
			var pacedSupport = CreateSupport("paced");
			var uncappedSupport = CreateSupport("uncapped");

			var pacedExit = RunOpenRaExe(pacedSupport, pacedSpecification, 120);
			var uncappedExit = RunOpenRaExe(uncappedSupport, uncappedSpecification, 120);
			var pacedResult = Path.Combine(pacedSupport, "match-result.json");
			var uncappedResult = Path.Combine(uncappedSupport, "match-result.json");

			Assert.That(pacedExit, Is.EqualTo(4));
			Assert.That(uncappedExit, Is.EqualTo(4));
			Assert.That(ReadStringField(pacedResult, "executionMode"), Is.EqualTo("PACED"));
			Assert.That(ReadStringField(uncappedResult, "executionMode"), Is.EqualTo("UNCAPPED"));
			Assert.That(ReadIntField(uncappedResult, "finalWorldTick"), Is.EqualTo(ReadIntField(pacedResult, "finalWorldTick")));
			Assert.That(ReadIntField(uncappedResult, "finalSyncHash"), Is.EqualTo(ReadIntField(pacedResult, "finalSyncHash")));
			Assert.That(ReadJsonField(uncappedResult, "players"), Is.EqualTo(ReadJsonField(pacedResult, "players")));
			Assert.That(
				ReadStringField(uncappedResult, "orderDigestSha256"),
				Is.EqualTo(ReadStringField(pacedResult, "orderDigestSha256")));
			Assert.That(
				ReadStringField(uncappedResult, "strategicDecisionDigestSha256"),
				Is.EqualTo(ReadStringField(pacedResult, "strategicDecisionDigestSha256")));

			var pacedThroughput = ReadDoubleField(pacedResult, "ticksPerSecond");
			var uncappedThroughput = ReadDoubleField(uncappedResult, "ticksPerSecond");
			Assert.That(pacedThroughput, Is.Not.Null.And.GreaterThan(0));
			Assert.That(uncappedThroughput, Is.GreaterThan(pacedThroughput));

			AssertReplayVerifies(CreateSupport("paced-verify"), ReadReplayPath(pacedResult));
			AssertReplayVerifies(CreateSupport("uncapped-verify"), ReadReplayPath(uncappedResult));
		}

		[TestCase(TestName = "UNCAPPED natural game over is replay executable at the same world tick")]
		public void NaturalGameOverIsReplayExecutable()
		{
			Assert.That(File.Exists(NaturalSpecPath), Is.True, $"Natural-end specification not found: {NaturalSpecPath}");
			var matchSupport = CreateSupport("natural-match");
			var verifySupport = CreateSupport("natural-verify");
			var matchExit = RunOpenRaExe(matchSupport, NaturalSpecPath, 120);
			var result = Path.Combine(matchSupport, "match-result.json");

			Assert.That(matchExit, Is.EqualTo(0));
			Assert.That(ReadStatus(result), Is.EqualTo("COMPLETED"));
			Assert.That(ReadIntField(result, "finalWorldTick"), Is.LessThan(30000));
			var recordedTick = ReadIntField(result, "finalWorldTick");

			var verifyExit = RunReplayVerification(verifySupport, ReadReplayPath(result), 120);
			var verification = Path.Combine(verifySupport, "replay-verification-result.json");
			Assert.That(verifyExit, Is.EqualTo(0));
			Assert.That(ReadStatus(verification), Is.EqualTo("VERIFIED"));
			Assert.That(ReadIntField(verification, "recordedFinalWorldTick"), Is.EqualTo(recordedTick));
			Assert.That(ReadIntField(verification, "observedFinalWorldTick"), Is.EqualTo(recordedTick));
		}

		[TestCase(TestName = "M3 candidate identity and effective squad size are recorded and replay verified")]
		public void CandidateIdentityIsRecorded()
		{
			Assert.That(File.Exists(CandidateSpecPath), Is.True, $"M3 candidate specification not found: {CandidateSpecPath}");
			var matchSupport = CreateSupport("candidate-match");
			var verifySupport = CreateSupport("candidate-verify");
			var exit = RunOpenRaExe(matchSupport, CandidateSpecPath, 120);
			var result = Path.Combine(matchSupport, "match-result.json");

			Assert.That(exit, Is.EqualTo(4));
			Assert.That(ReadStringField(result, "candidateId"), Is.EqualTo("squad-size-40-baseline"));
			Assert.That(ReadIntField(result, "squadSize"), Is.EqualTo(40));
			Assert.That(ReadStringField(result, "candidateSha256"), Does.Match("^[0-9a-f]{64}$"));

			var verifyExit = RunReplayVerification(verifySupport, ReadReplayPath(result), 120);
			Assert.That(verifyExit, Is.EqualTo(0));
			Assert.That(
				ReadStatus(Path.Combine(verifySupport, "replay-verification-result.json")),
				Is.EqualTo("VERIFIED"));
		}

		string CreateSupport(string name)
		{
			var path = Path.Combine(tempRoot, name);
			Directory.CreateDirectory(path);
			SeedContentIntoSupportDir(path);
			return path;
		}

		static void AssertReplayVerifies(string supportDir, string replay)
		{
			var exit = RunReplayVerification(supportDir, replay, 120);
			var result = Path.Combine(supportDir, "replay-verification-result.json");
			Assert.That(exit, Is.EqualTo(0), $"Replay verification failed: {result}");
			Assert.That(ReadStatus(result), Is.EqualTo("VERIFIED"));
		}
	}
}
