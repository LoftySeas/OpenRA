# OpenRA AI Mod Integration

## Goal

Describe how to integrate the neural RTS AI system without breaking the original OpenRA AI.

## Principles

- Keep original BotModule execution system.
- Add NeuralCommander as a strategic decision layer.
- Use existing Actor, World and Player APIs for state extraction.

## Integration Flow

World Tick -> AI State Collector -> NeuralCommander -> Strategic Action -> Existing Bot Modules -> Game Commands

## Recommended Modules

NeuralCommanderModule
- Owns strategic decisions.
- Runs every strategic interval.
- Does not control individual units directly.

StateCollectorModule
- Exports economy, military, map and threat features.

TrainingBridgeModule
- Sends observations and receives actions during training.

## Development Order

1. Add telemetry only.
2. Add rule based strategic replacement.
3. Add evolutionary optimization.
4. Add neural policy.
