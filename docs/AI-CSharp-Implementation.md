# OpenRA Neural AI C# Implementation Guide

## Purpose

This document defines the engineering design for integrating a learning-based strategic AI into OpenRA while preserving the existing ModularBot system.

## Design principle

Do not replace the RTS engine with a neural network. Keep:

- Actor system
- Path finding
- Combat execution
- Building legality
- Resource harvesting
- Squad movement

Replace only high-level decisions.

Architecture:

```
World
 |
StateCollector
 |
StateEncoder
 |
NeuralCommander
 |
ActionPlanner
 |
Existing Bot Modules
```

## Proposed namespaces

```
OpenRA.Mods.Common.AI.Neural
```

Classes:

```csharp
NeuralBotController
NeuralCommander
AIStateCollector
AIStateEncoder
AIActionDecoder
AIModelLoader
```

## NeuralBotController

Responsibilities:

- lifecycle management
- decision timing
- communication with ModularBot

Example:

```csharp
class NeuralBotController
{
    Tick()
    {
        if (ShouldDecide())
        {
            var state = collector.Collect();
            var vector = encoder.Encode(state);
            var action = commander.Decide(vector);
            decoder.Execute(action);
        }
    }
}
```

## Decision frequency

Recommended:

- strategic decisions: every 2-5 seconds
- emergency response: immediate
- tactical commands: delegated

## StateCollector

Collect:

- economy
- army value
- technology
- map control
- enemy memory
- threat level

Never expose hidden enemy information.

## ActionDecoder

The neural network should output:

```
ATTACK
DEFEND
EXPAND
TECH
HARASS
PRODUCE
SCOUT
```

The decoder converts these into OpenRA commands.

## Model format

Recommended:

Phase 1:
JSON weights

Phase 2:
ONNX runtime

Phase 3:
custom inference backend

## Development order

1. Export game state
2. Replay state/action pairs
3. Implement fake neural commander
4. Connect real inference
5. Add evolutionary training
