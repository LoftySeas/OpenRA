# AI Event System

## Purpose
Define how OpenRA gameplay events drive AI decisions.

## Event Sources
- UnitCreated
- UnitDestroyed
- BuildingCompleted
- BaseUnderAttack
- ResourceChanged
- EnemySpotted
- TechnologyUnlocked

## Architecture
World Event -> Event Bus -> Memory Update -> Neural Commander -> Action Queue

## Principles
- Events update belief state rather than directly forcing actions.
- High priority events interrupt normal planning.
- Strategic decisions remain separated from execution.