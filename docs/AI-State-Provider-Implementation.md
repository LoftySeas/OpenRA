# AI State Provider Implementation

## Purpose
Define how OpenRA runtime state is converted into AI observations.

## Responsibilities
- Collect World, Player, Actor information
- Normalize RTS features
- Maintain feature cache
- Provide deterministic snapshots for training

## Data Flow
World -> StateProvider -> FeatureEncoder -> NeuralCommander

## Core Components
- StateProvider
- ActorScanner
- ResourceTracker
- CombatAnalyzer
- MapControlAnalyzer

## Design Rules
- No hidden information leakage
- Same interface for training and runtime
- Version feature schema
