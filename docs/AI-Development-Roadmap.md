# OpenRA Neural AI Development Roadmap

## Phase 1: Observation

Create tools for exporting:

- game state
- actions
- replay information
- match results

## Phase 2: Parameter Evolution

Convert existing BotModule settings into genes.

Examples:

- attack timing
- building weights
- unit ratios
- expansion preference

Use CMA-ES or genetic algorithms.

## Phase 3: Neural Commander

Replace fixed strategic rules with a neural policy.

Input:

```
state vector
```

Output:

```
macro strategic action
```

## Phase 4: Self Play

Maintain an opponent archive:

- current best AI
- previous generations
- scripted personalities

## Phase 5: AI Personalities

Use MAP-Elites or behavior descriptors to create:

- rush AI
- turtle AI
- economic AI
- adaptive AI

## Long Term Goal

Create a commander AI that plays like a human rather than simply maximizing combat power.
