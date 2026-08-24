# OpenRA AI Implementation Architecture

## Purpose
Define the engineering boundary between OpenRA and learning systems.

## Runtime

```
OpenRA World
    |
State Provider
    |
State Encoder
    |
Neural Commander
    |
Action Decoder
    |
Existing Bot Modules
    |
Game Commands
```

## Components

### State Provider
Collects legal observable game information.

### Neural Commander
Selects strategic intent only.

### Action Decoder
Converts macro actions into existing OpenRA systems.

### Trainer Bridge
Supports offline simulation and model training.

## Rules

- Do not replace path finding.
- Do not expose hidden information.
- Do not control every unit directly.
- Keep execution deterministic.

## Implementation Order

1. State export
2. Fake commander
3. Action execution
4. Model inference
5. Training integration
