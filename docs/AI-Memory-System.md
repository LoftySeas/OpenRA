# AI Memory System

## Goal
Provide RTS AI with temporal reasoning under fog of war.

## Layers
- Short term memory: recent combat and events
- Working memory: current objectives
- Long term memory: opponent patterns and historical matches

## Implementation Options
- GRU/LSTM hidden state
- Transformer attention memory
- Explicit belief state tables

## Enemy Belief
Store estimated position, strength, confidence and timestamp instead of perfect information.