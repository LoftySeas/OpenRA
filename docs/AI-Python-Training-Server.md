# OpenRA AI Python Training Server

## Goal

Separate game simulation from optimization.

Architecture:

```
Python Trainer
 |
 | actions / parameters
 v
OpenRA Headless Server
 |
 | result statistics
 v
Fitness Evaluator
```

## Components

### Environment Runner

Responsibilities:

- launch OpenRA
- load map
- select players
- run without rendering
- collect results

### Trainer

Supported algorithms:

- CMA-ES
- Evolution Strategy
- NEAT
- PPO (future)

## Simulation protocol

Messages:

Observation:

```json
{
  "money":5000,
  "army":3000,
  "enemy_estimate":2000
}
```

Action:

```json
{
  "type":"ATTACK",
  "target":5
}
```

## Parallel training

Recommended:

```
Worker 1 -> OpenRA instance
Worker 2 -> OpenRA instance
Worker 3 -> OpenRA instance
...

Trainer aggregates fitness
```

## Training stages

### Stage 1

Optimize YAML parameters.

### Stage 2

Optimize neural weights.

### Stage 3

Self-play population training.

## Hardware target

Personal workstation:

- 8-16 CPU cores
- 32GB RAM
- RTX 3060 or better

CPU simulation speed is more important than GPU.
