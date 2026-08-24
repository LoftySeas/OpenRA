# AI Failure Analysis

## Common Problems

## Reward Hacking

Symptom:

AI maximizes score but loses games.

Solution:

- increase win reward
- reduce auxiliary rewards

## Overfitting

Symptom:

AI only wins one map or one opponent.

Solution:

- random maps
- opponent pool
- hidden validation maps

## Strategy Collapse

Symptom:

All AI generations become identical.

Solution:

- MAP-Elites
- personality preservation
- diversity reward

## Debugging

Always record:

- decisions
- state features
- reward changes
- game replay
