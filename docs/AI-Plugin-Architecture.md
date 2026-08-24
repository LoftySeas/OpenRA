# AI Plugin Architecture

## Goal
Create a replaceable AI framework without modifying core engine logic.

## Modules
- State Provider
- Neural Commander
- Rule Executor
- Trainer Bridge
- Evaluator

## Runtime Flow
OpenRA Engine -> AI Plugin -> Decision -> Command Queue -> Engine

## Benefits
- Multiple AI implementations
- Easy experimentation
- Safe separation from original game code