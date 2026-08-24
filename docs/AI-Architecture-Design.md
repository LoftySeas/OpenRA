# OpenRA Neural RTS AI Architecture Design

## Goal

Design a hybrid AI system for OpenRA that keeps the deterministic RTS engine while adding a learning-based strategic commander.

## Principles

- Rules handle legality, path finding, construction and unit execution.
- Machine learning handles high-level decisions.
- Training must run headless and deterministic.

## Architecture

```
Game World
   |
State Encoder
   |
Neural Commander
   |
Action Decoder
   |
OpenRA Bot Modules
   |
Squad / Unit Controllers
```

## Components

### StateEncoder
Converts world state into numerical features:

- economy
- technology
- army composition
- map control
- enemy observations
- threats

Example output:

```
float[128]
```

### NeuralCommander
Controls:

- attack timing
- expansion decisions
- technology priorities
- production strategy
- risk preference

It does not issue direct unit commands.

### ActionDecoder
Maps strategic actions to existing OpenRA modules:

```
ATTACK -> SquadManager
EXPAND -> MCV expansion manager
TECH -> BaseBuilder
```

## C# Module Layout

```
OpenRA.Game/AI/NeuralBot/
    NeuralBrain.cs
    StateEncoder.cs
    ActionDecoder.cs
    FitnessEvaluator.cs
    TrainingInterface.cs
```

## Implementation Phases

1. Export game state.
2. Evaluate existing bots.
3. Evolve parameters.
4. Add neural strategic layer.
5. Add self-play training.
