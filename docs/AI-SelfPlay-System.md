# OpenRA Self Play System

## Purpose

Create adaptive AI instead of one fixed opponent.

## Population

Maintain:

```
Current Champion
Historical Champions
Specialist Counter Bots
Scripted Baselines
```

## Match selection

Example:

```
40% current champion
30% historical versions
20% counter strategies
10% scripted AI
```

## Evolution loop

```
Generate candidates
        |
Play matches
        |
Calculate fitness
        |
Select survivors
        |
Mutate
        |
Repeat
```

## AI personality

Use behavior descriptors:

- aggression
- expansion rate
- technology preference
- air usage
- defense preference

Store multiple elites instead of one winner.

## MAP-Elites option

Maintain a library:

```
Fast Rush
Economic Turtle
Air Specialist
Naval Specialist
Harassment Expert
```

This improves gameplay variety.
