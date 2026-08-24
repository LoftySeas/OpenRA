# OpenRA AI Codebase Map

## Purpose

This document maps the OpenRA source architecture to the Neural Commander AI project.

## Core integration points

```
World
 |
Player
 |
Bot Controller
 |
ModularBot Modules
 |
Neural Strategic Layer
 |
Existing execution modules
```

## Recommended insertion points

### NeuralBrain
Responsible for strategic decisions.

Input:
- economy state
- army strength
- enemy memory
- map control

Output:
- attack
- defend
- expand
- tech
- harassment

### StateEncoder
Converts OpenRA runtime objects into stable feature vectors.

Example:
```
Player -> economy features
Actor -> unit/building features
World -> map features
Combat -> threat features
```

### ActionDecoder
Converts neural decisions into existing BotModule requests.

The neural system should not directly control every Actor.

## Module ownership

Resource modules:
- harvesting
- economy

Base builder modules:
- construction
- production

Squad modules:
- movement
- combat grouping

Neural layer:
- long term strategy

## Development rule

Preserve OpenRA deterministic simulation.
The learning system should be a commander layer, not a replacement RTS engine.
