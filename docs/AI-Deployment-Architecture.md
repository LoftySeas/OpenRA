# AI Deployment Architecture

## Goal
Describe how trained RTS AI models are packaged and executed inside OpenRA.

## Runtime Pipeline

```
ONNX Model
    |
ONNX Runtime / C# inference
    |
NeuralCommander
    |
OpenRA Bot Modules
    |
Actor Commands
```

## Deployment Rules

- Training environment and production environment must share the same observation encoder.
- The AI model only selects strategic decisions.
- Existing OpenRA systems handle movement, construction legality and combat execution.

## Model Package

Recommended package:

```
models/
  commander_v001.onnx
  metadata.json
  normalization.json
  action_schema.json
```

## Performance

Prefer CPU inference for small strategic networks. GPU acceleration is useful only for large experiments.
