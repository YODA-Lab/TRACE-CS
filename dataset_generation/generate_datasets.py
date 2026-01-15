import argparse
import copy
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence


import sys
sys.path.append('/Users/mithrandir/Desktop/Code/trace-cs')
from scheduler import CourseScheduler

from dataset_generation.kb_export import (
    build_base_kb,
    build_course_index_map,
    build_vpool_mapping,
    export_kb_json,
)
from dataset_generation.queries import generate_queries


@dataclass
class DatasetConfig:
    output_dir: Path
    base_input_path: Path
    course_files: Dict[str, Path]
    variations: int
    semesters: Sequence[int]
    max_schedules: int
    complexity_levels: Sequence[int]
    queries_per_complexity: int
    seed: int


def _load_courses(course_files: Dict[str, Path]) -> List[str]:
    codes: List[str] = []
    for path in course_files.values():
        with path.open("r") as f:
            courses = json.load(f)
        codes.extend([course["code"] for course in courses])
    return codes


def _adjust_current_semester(user_input: Dict, current_semester: int) -> Dict:
    if not (1 <= current_semester <= 8):
        raise ValueError("current_semester must be between 1 and 8")

    updated = copy.deepcopy(user_input)
    updated["current_semester"] = current_semester
    updated["courses_taken"] = {
        k: v for k, v in updated["courses_taken"].items() if int(k) <= current_semester
    }
    return updated


def _mutate_user_input(
    base_input: Dict,
    rng: random.Random,
    course_codes: Sequence[str],
    variation_index: int,
) -> Dict:
    if variation_index == 0:
        return copy.deepcopy(base_input)

    variation = copy.deepcopy(base_input)

    # Replace a few taken courses in random semesters
    semesters = list(variation["courses_taken"].keys())
    for semester in rng.sample(semesters, k=min(2, len(semesters))):
        taken_courses = variation["courses_taken"][semester]
        for _ in range(min(2, len(taken_courses))):
            if not taken_courses:
                break
            course_to_replace = rng.choice(taken_courses)
            taken_courses.remove(course_to_replace)

            all_taken = [
                c for sem_courses in variation["courses_taken"].values() for c in sem_courses
            ]
            available = [c for c in course_codes if c not in all_taken]
            if available:
                taken_courses.append(rng.choice(available))

    # Add preferred courses with random weights
    variation["preferred_courses"] = {}
    num_preferred = rng.randint(2, 5)
    for _ in range(num_preferred):
        all_taken = [
            c for sem_courses in variation["courses_taken"].values() for c in sem_courses
        ]
        available = [
            c for c in course_codes if c not in all_taken and c not in variation["preferred_courses"]
        ]
        if available:
            course = rng.choice(available)
            variation["preferred_courses"][course] = rng.randint(1, 3)

    return variation


def _save_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _format_schedule_id(semester: int, variation_index: int, schedule_index: int) -> str:
    return f"sem{semester}_var{variation_index}_sch{schedule_index}"


