# AI Message Schema

Defines communication messages between simulation and trainer.

## Observation

Contains:
- timestamp
- player state
- resources
- army composition
- map features
- enemy belief state

## Action

Contains:
- action type
- target region
- priority
- duration

## Reward

Contains:
- win result
- economic score
- combat score
- map control
- penalties
