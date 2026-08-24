# AI Class Diagram

## Core Components

NeuralCommander
- Receives encoded world state.
- Produces strategic actions.

StateEncoder
- Converts OpenRA World/Player/Actor data into feature vectors.

ActionDecoder
- Converts abstract decisions into BotModule commands.

TrainingBridge
- Sends evaluation data to external trainers.

FitnessEvaluator
- Calculates win, economy, army and behavior scores.

## Data Flow

World -> StateEncoder -> NeuralCommander -> ActionDecoder -> OpenRA Modules

Trainer -> TrainingBridge -> Simulation -> FitnessEvaluator
