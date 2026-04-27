"""Tasks YAML loader.

Supports two playbook shapes:

* a plain list of task mappings (legacy / minimal form), or
* a top-level mapping with ``tasks:`` and optional ``handlers:`` keys.

Each task may carry ``name``, ``become`` and ``notify`` metadata on top
of ``module`` and ``params``.

Author: Sandro Bakuradze.
"""

from pathlib import Path
from typing import Dict, List

import yaml


class TasksError(Exception):
    """Raised when the tasks file is missing or malformed."""


def _validate_task(task: dict, idx: int, kind: str = "Task") -> None:
    """Validate a task mapping in place; raise on error."""
    if not isinstance(task, dict) or "module" not in task:
        raise TasksError(f"{kind} #{idx} missing required 'module' key")
    task.setdefault("params", {})
    if not isinstance(task["params"], dict):
        raise TasksError(f"{kind} #{idx} 'params' must be a mapping")
    task.setdefault("become", False)
    notify = task.get("notify")
    if notify is None:
        task["notify"] = []
    elif isinstance(notify, str):
        task["notify"] = [notify]
    elif isinstance(notify, list):
        task["notify"] = [str(n) for n in notify]
    else:
        raise TasksError(
            f"{kind} #{idx} 'notify' must be a string or list of strings"
        )


def load_tasks(path: str) -> Dict[str, List[dict]]:
    """Load a playbook and return ``{"tasks": [...], "handlers": [...]}``."""
    data = yaml.safe_load(Path(path).read_text())

    if isinstance(data, list):
        tasks = data
        handlers: List[dict] = []
    elif isinstance(data, dict):
        tasks = data.get("tasks", [])
        handlers = data.get("handlers", []) or []
        if not isinstance(tasks, list) or not isinstance(handlers, list):
            raise TasksError(
                f"Playbook {path}: 'tasks' and 'handlers' must be lists"
            )
    else:
        raise TasksError(
            f"Playbook {path} must be a list or a mapping"
        )

    if not tasks:
        raise TasksError(f"Playbook {path} has no tasks")

    for idx, task in enumerate(tasks, 1):
        _validate_task(task, idx, kind="Task")

    for idx, handler in enumerate(handlers, 1):
        _validate_task(handler, idx, kind="Handler")
        if "name" not in handler or not handler["name"]:
            raise TasksError(f"Handler #{idx} missing required 'name'")

    return {"tasks": tasks, "handlers": handlers}
