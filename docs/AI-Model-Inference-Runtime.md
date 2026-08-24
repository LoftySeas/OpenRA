# AI Model Inference Runtime

## Purpose
Deploy trained models inside OpenRA.

## Architecture
ONNX Model -> Runtime Wrapper -> NeuralCommander

## Requirements
- Fast inference
- Model hot reload
- CPU compatibility
- Deterministic execution

## Deployment Flow
Training checkpoint -> Export -> Validation -> Runtime package
