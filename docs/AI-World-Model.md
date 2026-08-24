# AI World Model

## Purpose
Maintain hidden state and uncertainty under RTS fog of war.

## Components

- Visible state encoder
- Enemy belief model
- Resource prediction
- Threat estimation
- Historical memory

## Model Options

Small systems:
- Feature history buffers
- GRU/LSTM

Advanced systems:
- Transformer memory
- Learned world simulation

## Belief State

The AI should store probabilities instead of assuming unknown information:

enemy_army_probability
enemy_tech_probability
enemy_expansion_probability

This enables human-like scouting and uncertainty handling.