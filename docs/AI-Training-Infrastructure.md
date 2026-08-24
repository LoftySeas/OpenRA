# OpenRA AI Training Infrastructure

## Goal

Build a reproducible environment for evolutionary algorithms and neural training.

## Headless Simulation

Training mode should:

- disable rendering
- accelerate game ticks
- fix random seeds
- automatically start matches
- export results

## Components

```
OpenRA Engine
      |
Simulation Runner
      |
Fitness Collector
      |
Evolution Controller
      |
Model Storage
```

## Training Loop

```
Generate candidates
        |
Run thousands of matches
        |
Calculate fitness
        |
Select better policies
        |
Mutate / update model
```

## Recommended Algorithms

### Stage 1

CMA-ES for tuning existing AI parameters.

### Stage 2

Evolution Strategies for small neural networks.

### Stage 3

Self-play with historical opponents.

## Fitness Metrics

Primary:

- win rate
- survival

Secondary:

- economy efficiency
- map control
- army efficiency
- strategic diversity

## Hardware Target

Personal workstation is sufficient when simulations are accelerated and parallelized.
