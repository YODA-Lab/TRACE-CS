import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

repo_root = Path(__file__).resolve().parents[1]
sys.path.append(str(repo_root))

from types import SimpleNamespace

from scheduler import CourseScheduler
from explainer import contrastive_explanations, post_process_explanation


def _load_json(path: Path) -> Dict:
    with path.open("r") as f:
        return json.load(f)


def _save_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _build_true_lits_from_payload(schedule_payload: Dict) -> List[List[int]]:
    schedule_literals = schedule_payload.get("schedule_true_literals")
    if schedule_literals:
        return [[lit] for lit in schedule_literals]
    return []


def _build_true_lits(scheduler, schedule: List[List[str]]) -> List[List[int]]:
    true_lits: List[List[int]] = []
    for semester_index, courses in enumerate(schedule):
        if semester_index < scheduler.current_semester:
            continue
        relative_index = semester_index - scheduler.current_semester
        for course in courses:
            if course in scheduler.course_vars:
                var = scheduler.course_vars[course]["semester_vars"][relative_index]
                true_lits.append([var])
    return true_lits


def _build_query_data_from_items(scheduler, items: List[Dict]) -> List:
    query_data = []
    for item in items:
        course_name = item["course"]
        semester = item.get("semester")
        condition = item["condition"]
        is_positive = condition == "add"

        if course_name in scheduler.courses_taken:
            query_data.append(
                (course_name, semester, f"{course_name} has already been taken in a past semester.", "")
            )
            continue

        if course_name not in scheduler.courses:
            query_data.append((course_name, semester, "This course does not exist.", ""))
            continue

        if semester is None:
            query_data.append(
                (course_name, None, is_positive, scheduler.course_vars[course_name]["var"])
            )
            continue

        if semester > 8:
            query_data.append(
                (course_name, semester, f"There is no semester {semester}. The maximum amount of semesters is 8.", "")
            )
            continue

        if semester <= scheduler.current_semester:
            query_data.append(
                (course_name, semester, f"Semester {semester} has already passed.", "")
            )
            continue

        semester_number = int(semester) - scheduler.current_semester - 1
        query_data.append(
            (
                course_name,
                semester_number,
                is_positive,
                scheduler.course_vars[course_name]["semester_vars"][semester_number],
            )
        )

    return query_data


def _build_course_vars_from_kb(kb_payload: Dict) -> Dict[str, Dict[str, object]]:
    index_map = {entry["index"]: entry["course_code"] for entry in kb_payload["course_index_map"]}
    course_vars: Dict[str, Dict[str, object]] = {
        code: {"var": None, "semester_vars": {}} for code in index_map.values()
    }

    for entry in kb_payload["vpool_mapping"]:
        var_id = entry["var"]
        label = entry["label"]
        if not isinstance(label, str) or not label.startswith("c"):
            continue
        if "_s" in label:
            prefix, sem_part = label.split("_s", 1)
            index = int(prefix[1:])
            semester = int(sem_part)
            course_code = index_map.get(index)
            if course_code is not None:
                course_vars[course_code]["semester_vars"][semester] = var_id
        else:
            index = int(label[1:])
            course_code = index_map.get(index)
            if course_code is not None:
                course_vars[course_code]["var"] = var_id

    for course_code, data in course_vars.items():
        semester_vars = data["semester_vars"]
        if semester_vars:
            data["semester_vars"] = [semester_vars[k] for k in sorted(semester_vars.keys())]
        else:
            data["semester_vars"] = []

    return course_vars


def _apply_saved_kb(scheduler, kb_payload: Dict) -> None:
    scheduler.cnf = SimpleNamespace(hard=kb_payload["kb_clauses"], soft=[])
    templates = kb_payload.get("templates")
    if templates is None:
        raise ValueError(
            "Saved KB does not include templates. Regenerate datasets with templates enabled."
        )
    scheduler.templates = {entry["label"]: entry["clauses"] for entry in templates}
    scheduler.course_vars = _build_course_vars_from_kb(kb_payload)


def run_dataset_experiments(
    manifest_path: Path,
    output_path: Path,
    course_files: Dict[str, Path],
    max_schedules: Optional[int],
    max_queries: Optional[int],
    post_process: bool,
    use_saved_kb: bool,
) -> None:
    manifest = _load_json(manifest_path)
    schedule_entries = manifest.get("schedules", [])

    if max_schedules is not None:
        schedule_entries = schedule_entries[:max_schedules]

    results = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "manifest_path": str(manifest_path),
        "num_schedules": len(schedule_entries),
        "results": [],
    }

    for entry in schedule_entries:
        schedule_path = Path(entry["schedule_path"])
        input_path = Path(entry["input_path"])
        kb_path = Path(entry["kb_path"])

        schedule_payload = _load_json(schedule_path)
        user_input = _load_json(input_path)

        scheduler = CourseScheduler(
            str(course_files["core"]),
            str(course_files["methods"]),
            str(course_files["systems"]),
            str(course_files["cs_electives"]),
            str(course_files["sciences"]),
            str(course_files["social"]),
            str(input_path),
        )
        if use_saved_kb:
            kb_payload = _load_json(kb_path)
            _apply_saved_kb(scheduler, kb_payload)
        else:
            scheduler.generate_constraints()

        schedule = schedule_payload["schedule"]
        true_lits = _build_true_lits_from_payload(schedule_payload)
        if not true_lits:
            true_lits = _build_true_lits(scheduler, schedule)
        schedules = [schedule]
        all_true_lits = [true_lits]

        queries = schedule_payload.get("queries", [])
        if max_queries is not None:
            queries = queries[:max_queries]

        for query in queries:
            query_data = _build_query_data_from_items(scheduler, query["items"])
            explanation = contrastive_explanations(
                scheduler, schedules, 0, all_true_lits, query_data
            )
            post_processed = None
            if post_process:
                post_processed = post_process_explanation(
                    explanation, query["text"], schedule, scheduler.courses
                )

            results["results"].append(
                {
                    "schedule_id": schedule_payload["schedule_id"],
                    "input_path": str(input_path),
                    "current_semester": user_input["current_semester"],
                    "query_id": query["query_id"],
                    "query": query["text"],
                    "query_items": query["items"],
                    "explanation": explanation,
                    "post_processed_explanation": post_processed,
                }
            )

    _save_json(output_path, results)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run explainer algorithms on generated datasets."
    )
    parser.add_argument(
        "--manifest",
        default=str(repo_root / "datasets" / "manifest.json"),
    )
    parser.add_argument(
        "--output",
        default=str(repo_root / "datasets" / "experiment_results.json"),
    )
    parser.add_argument("--max-schedules", type=int, default=None)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--post-process", action="store_true")
    parser.add_argument("--use-saved-kb", action="store_true")
    args = parser.parse_args()

    files_dir = repo_root / "files"
    course_files = {
        "core": files_dir / "core_courses.json",
        "methods": files_dir / "methods_electives.json",
        "systems": files_dir / "systems_electives.json",
        "cs_electives": files_dir / "CS_electives.json",
        "sciences": files_dir / "sciences_electives.json",
        "social": files_dir / "social_electives.json",
    }

    return args, course_files


if __name__ == "__main__":
    args, course_files = _parse_args()
    run_dataset_experiments(
        manifest_path=Path(args.manifest),
        output_path=Path(args.output),
        course_files=course_files,
        max_schedules=args.max_schedules,
        max_queries=args.max_queries,
        post_process=args.post_process,
        use_saved_kb=args.use_saved_kb,
    )
