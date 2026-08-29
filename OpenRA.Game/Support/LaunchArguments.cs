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
using OpenRA.Network;

namespace OpenRA
{
	public class LaunchArguments
	{
		[Desc("Connect to the following server given as IP:PORT on startup.")]
		public string Connect;

		[Desc("Connect to the unified resource identifier openra://IP:PORT on startup.")]
		public string URI;

		[Desc("Automatically start playing the given replay file.")]
		public string Replay;

		[Desc("Dump performance data into cpu.csv and render.csv in the logs folder with the given prefix.")]
		public string Benchmark;

		[Desc("Automatically start playing the given map.")]
		public string Map;

		[Desc("Automatically run the local match described by the given JSON specification.")]
		public string Match;

		[Desc("Automatically verify the given replay and write a machine-readable result.")]
		public string VerifyReplay;

		public LaunchArguments(Arguments args)
		{
			if (args == null)
				return;

			foreach (var f in GetType().GetFields())
				if (args.Contains("Launch." + f.Name))
					FieldLoader.LoadFieldOrProperty(this, f.Name, args.GetValue("Launch." + f.Name, ""));
		}

		public ConnectionTarget GetConnectEndPoint()
		{
			try
			{
				Uri uri;
				if (!string.IsNullOrEmpty(URI))
					uri = new Uri(URI);
				else if (!string.IsNullOrEmpty(Connect))
					uri = new Uri("tcp://" + Connect);
				else
					return null;

				if (uri.IsAbsoluteUri)
					return new ConnectionTarget(uri.Host, uri.Port);
				else
					return null;
			}
			catch (Exception ex)
			{
				Log.Write("client", $"Failed to parse Launch.URI or Launch.Connect: {ex.Message}");
				return null;
			}
		}

		public void ValidateAutomatedEntryPoints()
		{
			var hasConnection = !string.IsNullOrEmpty(Connect) || !string.IsNullOrEmpty(URI);
			if (!string.IsNullOrEmpty(Match) &&
				(hasConnection || !string.IsNullOrEmpty(Map) || !string.IsNullOrEmpty(Replay) || !string.IsNullOrEmpty(VerifyReplay)))
				throw new ArgumentException(
					"Launch.Match cannot be combined with Launch.Connect, Launch.URI, Launch.Map, Launch.Replay, or Launch.VerifyReplay.");

			if (!string.IsNullOrEmpty(VerifyReplay) &&
				(hasConnection || !string.IsNullOrEmpty(Map) || !string.IsNullOrEmpty(Replay)))
				throw new ArgumentException(
					"Launch.VerifyReplay cannot be combined with Launch.Connect, Launch.URI, Launch.Map, or Launch.Replay.");
		}
	}
}
