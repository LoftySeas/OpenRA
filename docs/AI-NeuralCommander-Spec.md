# NeuralCommander Specification

## Purpose
NeuralCommander is the strategic decision layer between OpenRA simulation state and existing BotModules.

## Responsibilities
- Decide macro goals
- Select strategic actions
- Allocate resources
- Choose attack, defense, expansion timing

## Input
- Economy state
- Military composition
- Enemy belief state
- Map control
- Technology progression

## Output
- Macro action
- Target region
- Priority
- Confidence

## Decision Cycle
Strategic decisions run every 0.5-5 seconds depending on game phase.

## Design Principle
The network does not control individual units. OpenRA modules execute actions safely.