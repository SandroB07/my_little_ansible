"""File / directory / symlink state module (bonus).

Author: Sandro Bakuradze.
"""

import shlex
from typing import Optional

from ..result import TaskResult, TaskStatus
from .base import BaseModule

VALID_STATES = {"file", "directory", "link", "absent"}


def _stat(ssh, path: str) -> Optional[dict]:
    """Return ``{type, mode, owner, group}`` or ``None`` if absent."""
    qpath = shlex.quote(path)
    res = ssh.exec(f"stat -c '%F|%a|%U|%G' {qpath} 2>/dev/null")
    if not res.ok or not res.stdout.strip():
        return None
    parts = res.stdout.strip().split("|")
    if len(parts) != 4:
        return None
    return {
        "type": parts[0],
        "mode": parts[1],
        "owner": parts[2],
        "group": parts[3],
    }


def _mode_to_str(mode) -> str:
    """Normalise integer or string modes to an octal string (e.g. 755)."""
    if isinstance(mode, int):
        return oct(mode)[2:]
    s = str(mode).lstrip("0")
    return s or "0"


class FileModule(BaseModule):
    """Manage file, directory or symlink presence and attributes."""

    name = "file"

    def process(self, ssh, dry_run=False):
        path = self.require("path")
        state = self.params.get("state", "file")
        if state not in VALID_STATES:
            return TaskResult(
                TaskStatus.FAILED, error=f"unknown state: {state}"
            )
        mode = self.params.get("mode")
        owner = self.params.get("owner")
        group = self.params.get("group")
        src = self.params.get("src")
        qpath = shlex.quote(path)

        before = _stat(ssh, path)
        changes = []

        if state == "absent":
            if before is None:
                return TaskResult(TaskStatus.OK, f"{path} already absent")
            if dry_run:
                return TaskResult(TaskStatus.CHANGED, f"would remove {path}")
            res = ssh.exec(f"rm -rf {qpath}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"removed {path}")

        if state == "directory":
            if before is None:
                changes.append("create directory")
                if not dry_run:
                    res = ssh.exec(f"mkdir -p {qpath}")
                    if not res.ok:
                        return TaskResult(
                            TaskStatus.FAILED, error=res.stderr
                        )
            elif before["type"] != "directory":
                return TaskResult(
                    TaskStatus.FAILED,
                    error=f"{path} exists but is not a directory",
                )

        elif state == "file":
            if before is None:
                changes.append("touch")
                if not dry_run:
                    res = ssh.exec(f"touch {qpath}")
                    if not res.ok:
                        return TaskResult(
                            TaskStatus.FAILED, error=res.stderr
                        )

        elif state == "link":
            if src is None:
                return TaskResult(
                    TaskStatus.FAILED, error="link state requires 'src'"
                )
            qsrc = shlex.quote(src)
            link_target = ssh.exec(f"readlink {qpath} 2>/dev/null")
            current_target = (
                link_target.stdout.strip() if link_target.ok else None
            )
            already_correct = (
                before is not None
                and before["type"] == "symbolic link"
                and current_target == src
            )
            if not already_correct:
                changes.append(f"symlink -> {src}")
                if not dry_run:
                    res = ssh.exec(f"ln -sfn {qsrc} {qpath}")
                    if not res.ok:
                        return TaskResult(
                            TaskStatus.FAILED, error=res.stderr
                        )

        after = before if dry_run else _stat(ssh, path)

        if mode is not None:
            want = _mode_to_str(mode)
            have = after["mode"] if after else None
            if have != want:
                changes.append(f"mode={want}")
                if not dry_run:
                    ssh.exec(f"chmod {shlex.quote(want)} {qpath}")

        if owner:
            have = after["owner"] if after else None
            if have != owner:
                changes.append(f"owner={owner}")
                if not dry_run:
                    ssh.exec(f"chown {shlex.quote(owner)} {qpath}")

        if group:
            have = after["group"] if after else None
            if have != group:
                changes.append(f"group={group}")
                if not dry_run:
                    ssh.exec(f"chgrp {shlex.quote(group)} {qpath}")

        if not changes:
            return TaskResult(TaskStatus.OK, f"{path} unchanged")
        verb = "would apply" if dry_run else "applied"
        return TaskResult(
            TaskStatus.CHANGED, f"{verb}: {', '.join(changes)}"
        )
