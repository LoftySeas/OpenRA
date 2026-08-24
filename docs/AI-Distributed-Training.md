# Distributed Training

## Architecture

Trainer
 -> Workers
 -> Headless OpenRA simulations
 -> Fitness Collector

## Worker Responsibilities
- Load model
- Run games
- Return metrics

## Scaling
CPU cores scale simulation count. GPU is mainly used for neural inference/training.

## Goal
Support hundreds or thousands of parallel matches.