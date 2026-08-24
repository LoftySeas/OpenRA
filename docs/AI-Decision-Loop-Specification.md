# AI Decision Loop Specification

## Purpose
Define when and why the NeuralCommander makes decisions.

## Decision Layers

### Strategic Loop
Interval: 2-10 seconds depending on game phase.

Handles:
- expansion
- technology
- production priorities
- attack timing

### Tactical Loop
Interval: 0.2-1 second.

Handles:
- squad movement
- target selection
- retreat

### Event Interrupts
Immediate decision triggers:
- base attacked
- critical building destroyed
- enemy super weapon detected
- resource collapse

## Decision Flow

```
World Update
    |
Event Collector
    |
State Encoder
    |
NeuralCommander
    |
Action Mask
    |
Command Executor
```

## Design Rule
The AI should think less frequently than units execute actions. Strategic reasoning and execution must remain separated.
