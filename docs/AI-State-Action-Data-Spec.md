# OpenRA AI State Action Data Specification

## Purpose

Single source of truth for AI observations, actions and rewards.

## Observation

The model consumes aggregated state, not raw actors.

Categories:

- Economy: credits, income, harvesters, production capacity
- Military: unit value, composition, health, position
- Technology: available production and upgrades
- Map: control, resources, threats
- Enemy belief: last seen position, estimated strength, confidence

## Action

Actions are hierarchical macro decisions:

- ATTACK
- DEFEND
- EXPAND
- TECH
- HARASS
- SCOUT
- CHANGE_PRODUCTION

Each action contains:

- action type
- target region
- priority
- confidence
- duration

## Reward

Primary:

- victory
- defeat

Secondary:

- economy efficiency
- army efficiency
- map control
- objective progress

Avoid rewards that encourage farming statistics instead of winning games.

## Versioning

Schema changes require a version update.