import random
from typing import Dict, List, Optional, Sequence


def _build_course_to_semester(schedule: List[List[str]]) -> Dict[str, int]:
    course_to_semester = {}
    for sem_idx, courses in enumerate(schedule, start=1):
        for course in courses:
            course_to_semester[course] = sem_idx
    return course_to_semester


def _choose_query_type(
    rng: random.Random,
    requested_types: Sequence[str],
    scheduled_courses: Sequence[str],
    unscheduled_courses: Sequence[str],
    complexity: int,
) -> Optional[str]:
    available = set()
    if unscheduled_courses:
        available.add("add")
    if scheduled_courses:
        available.add("remove")
    if scheduled_courses and unscheduled_courses and complexity >= 2:
        available.add("mix")

    candidates = [qtype for qtype in requested_types if qtype in available]
    if not candidates:
        return None
    return rng.choice(candidates)


def generate_queries(
    scheduler,
    schedule: List[List[str]],
    rng: random.Random,
    complexity_levels: Sequence[int],
    queries_per_complexity: int,
    query_types: Sequence[str] = ("add", "remove", "mix"),
    include_semester_prob: float = 0.7,
) -> List[Dict[str, object]]:
    """
    Generate contrastive query strings for a schedule.

    Returns a list of dicts with:
      - query_id
      - text
      - type (add/remove/mix)
      - complexity
      - items: [{"course": str, "semester": int|None, "condition": "add"|"remove"}]
    """
    scheduled_courses = [course for semester in schedule for course in semester]
    unscheduled_courses = [
        course
        for course in scheduler.courses.keys()
        if course not in scheduled_courses and course not in scheduler.courses_taken
    ]
    course_to_semester = _build_course_to_semester(schedule)

    queries: List[Dict[str, object]] = []
    query_counter = 0

    for complexity in complexity_levels:
        for _ in range(queries_per_complexity):
            qtype = _choose_query_type(
                rng,
                query_types,
                scheduled_courses,
                unscheduled_courses,
                complexity,
            )
            if qtype is None:
                continue

            items: List[Dict[str, object]] = []
            text = ""

            if qtype == "add":
                count = min(complexity, len(unscheduled_courses))
                courses_to_add = rng.sample(unscheduled_courses, k=count)
                include_semester = rng.random() < include_semester_prob
                if include_semester:
                    parts = []
                    for course in courses_to_add:
                        semester = rng.randint(scheduler.current_semester + 1, 8)
                        items.append(
                            {"course": course, "semester": semester, "condition": "add"}
                        )
                        parts.append(f"{course} in semester {semester}")
                    text = f"Why not {', '.join(parts)}?"
                else:
                    for course in courses_to_add:
                        items.append(
                            {"course": course, "semester": None, "condition": "add"}
                        )
                    text = f"Why not {', '.join(courses_to_add)}?"

            elif qtype == "remove":
                count = min(complexity, len(scheduled_courses))
                courses_to_remove = rng.sample(scheduled_courses, k=count)
                parts = []
                for course in courses_to_remove:
                    semester = course_to_semester.get(course)
                    items.append(
                        {"course": course, "semester": semester, "condition": "remove"}
                    )
                    parts.append(f"{course} in semester {semester}")
                text = f"Why {', '.join(parts)}?"

            elif qtype == "mix":
                add_count = max(1, complexity // 2)
                remove_count = complexity - add_count
                add_count = min(add_count, len(unscheduled_courses))
                remove_count = min(remove_count, len(scheduled_courses))

                courses_to_add = rng.sample(unscheduled_courses, k=add_count)
                courses_to_remove = rng.sample(scheduled_courses, k=remove_count)

                add_parts = []
                for course in courses_to_add:
                    semester = rng.randint(scheduler.current_semester + 1, 8)
                    items.append(
                        {"course": course, "semester": semester, "condition": "add"}
                    )
                    add_parts.append(f"{course} in semester {semester}")

                remove_parts = []
                for course in courses_to_remove:
                    semester = course_to_semester.get(course)
                    items.append(
                        {"course": course, "semester": semester, "condition": "remove"}
                    )
                    remove_parts.append(f"{course} in semester {semester}")

                text = (
                    f"Why {', '.join(remove_parts)}? "
                    f"And why not {', '.join(add_parts)}?"
                )

            query_counter += 1
            queries.append(
                {
                    "query_id": f"q{query_counter:04d}",
                    "text": text,
                    "type": qtype,
                    "complexity": complexity,
                    "items": items,
                }
            )

    return queries
