# AI Interface Contracts

Defines stable interfaces between OpenRA engine, AI modules, and training systems.

## Core interfaces

- IStateProvider: provides normalized observations.
- IActionExecutor: converts AI actions into engine commands.
- IModelRuntime: executes neural inference.
- ITrainerBridge: communicates with external training services.

## Design goals

- Keep engine logic independent from learning algorithms.
- Allow rule AI and neural AI to share execution components.
- Support offline simulation and live game execution.
