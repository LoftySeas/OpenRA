# AI Simulation Runner

## Purpose
Provide automated headless RTS simulation for training.

## Components

- Game launcher
- Scenario loader
- Worker process
- Match controller
- Result collector

## Pipeline

1. Start OpenRA headless instance.
2. Load map and AI agents.
3. Run accelerated simulation.
4. Collect statistics.
5. Return fitness score.

## Parallel Training

Multiple workers can evaluate different policies simultaneously.
