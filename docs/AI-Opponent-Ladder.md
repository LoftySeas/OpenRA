# AI Opponent Ladder

## Goal

Maintain a population of AI opponents instead of only training against the newest model.

## Structure

```
Beginner Script AI
       |
Intermediate Neural AI
       |
Current Champion
       |
Historical Champions
       |
Specialized Counter AI
```

## Rating

Use:

- Elo
- TrueSkill
- win rate matrix

## Selection

Training opponents should include:

- current strongest AI
- historical versions
- strategy counters
- scripted baselines

This avoids overfitting to one opponent.
