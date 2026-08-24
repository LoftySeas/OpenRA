# AI C# File Layout

## Goal
Define the production code organization for OpenRA AI extension.

## Proposed Structure

OpenRA.AI/
- NeuralCommander/
  - NeuralCommander.cs
  - DecisionCycle.cs
  - StrategyState.cs
- StateProvider/
  - IStateProvider.cs
  - WorldStateProvider.cs
  - FeatureEncoder.cs
- ActionSystem/
  - IActionExecutor.cs
  - ActionDecoder.cs
  - ActionMask.cs
- Runtime/
  - ModelRuntime.cs
  - ModelLoader.cs
- Training/
  - TrainerBridge.cs
  - EpisodeRecorder.cs

## Design Rule
Keep engine interaction separate from learning logic.