"""Playbook runner: drives modules across every host in the inventory.

Also implements the bonus playbook features: task names, sudo
(``become``) execution, handler notifications and the final play
recap.

Author: Sandro Bakuradze.
"""

import logging
from typing import Dict, List, Tuple

from .inventory import load_inventory
from .logging_config import get_logger
from .modules import MODULES
from .result import TaskResult, TaskStatus
from .ssh_client import SSHConnection
from .tasks import load_tasks

MAX_STDERR = 300


def _truncate(text: str, limit: int = MAX_STDERR) -> str:
    """Return a single-line, size-capped version of ``text``."""
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _label(task: dict, idx: int, kind: str = "task") -> str:
    """Build a human-friendly label for logging."""
    name = task.get("name")
    module_name = task["module"]
    head = f"{kind} {idx}" if idx else kind
    if name:
        return f"{head} [{module_name}] '{name}'"
    return f"{head} [{module_name}]"


def _format_message(label: str, result: TaskResult) -> str:
    """Render a one-line summary for a task result."""
    parts = [f"{label} -> {result.status.value}"]
    if result.message:
        parts.append(_truncate(result.message))
    if result.status == TaskStatus.FAILED and result.error:
        parts.append(f"stderr: {_truncate(result.error)}")
    return " | ".join(parts)


def _run_single(
    ssh: SSHConnection,
    task: dict,
    label: str,
    hlog: logging.LoggerAdapter,
    debug: bool,
    dry_run: bool,
) -> TaskResult:
    """Execute one task (or handler) and log the outcome."""
    module_name = task["module"]
    mod_cls = MODULES.get(module_name)
    if mod_cls is None:
        hlog.error(f"{label} -> FAILED | unknown module")
        return TaskResult(TaskStatus.FAILED, error="unknown module")

    ssh.become = bool(task.get("become", False))
    try:
        module = mod_cls(task.get("params", {}))
        result = module.process(ssh, dry_run=dry_run)
    except Exception as exc:
        if debug:
            hlog.exception(f"{label} raised")
        result = TaskResult(TaskStatus.FAILED, error=str(exc))
    finally:
        ssh.become = False

    level = (
        logging.ERROR
        if result.status == TaskStatus.FAILED
        else logging.INFO
    )
    hlog.log(level, _format_message(label, result))
    return result


def _log_recap(
    overall: logging.LoggerAdapter,
    totals: Dict[str, Dict[str, int]],
) -> None:
    """Log a per-host play recap at the end of the run."""
    overall.info("=" * 60)
    overall.info("PLAY RECAP")
    width = max((len(h) for h in totals), default=0)
    for host, counts in totals.items():
        overall.info(
            f"{host:<{width}} : "
            f"ok={counts['ok']}  "
            f"changed={counts['changed']}  "
            f"failed={counts['failed']}  "
            f"unreachable={counts['unreachable']}"
        )


def _handlers_by_name(handlers: List[dict]) -> Dict[str, dict]:
    """Index handlers by their ``name`` field."""
    return {h["name"]: h for h in handlers}


def run_playbook(
    tasks_path: str,
    inventory_path: str,
    debug: bool,
    dry_run: bool,
) -> int:
    """Execute every task against every host and return a shell exit code."""
    overall = get_logger("mla")
    playbook = load_tasks(tasks_path)
    tasks: List[dict] = playbook["tasks"]
    handlers: List[dict] = playbook["handlers"]
    handler_index = _handlers_by_name(handlers)
    inventory = load_inventory(inventory_path)

    host_ips = [cfg["ssh_address"] for cfg in inventory.values()]
    overall.info(f"Loaded {len(tasks)} task(s) from {tasks_path}")
    if handlers:
        overall.info(f"Loaded {len(handlers)} handler(s)")
    overall.info(
        f"Target hosts ({len(host_ips)}): {', '.join(host_ips)}"
    )
    if dry_run:
        overall.info("dry-run mode enabled: no changes will be applied")

    totals: Dict[str, Dict[str, int]] = {}
    overall_failures = 0

    for host_name, host_cfg in inventory.items():
        ip = host_cfg["ssh_address"]
        hlog = get_logger(ip)
        counts = {TaskStatus.OK.val: 0, TaskStatus.CHANGED.val: 0, TaskStatus.FAILED.val: 0, "unreachable": 0}
        totals[ip] = counts

        hlog.info(f"connecting ({host_name})")
        try:
            conn_ctx: Tuple = (host_name, host_cfg)
            with SSHConnection(*conn_ctx) as ssh:
                notified: List[str] = []
                for idx, task in enumerate(tasks, 1):
                    label = _label(task, idx)
                    result = _run_single(
                        ssh, task, label, hlog, debug, dry_run
                    )
                    if result.status == TaskStatus.OK:
                        counts[TaskStatus.OK.val] += 1
                    elif result.status == TaskStatus.CHANGED:
                        counts[TaskStatus.CHANGED.val] += 1
                        for hname in task.get("notify", []):
                            if hname not in notified:
                                if hname not in handler_index:
                                    hlog.error(
                                        f"notify '{hname}' -> "
                                        "FAILED | unknown handler"
                                    )
                                    continue
                                notified.append(hname)
                    else:
                        counts[TaskStatus.FAILED.val] += 1
                        overall_failures += 1

                # Run notified handlers once per host.
                for hidx, hname in enumerate(notified, 1):
                    handler = handler_index[hname]
                    label = _label(handler, hidx, kind="handler")
                    result = _run_single(
                        ssh, handler, label, hlog, debug, dry_run
                    )
                    if result.status == TaskStatus.OK:
                        counts[TaskStatus.OK.val] += 1
                    elif result.status == TaskStatus.CHANGED:
                        counts[TaskStatus.CHANGED.val] += 1
                    else:
                        counts[TaskStatus.FAILED.val] += 1
                        overall_failures += 1
        except Exception as exc:
            if debug:
                hlog.exception("connection failed")
            hlog.error(f"connection failed: {_truncate(str(exc))}")
            counts["unreachable"] += 1
            overall_failures += len(tasks)

    _log_recap(overall, totals)

    if overall_failures:
        overall.error(f"completed with {overall_failures} failure(s)")
        return 1
    overall.info("completed successfully")
    return 0
