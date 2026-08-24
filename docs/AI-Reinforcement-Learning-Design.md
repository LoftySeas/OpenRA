# Reinforcement Learning Design

## Scope

RL is used only where long term adaptation is valuable.

## Recommended Usage

Good candidates:
- Strategic attack timing
- Expansion decisions
- Unit composition
- Tactical micro

Bad candidates:
- Pathfinding
- Building legality
- Resource accounting

## Algorithms

Early:
- CMA-ES
- Evolution Strategies

Advanced:
- PPO
- Multi-agent self play

## Reward

Primary reward:
- Win/Loss

Secondary:
- Economy efficiency
- Army value
- Map control
- Objective progress

Avoid reward hacking by reducing shaping rewards over time.
