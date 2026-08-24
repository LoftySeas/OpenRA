# Neural Network Design for OpenRA AI

## Goal

Design a compact strategic network suitable for personal GPU training.

## Network architecture

Recommended first version:

```
Feature Vector
      |
  Dense 256
      |
  Dense 128
      |
  GRU 64(optional)
      |
  Multiple Action Heads
```

## Input features

Categories:

### Economy
- money
- income rate
- harvester count
- refinery count
- unused resources

### Military
- infantry value
- vehicle value
- air value
- defense value

### Technology
- tech level
- available production
- special weapons

### Map
- resource control
- threat map
- enemy last known position

## Output heads

Strategic action:

```
ATTACK
DEFEND
EXPAND
TECH
HARASS
SAVE
```

Target:

```
region id
```

Intensity:

```
low / medium / high
```

## Deployment

Recommended export:

```
PyTorch training
        |
        v
      ONNX
        |
        v
 OpenRA C# runtime
```

## Training priority

1. Economic decisions
2. Build order
3. Army composition
4. Attack timing
5. Tactical micro

Do not start with pixel input or unit-level control.
