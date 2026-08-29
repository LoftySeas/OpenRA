// Exposes internals to the OpenRA.Test assembly so the M1 end-to-end
// test fixture can drive the production evaluation and dispatch
// logic without spinning up a real World. The visible members are
// limited to the production test seams (FindAttackController on
// StrategicActionExecutor, FindEnabledAttackController on
// StrategicStateProvider, EvaluateDecision on the commander).
//
// OpenRA.AI also sees the internals so the commander can reuse
// the same PickEnabledAttackController selection rule as the
// state provider instead of re-deriving it inline.
[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("OpenRA.Test")]
[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("OpenRA.AI")]
