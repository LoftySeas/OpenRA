# OpenRA AI Code Integration Map

## Source Inspection Notes

The repository separates core engine and mod-specific logic. The AI extension should avoid changing core simulation rules.

Observed structure:

```
OpenRA.Game
    Engine runtime

OpenRA.Mods.Common
    Shared gameplay utilities and reusable systems

OpenRA.Mods.Cnc / RA
    Mod-specific AI behavior
```

## Integration Strategy

Add a new AI layer:

```
Existing Bot System
        |
NeuralCommander Adapter
        |
State Provider
        |
Model Runtime
```

## Rules

- Keep path finding deterministic.
- Keep command execution inside existing systems.
- Only replace strategic decisions.
- Avoid direct neural control of every Actor.

The repository contains reusable AI-related utility areas under OpenRA.Mods.Common, which should be reused where possible rather than duplicated.
