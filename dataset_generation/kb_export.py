import json
from pathlib import Path
from typing import Dict, List


def _normalize_clause(clause):
    return list(clause) if isinstance(clause, (list, tuple)) else [int(clause)]


def build_base_kb(scheduler) -> List[List[int]]:
    return [_normalize_clause(c) for c in (scheduler.cnf.hard + scheduler.cnf.soft)]


def build_schedule_kb(
    base_kb: List[List[int]], schedule_unit_clauses: List[List[int]]
) -> List[List[int]]:
    return list(base_kb) + list(schedule_unit_clauses)


def build_vpool_mapping(scheduler) -> List[Dict[str, object]]:
    mapping = []
    for var_id in range(1, scheduler.vpool.top + 1):
        label = scheduler.vpool.obj(var_id)
        if label is not None:
            mapping.append({"var": var_id, "label": label})
    return mapping


def build_course_index_map(scheduler) -> List[Dict[str, object]]:
    return [
        {"index": idx, "course_code": code}
        for idx, code in enumerate(scheduler.course_codes)
    ]


def export_kb_json(
    output_path: Path,
    schedule_id: str,
    base_kb: List[List[int]],
    schedule_unit_clauses: List[List[int]],
    vpool_mapping: List[Dict[str, object]],
    course_index_map: List[Dict[str, object]],
    templates: Dict[str, List[List[int]]] = None,
) -> None:
    payload = {
        "schedule_id": schedule_id,
        "base_kb_size": len(base_kb),
        "schedule_unit_clause_count": len(schedule_unit_clauses),
        "kb_clauses": build_schedule_kb(base_kb, schedule_unit_clauses),
        "schedule_unit_clauses": schedule_unit_clauses,
        "vpool_mapping": vpool_mapping,
        "course_index_map": course_index_map,
    }
    if templates is not None:
        payload["templates"] = [
            {"label": label, "clauses": clauses} for label, clauses in templates.items()
        ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
