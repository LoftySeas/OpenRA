# AI Performance Optimization

## Training Bottleneck

For RTS AI, simulation speed matters more than neural network size.

## Optimization Targets

### Headless Mode

Disable rendering and audio.

### Parallel Simulation

Run many independent games:

- one process per match
- shared model weights
- asynchronous evaluation

### Deterministic Simulation

Use fixed seeds for comparison.

### Caching

Cache:

- map analysis
- navigation data
- static unit information

## Goal

A personal workstation should be able to run thousands of accelerated matches.
