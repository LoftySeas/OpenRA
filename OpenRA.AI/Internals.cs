// Exposes internals to the OpenRA.Test assembly so the M1 end-to-end
// test fixture can drive the production evaluation loop against
// synthetic state without spinning up a real World. The visible
// members are limited to the test seam (GetStateProvider,
// GetExecutor, GetWorldTick, GetIsReplay) and the internal
// EvaluateDecision entry point.
[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("OpenRA.Test")]
