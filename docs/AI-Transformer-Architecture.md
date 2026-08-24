# AI Transformer Architecture

## Purpose
Explore Transformer based memory models for RTS AI.

## Motivation
RTS requires long horizon memory. A model should remember:
- enemy sightings
- economic trends
- previous battles
- opponent tendencies

## Architecture
State Encoder -> Tokenizer -> Transformer Encoder -> Policy Heads

Tokens may represent:
- map regions
- units
- buildings
- economy snapshots
- historical events

## Practical Roadmap
Start with MLP/GRU. Introduce Transformer only after reliable data pipelines exist.
