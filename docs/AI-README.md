# OpenRA Neural RTS AI Framework

## Purpose

This document is the entry point for the OpenRA AI research and implementation documentation.

The goal is to add a learning-based strategic commander while keeping the deterministic RTS engine.

Core principle:

> Neural AI decides strategic intent. OpenRA systems execute actions safely.

## Architecture

```
Game World
    |
State Provider
    |
State Encoder
    |
Neural Commander
    |
Action Decoder
    |
OpenRA Bot Modules
    |
Squad / Unit Controllers
```

## Reading Order

1. Architecture
   - AI-Architecture-Design
   - AI-OpenRA-Code-Integration-Map
   - AI-NeuralCommander-Spec

2. Data Contracts
   - AI-State-Action-Reward-Schema
   - AI-API-Protocol
   - AI-Interface-Contracts

3. Training
   - AI-Training-Infrastructure
   - AI-Experiment-Framework
   - AI-SelfPlay-System

4. Engineering
   - AI-CSharp-Implementation
   - AI-Deployment-Architecture

## Development Strategy

Phase 1:
- Export OpenRA state
- Build simulation runner
- Evaluate scripted AI

Phase 2:
- Optimize existing AI parameters
- Introduce CMA-ES

Phase 3:
- Add NeuralCommander
- Train strategic policies

Phase 4:
- Self-play league
- AI personalities
- Continuous improvement
