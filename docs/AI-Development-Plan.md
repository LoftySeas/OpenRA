# OpenRA AI Development Plan

## Goal
Build a human-like RTS commander AI while preserving OpenRA deterministic execution.

## Phase 1: Observation Platform

- export game state
- build simulation runner
- collect replays and results

## Phase 2: Existing AI Optimization

Use evolution methods:

- CMA-ES
- genetic algorithms

Optimize:

- build priorities
- attack timing
- unit ratios
- expansion behavior

## Phase 3: Neural Commander

Replace selected strategic heuristics with learned policies.

Input:

- state vector
- enemy belief
- historical context

Output:

- macro strategic actions

## Phase 4: Self Play

Maintain:

- current best models
- historical opponents
- scripted personalities

## Phase 5: Production

- model deployment
- difficulty presets
- regression testing
