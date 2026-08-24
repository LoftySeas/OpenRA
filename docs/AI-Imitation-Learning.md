# AI Imitation Learning

## Goal
Learn RTS behavior from human replay data.

## Pipeline
Replay -> State Extraction -> Action Labels -> Behavior Cloning -> Fine Tuning

## Uses
- human-like build orders
- player style learning
- initial policy before self-play

## Hybrid Approach
Use imitation learning for initialization, then use evolution or reinforcement learning for improvement.
