# Dataset Generation Suite

This folder contains a small, readable suite for generating datasets of:
- schedules
- contrastive queries
- SAT knowledge bases (KBs) for each encoded schedule

The outputs are intended to be used with `explainer.py` and the SAT-based
explanation pipeline.

## Quick start

```bash
python /Users/mithrandir/Desktop/Code/trace-cs/dataset_generation/generate_datasets.py \
  --output-dir /Users/mithrandir/Desktop/Code/trace-cs/datasets \
  --variations 3 \
  --semesters 2,4,6 \
  --max-schedules 5 \
  --complexity-levels 1,2,4,6 \
  --queries-per-complexity 3 \
  --seed 42
```

## Output structure

```
datasets/
  manifest.json
  inputs/
    input_sem4_var0.json
  schedules/
    sem4_var0_sch0.json
  kbs/
    kb_sem4_var0_sch0.json
```

### `manifest.json`
Contains dataset-level metadata and a list of generated schedules with paths.

### `schedules/*.json`
Each schedule file contains:
- `schedule_id`
- `schedule` (list of semesters)
- `schedule_true_literals` (unit literals that encode the schedule)
- `queries` (query texts + structured items)

### `kbs/*.json`
Each KB file contains:
- `kb_clauses`: the full KB for the encoded schedule (base constraints + schedule)
- `schedule_unit_clauses`: the unit clauses encoding the schedule
- `vpool_mapping` and `course_index_map` for interpretability

## Notes

- The schedule KB is constructed from `scheduler.cnf.hard + scheduler.cnf.soft`
  plus the schedule-specific unit clauses.
- Query generation is randomized but reproducible via `--seed`.

## Run experiments on datasets

Use the generated datasets directly with the explainer algorithms:

```bash
python /Users/mithrandir/Desktop/Code/trace-cs/dataset_generation/run_experiments_on_datasets.py \
  --manifest /Users/mithrandir/Desktop/Code/trace-cs/datasets/manifest.json \
  --output /Users/mithrandir/Desktop/Code/trace-cs/datasets/experiment_results.json \
  --max-schedules 1 \
  --max-queries 2
```

To also call the LLM post-processor (requires API key configured):

```bash
python /Users/mithrandir/Desktop/Code/trace-cs/dataset_generation/run_experiments_on_datasets.py \
  --post-process
```

Use the saved KB + templates:

```bash
python /Users/mithrandir/Desktop/Code/trace-cs/dataset_generation/run_experiments_on_datasets.py \
  --use-saved-kb
```

Note: This requires datasets generated after the templates were added to KB exports.
