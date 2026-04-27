"""Arbitrary shell command execution module.

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class CommandModule(BaseModule):
    """Run a shell command on the remote host."""

    name = "command"

    def process(self, ssh, dry_run=False):
        cmd = self.require("command")
        shell = self.params.get("shell", "/bin/bash")
        if dry_run:
            return TaskResult(TaskStatus.CHANGED, f"would run: {cmd}")
        res = ssh.exec(
            f"{shlex.quote(shell)} -c {shlex.quote(cmd)}"
        )
        if not res.ok:
            return TaskResult(
                TaskStatus.FAILED,
                message=res.stdout.strip(),
                error=res.stderr.strip(),
            )
        return TaskResult(TaskStatus.CHANGED, message=res.stdout.strip())
