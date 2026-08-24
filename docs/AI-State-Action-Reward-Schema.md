# AI State Action Reward Schema

## Observation Schema

The model input must be a stable versioned structure.

Example:

```
Economy
- credits
- income_rate
- harvester_count
- refinery_count

Military
- infantry_value
- armor_value
- air_value
- army_health

Map
- controlled_regions
- resource_nodes
- threat_map

Enemy Belief
- last_seen_position
- estimated_strength
- confidence
```

## Action Schema

Macro actions:

```
ATTACK
DEFEND
EXPAND
TECH
HARASS
SAVE_RESOURCE
```

Each action contains:

```
type
target_region
priority
confidence
duration
```

## Reward Schema

Primary:

```
win: high weight
loss: strong negative
```

Secondary:

```
economy efficiency
army efficiency
map control
objective progress
```

Avoid rewarding only destruction statistics because it causes exploit behavior.
