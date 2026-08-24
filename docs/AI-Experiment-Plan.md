# OpenRA AI Experiment Plan

## Objective

Create reproducible AI experiments instead of manually tuning bots.

## Experiment phases

### Phase 1
Baseline comparison.

Compare:
- OpenRA scripted bots
- parameter optimized bots
- neural commander bots

### Phase 2
Evolution experiments.

Algorithms:
- CMA-ES
- Evolution Strategies
- NEAT

Measure:
- win rate
- economy efficiency
- army efficiency
- stability

## Benchmark maps

Maintain fixed sets:

- small rush maps
- expansion maps
- defensive maps
- naval maps
- asymmetric maps

## Experiment record

Each run stores:

```
experiment_id
model_version
algorithm
hyperparameters
maps
opponents
fitness
runtime
hardware
```

## Reproducibility

Always record:

- random seed
- OpenRA commit
- mod version
- AI model hash
- configuration

## Success criteria

A good AI should not only win.

It should:

- adapt to opponents
- show different strategies
- avoid obvious cheating
- scale difficulty
- remain understandable to players
