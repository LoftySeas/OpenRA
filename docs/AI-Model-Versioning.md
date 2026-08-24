# AI Model Versioning

## Goals
Manage trained RTS AI models reproducibly.

## Model Record

Each model should store:

- model id
- generation
- algorithm
- training scenarios
- opponent pool
- fitness score
- Elo rating
- behavior profile

## Checkpoints

Save:

- neural weights
- optimizer state
- random seeds
- configuration
- evaluation results

## Promotion Flow

```
Candidate
   |
Training evaluation
   |
Validation maps
   |
Human play test
   |
AI archive
```

Never replace the best model without validation.
