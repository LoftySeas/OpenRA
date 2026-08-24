# AI Implementation Milestones

## Goal
Turn the OpenRA AI research design into an incremental engineering project.

## Milestone 1: Observation Layer
- Export game state snapshots.
- Define StateEncoder schema.
- Validate replay consistency.

## Milestone 2: Strategic Brain
- Add NeuralCommander interface.
- Keep existing BotModules as execution layer.
- Replace selected heuristic decisions.

## Milestone 3: Evolution Training
- Add CMA-ES parameter optimizer.
- Build headless battle evaluator.
- Track AI rating.

## Milestone 4: Neural Training
- Train strategic policy networks.
- Add self-play opponents.
- Store checkpoints.

## Milestone 5: Production
- Package models.
- Add difficulty presets.
- Maintain regression tests.
