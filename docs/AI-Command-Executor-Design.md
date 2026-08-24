# AI Command Executor Design

## Purpose
Convert high level AI decisions into safe OpenRA orders.

## Pipeline
Neural Action -> Action Decoder -> Validator -> OpenRA Order

## Responsibilities
- Check legality
- Prevent invalid commands
- Manage cooldowns
- Handle failures

## Example
ATTACK_REGION -> SquadManager -> AttackMove Orders

The executor keeps the neural model focused on strategy instead of engine details.
