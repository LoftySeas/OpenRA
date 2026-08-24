# OpenRA AI Data Model

## State Vector

The learning system should consume aggregated state rather than raw actors.

Example:

```
Economy
- credits
- income rate
- harvester count
- refinery count

Military
- infantry value
- armor value
- air value
- naval value

Technology
- tech level
- available production

Map
- resource control
- territory control
- enemy last seen position

Threat
- base danger
- army imbalance
- recent attacks
```

## Action Space

The neural model should output macro actions.

```
WAIT
BUILD_ECONOMY
TECH_UP
EXPAND
PRODUCE_ARMOR
PRODUCE_AIR
SCOUT
ATTACK
DEFEND
HARASS
RETREAT
```

## Decision Frequency

Strategic decisions should happen every few seconds, not every frame.

## Memory

Use historical features:

- previous enemy sightings
- income trend
- army trend
- previous attacks

A recurrent network can later replace manual memory features.