def generate_datasets(config: DatasetConfig) -> None:
    rng = random.Random(config.seed)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with config.base_input_path.open("r") as f:
        base_input = json.load(f)

    course_codes = _load_courses(config.course_files)
    manifest = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "config": {
            "variations": config.variations,
            "semesters": list(config.semesters),
            "max_schedules": config.max_schedules,
            "complexity_levels": list(config.complexity_levels),
            "queries_per_complexity": config.queries_per_complexity,
            "seed": config.seed,
        },
        "inputs": [],
        "schedules": [],
    }

    for semester in config.semesters:
        for variation_index in range(config.variations):
            mutated_input = _mutate_user_input(base_input, rng, course_codes, variation_index)
            mutated_input = _adjust_current_semester(mutated_input, semester)
            mutated_input["max_schedule_count"] = config.max_schedules

            input_path = output_dir / "inputs" / f"input_sem{semester}_var{variation_index}.json"
            _save_json(input_path, mutated_input)
            manifest["inputs"].append(str(input_path))

            scheduler = CourseScheduler(
                str(config.course_files["core"]),
                str(config.course_files["methods"]),
                str(config.course_files["systems"]),
                str(config.course_files["cs_electives"]),
                str(config.course_files["sciences"]),
                str(config.course_files["social"]),
                str(input_path),
            )

            schedules, models, true_lits = scheduler.solve()
            if not schedules:
                continue

            base_kb = build_base_kb(scheduler)
            vpool_mapping = build_vpool_mapping(scheduler)
            course_index_map = build_course_index_map(scheduler)

            for schedule_index, schedule in enumerate(schedules[: config.max_schedules]):
                schedule_id = _format_schedule_id(
                    semester, variation_index, schedule_index
                )
                schedule_unit_clauses = [
                    list(clause) for clause in true_lits[schedule_index]
                ]
                schedule_literals = [clause[0] for clause in schedule_unit_clauses]

                queries = generate_queries(
                    scheduler=scheduler,
                    schedule=schedule,
                    rng=rng,
                    complexity_levels=config.complexity_levels,
                    queries_per_complexity=config.queries_per_complexity,
                )

                schedule_payload = {
                    "schedule_id": schedule_id,
                    "current_semester": scheduler.current_semester,
                    "schedule_index": schedule_index,
                    "schedule": schedule,
                    "model": models[schedule_index],
                    "schedule_true_literals": schedule_literals,
                    "queries": queries,
                }

                schedule_path = output_dir / "schedules" / f"{schedule_id}.json"
                _save_json(schedule_path, schedule_payload)

                kb_path = output_dir / "kbs" / f"kb_{schedule_id}.json"
                export_kb_json(
                    output_path=kb_path,
                    schedule_id=schedule_id,
                    base_kb=base_kb,
                    schedule_unit_clauses=schedule_unit_clauses,
                    vpool_mapping=vpool_mapping,
                    course_index_map=course_index_map,
                    templates=scheduler.templates,
                )

                manifest["schedules"].append(
                    {
                        "schedule_id": schedule_id,
                        "input_path": str(input_path),
                        "schedule_path": str(schedule_path),
                        "kb_path": str(kb_path),
                        "num_queries": len(queries),
                    }
                )

    manifest_path = output_dir / "manifest.json"
    _save_json(manifest_path, manifest)


def _parse_args() -> DatasetConfig:
    repo_root = Path(__file__).resolve().parents[1]
    files_dir = repo_root / "files"

    parser = argparse.ArgumentParser(
        description="Generate schedules, queries, and KBs for explainer experiments."
    )
    parser.add_argument("--output-dir", default=str(repo_root / "datasets"))
    parser.add_argument("--base-input", default=str(files_dir / "user_input.json"))
    parser.add_argument("--variations", type=int, default=3)
    parser.add_argument("--semesters", default="2,4,6")
    parser.add_argument("--max-schedules", type=int, default=5)
    parser.add_argument("--complexity-levels", default="1,2,4,6")
    parser.add_argument("--queries-per-complexity", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    semesters = [int(s.strip()) for s in args.semesters.split(",") if s.strip()]
    complexity_levels = [
        int(s.strip()) for s in args.complexity_levels.split(",") if s.strip()
    ]

    course_files = {
        "core": files_dir / "core_courses.json",
        "methods": files_dir / "methods_electives.json",
        "systems": files_dir / "systems_electives.json",
        "cs_electives": files_dir / "CS_electives.json",
        "sciences": files_dir / "sciences_electives.json",
        "social": files_dir / "social_electives.json",
    }

    return DatasetConfig(
        output_dir=Path(args.output_dir),
        base_input_path=Path(args.base_input),
        course_files=course_files,
        variations=args.variations,
        semesters=semesters,
        max_schedules=args.max_schedules,
        complexity_levels=complexity_levels,
        queries_per_complexity=args.queries_per_complexity,
        seed=args.seed,
    )


if __name__ == "__main__":
    generate_datasets(_parse_args())
