# AI Strategic Planning

## Goal
Design a hybrid symbolic + neural strategic layer for RTS AI.

## Architecture

Observation -> World Model -> Goal Selector -> Planner -> OpenRA Modules

## Goals
- Expand economy
- Defend base
- Destroy enemy technology
- Control map resources
- Prepare decisive attack

## Hybrid Approach

Neural network predicts priorities:
- attack timing
- risk tolerance
- technology preference
- expansion value

Symbolic planner ensures:
- legal actions
- resource constraints
- technology requirements

## Planning Methods

Supported approaches:
- Utility AI
- GOAP
- Behavior Trees
- Neural policy selection

The recommended OpenRA implementation keeps execution deterministic while allowing learning systems to select strategic intent.