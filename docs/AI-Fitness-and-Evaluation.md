# AI Fitness and Evaluation System

## Objective

Measure AI strength without encouraging cheating behavior.

## Fitness formula

```
Fitness =
 WinScore
 + EconomyScore
 + CombatScore
 + MapControlScore
 - AbusePenalty
```

## Win score

Highest priority:

- victory: +1
- draw: 0
- defeat: -1

## Economy score

Measure:

- resource efficiency
- unused income
- expansion quality

Avoid rewarding infinite economy growth.

## Combat score

Use:

- damage dealt
- army preservation
- valuable unit protection

## Robust evaluation

Every AI version should play:

- multiple maps
- different starting positions
- multiple opponents
- historical AI versions

## Avoid overfitting

Maintain hidden validation scenarios.

Training maps must not equal final evaluation maps.

## Ranking

Recommended:

- Elo rating
- TrueSkill
- win rate confidence interval

Store every successful AI checkpoint.
