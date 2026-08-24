// Exposes internals to the OpenRA.Test assembly so focused unit tests can exercise
// helpers (e.g. FluentProvider.BuildLanguagePaths) without going through full Manifest
// or Map construction. Keep this list minimal - only test assemblies that genuinely
// need to reach into the implementation should be listed.
[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("OpenRA.Test")]
