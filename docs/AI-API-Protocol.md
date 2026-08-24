# OpenRA AI API Protocol Design

## Purpose
Define communication between OpenRA simulation and external training systems.

## Components

```
OpenRA Headless
      |
      | State packets
      v
Python Trainer
      |
      | Action packets
      v
OpenRA AI Controller
```

## State Packet

Recommended fields:

- timestamp
- player id
- resources
- income rate
- technology level
- buildings summary
- army value
- enemy observations
- map control
- squad status

## Action Packet

High level actions only:

- Attack(region)
- Defend(region)
- Expand(location)
- Research(technology)
- Produce(unit type)
- Scout(region)

## Design Rules

The protocol must avoid exposing hidden information and must keep the same observation limits as human players.

The interface should support both training and live inference.
