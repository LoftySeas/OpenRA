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
using OpenRA.Support;

namespace OpenRA.Test
{
	[TestFixture]
	sealed class AutomatedMatchTest
	{
		[TestCase(TestName = "Automated bot RNG is reproducible and interactive mode preserves LocalRandom")]
		public void AutomatedBotRandomIsIsolated()
		{
			var localRandom = new MersenneTwister();
			Assert.That(World.CreateBotRandom(localRandom, null), Is.SameAs(localRandom));

			var first = World.CreateBotRandom(localRandom, 123456);
			var second = World.CreateBotRandom(new MersenneTwister(), 123456);
			Assert.That(first, Is.Not.SameAs(localRandom));
			Assert.That(first.Next(), Is.EqualTo(second.Next()));
			Assert.That(first.Next(), Is.EqualTo(second.Next()));
		}

		const string ValidSpecification = """
			{
			  "schemaVersion": "1.0.0",
			  "modId": "ra",
			  "mapUid": "example-map",
			  "randomSeed": 123456,
			  "options": { "gamespeed": "fastest" },
			  "players": [
			    {
			      "slot": "Multi0",
			      "botType": "strategic",
			      "faction": "Random",
			      "color": "F50606",
			      "spawnPoint": 1,
			      "team": 1,
			      "handicap": 0
			    },
			    {
			      "slot": "Multi1",
			      "botType": "normal",
			      "faction": "Random",
			      "color": "280DF6",
			      "spawnPoint": 2,
			      "team": 2,
			      "handicap": 0
			    }
			  ],
			  "maxWorldTicks": 90000,
			  "recordReplay": true
			}
			""";

		[TestCase(TestName = "Automated match specification parses the canonical shape")]
		public void ParsesCanonicalSpecification()
		{
			var specification = AutomatedMatchSpecification.Parse(ValidSpecification, "test.json");

			Assert.That(specification.SchemaVersion, Is.EqualTo("1.0.0"));
			Assert.That(specification.ModId, Is.EqualTo("ra"));
			Assert.That(specification.RandomSeed, Is.EqualTo(123456));
			Assert.That(specification.Players, Has.Count.EqualTo(2));
			Assert.That(specification.Players[0].BotType, Is.EqualTo("strategic"));
			Assert.That(specification.MaxWorldTicks, Is.EqualTo(90000));
			Assert.That(specification.EffectiveExecutionMode, Is.EqualTo("PACED"));
			Assert.That(
				new AutomatedMatchRunner.MatchResult().SchemaVersion,
				Is.EqualTo(AutomatedMatchSpecification.CurrentSchemaVersion));
		}

		[TestCase("PACED")]
		[TestCase("UNCAPPED")]
		public void ParsesVersionOnePointOneExecutionModes(string executionMode)
		{
			var json = ValidSpecification
				.Replace("\"schemaVersion\": \"1.0.0\"", "\"schemaVersion\": \"1.1.0\"")
				.Replace("\"recordReplay\": true", $"\"recordReplay\": true, \"executionMode\": \"{executionMode}\"");

			var specification = AutomatedMatchSpecification.Parse(json, "test.json");
			Assert.That(specification.EffectiveExecutionMode, Is.EqualTo(executionMode));
		}

		[TestCase(TestName = "Version 1.2 accepts one strongly typed candidate path")]
		public void VersionOnePointTwoAcceptsCandidatePath()
		{
			var json = ValidSpecification
				.Replace("\"schemaVersion\": \"1.0.0\"", "\"schemaVersion\": \"1.2.0\"")
				.Replace("\"recordReplay\": true", "\"recordReplay\": true, \"executionMode\": \"UNCAPPED\", \"candidatePath\": \"candidate.json\"");

			var specification = AutomatedMatchSpecification.Parse(json, "test.json");
			Assert.That(specification.CandidatePath, Is.EqualTo("candidate.json"));
		}

