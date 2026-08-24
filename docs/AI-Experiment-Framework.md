# AI Experiment Framework

## Experiment Levels

### Level 1: Parameter Optimization

Goal:
Improve existing scripted AI.

Methods:
- CMA-ES
- genetic algorithms

### Level 2: Strategic Neural AI

Goal:
Learn macro decisions.

Metrics:
- win rate
- economy
- map control
- robustness

### Level 3: Self Play

Goal:
Discover adaptive strategies.

## Experiment Record

Each run stores:

```
experiment_id
model_version
map_set
audience/opponents
algorithm
hyperparameters
results
analysis
```

## Reproducibility

Every experiment must record:

- random seed
- engine version
- mod version
- model checkpoint
