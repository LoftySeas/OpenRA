# AI Data Pipeline

## Overview

The training system requires a complete pipeline from game simulation to model improvement.

```
OpenRA Simulation
      |
State Recorder
      |
Replay / Dataset
      |
Feature Encoder
      |
Training Algorithm
      |
Model Registry
```

## Data Types

### Online Data

Collected during training:

- observation vectors
- chosen actions
- game result
- resource timeline
- combat statistics

### Offline Data

Generated from:

- human replays
- scripted bots
- previous AI generations

## Dataset Versioning

Every dataset should record:

- map version
- mod version
- random seed
- AI version
- feature schema version

This prevents invalid comparisons.