		[TestCase(TestName = "StrategicAI candidate contract is strict and bounded")]
		public void CandidateContractIsStrictAndBounded()
		{
			const string ValidCandidate = """
				{ "schemaVersion": "1.0.0", "candidateId": "squad-size-20", "squadSize": 20, "notes": "grid" }
				""";
			var candidate = StrategicAiCandidate.Parse(ValidCandidate, "candidate.json");
			Assert.That(candidate.CandidateId, Is.EqualTo("squad-size-20"));
			Assert.That(candidate.SquadSize, Is.EqualTo(20));

			Assert.That(
				() => StrategicAiCandidate.Parse(ValidCandidate.Replace("20,", "0,"), "candidate.json"),
				Throws.TypeOf<InvalidDataException>().With.Message.Contains("1..1000"));
			Assert.That(
				() => StrategicAiCandidate.Parse(ValidCandidate.Replace(" }", ", \"extra\": true }"), "candidate.json"),
				Throws.TypeOf<InvalidDataException>());
		}

		[TestCase(TestName = "Version 1.1 requires an explicit execution mode")]
		public void VersionOnePointOneRequiresExecutionMode()
		{
			var json = ValidSpecification.Replace("\"schemaVersion\": \"1.0.0\"", "\"schemaVersion\": \"1.1.0\"");

			Assert.That(
				() => AutomatedMatchSpecification.Parse(json, "test.json"),
				Throws.TypeOf<InvalidDataException>().With.Message.Contains("executionMode"));
		}

		[TestCase(TestName = "Automated match specification rejects unknown properties")]
		public void RejectsUnknownProperty()
		{
			var json = ValidSpecification.Replace(
				"\"recordReplay\": true",
				"\"recordReplay\": true, \"unexpected\": true");

			Assert.That(
				() => AutomatedMatchSpecification.Parse(json, "test.json"),
				Throws.TypeOf<InvalidDataException>());
		}

		[TestCase(TestName = "Automated match specification rejects duplicate slots")]
		public void RejectsDuplicateSlots()
		{
			var json = ValidSpecification.Replace("\"slot\": \"Multi1\"", "\"slot\": \"Multi0\"");

			Assert.That(
				() => AutomatedMatchSpecification.Parse(json, "test.json"),
				Throws.TypeOf<InvalidDataException>()
					.With.Message.Contains("uses slot 'Multi0' more than once"));
		}

		[TestCase(TestName = "Automated match specification requires replay recording in version 1")]
		public void RequiresReplayRecording()
		{
			var json = ValidSpecification.Replace("\"recordReplay\": true", "\"recordReplay\": false");

			Assert.That(
				() => AutomatedMatchSpecification.Parse(json, "test.json"),
				Throws.TypeOf<InvalidDataException>()
					.With.Message.Contains("must enable recordReplay"));
		}

		[TestCase(TestName = "Launch arguments expose the automated match entry point")]
		public void LaunchArgumentsExposeMatch()
		{
			var launch = new LaunchArguments(new Arguments(["Launch.Match=match.json"]));

			Assert.That(launch.Match, Is.EqualTo("match.json"));
		}

		[TestCase(TestName = "Launch arguments expose the replay verification entry point")]
		public void LaunchArgumentsExposeReplayVerification()
		{
			var launch = new LaunchArguments(new Arguments(["Launch.VerifyReplay=match.orarep"]));

			Assert.That(launch.VerifyReplay, Is.EqualTo("match.orarep"));
		}

		[TestCase("Launch.Match=match.json", "Launch.VerifyReplay=match.orarep")]
		[TestCase("Launch.Match=match.json", "Launch.Connect=127.0.0.1:1234")]
		[TestCase("Launch.VerifyReplay=match.orarep", "Launch.Replay=match.orarep")]
		[TestCase("Launch.VerifyReplay=match.orarep", "Launch.Map=example")]
		public void AutomatedEntryPointsRejectConflictingArguments(string first, string second)
		{
			var launch = new LaunchArguments(new Arguments([first, second]));

			Assert.That(launch.ValidateAutomatedEntryPoints, Throws.TypeOf<System.ArgumentException>());
		}
	}
}
