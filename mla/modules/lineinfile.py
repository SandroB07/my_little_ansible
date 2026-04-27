"""Ensure a single line is present (or absent) in a remote file (bonus).

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class LineInFileModule(BaseModule):
    """Idempotently add or remove an exact line in a file."""

    name = "lineinfile"

    def process(self, ssh, dry_run=False):
        path = self.require("path")
        line = self.require("line")
        state = self.params.get("state", "present")
        create = bool(self.params.get("create", False))

        qpath = shlex.quote(path)
        qline = shlex.quote(line)

        exists = ssh.exec(f"test -f {qpath}").ok

        if not exists:
            if state == "absent":
                return TaskResult(
                    TaskStatus.OK, f"{path} does not exist"
                )
            if not create:
                return TaskResult(
                    TaskStatus.FAILED,
                    error=f"{path} not found (pass 'create: true' to create)",
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED,
                    f"would create {path} with line",
                )
            res = ssh.exec(
                f"printf '%s\\n' {qline} > {qpath}"
            )
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"created {path}")

        present = ssh.exec(f"grep -Fxq {qline} {qpath}").ok

        if state == "present":
            if present:
                return TaskResult(
                    TaskStatus.OK, f"line already in {path}"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED,
                    f"would append line to {path}",
                )
            res = ssh.exec(
                f"printf '%s\\n' {qline} >> {qpath}"
            )
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(
                TaskStatus.CHANGED, f"appended line to {path}"
            )

        if state == "absent":
            if not present:
                return TaskResult(
                    TaskStatus.OK, f"line not in {path}"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED,
                    f"would remove line from {path}",
                )
            tmp_path = f"{path}.mla.tmp"
            qtmp = shlex.quote(tmp_path)
            cmd = (
                f"( grep -Fvx {qline} {qpath} || true ) > {qtmp}"
                f" && mv {qtmp} {qpath}"
            )
            res = ssh.exec(cmd)
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(
                TaskStatus.CHANGED, f"removed line from {path}"
            )

        return TaskResult(
            TaskStatus.FAILED, error=f"unknown state: {state}"
        )
