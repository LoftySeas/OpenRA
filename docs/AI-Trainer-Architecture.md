# AI Trainer Architecture

Components:

- Environment Worker
- Self Play Manager
- Evaluator
- Population Manager
- Model Registry

Training flow:

Generate agents -> Run matches -> Calculate fitness -> Select -> Mutate -> Repeat.