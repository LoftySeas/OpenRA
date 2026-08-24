# AI Multi Agent Control

## Objective
Control squads instead of individual units.

## Hierarchy

Commander AI
 -> Squad Manager
 -> Unit Controller

## Squad Roles

- Assault group
- Defense group
- Support group
- Scout group
- Harassment group

## Learning Scope

Machine learning decides:
- formation intent
- target priority
- retreat timing
- coordination

Engine rules handle:
- pathfinding
- collision
- weapon execution
- movement commands

This keeps the AI stable and debuggable.