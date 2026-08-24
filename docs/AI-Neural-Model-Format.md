# AI Neural Model Format

## Training Format

Recommended:

- PyTorch checkpoint during research.
- ONNX for runtime deployment.

## Conversion

PyTorch -> ONNX -> C# ONNX Runtime

## Requirements

- Fixed input schema.
- Versioned model metadata.
- Compatible action space.
