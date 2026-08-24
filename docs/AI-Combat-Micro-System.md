# Combat Micro AI System

## Purpose

Design tactical AI after strategic AI is stable.

## Squad Level Control

Use squads instead of individual units.

Squad states:
- Assemble
- Attack
- Retreat
- Defend
- Harass

## Features

Input:
- Unit health
- Enemy composition
- Terrain
- Distance
- Threat map

Output:
- Focus target
- Formation
- Movement style
- Retreat decision

## Rule First

The engine should keep movement, collision and targeting legality.
The learned model selects tactical intent.
