# AI Repository Structure

## Goal
Define the recommended source tree for the OpenRA AI extension.

```
OpenRA.AI/
├── NeuralCommander/
├── StateEncoder/
├── ActionDecoder/
├── TrainingBridge/
├── SimulationRunner/
├── Evaluator/
├── Models/
└── Tools/
```

## Design Principles

- Keep the original RTS engine independent.
- Separate inference, training and evaluation.
- Allow rule based AI and neural AI to coexist.

## Runtime Flow

World State -> StateEncoder -> Neural Model -> ActionDecoder -> OpenRA Modules
