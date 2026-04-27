"""System user account management module (bonus).

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class UserModule(BaseModule):
    """Create or remove a local user account idempotently."""

    name = "user"

    def process(self, ssh, dry_run=False):
        user = self.require("name")
        state = self.params.get("state", "present")
        shell = self.params.get("shell")
        home = self.params.get("home")
        system = bool(self.params.get("system", False))
        create_home = bool(self.params.get("create_home", True))
        remove_home = bool(self.params.get("remove_home", False))

        qu = shlex.quote(user)
        exists = ssh.exec(f"getent passwd {qu}").ok

        if state == "absent":
            if not exists:
                return TaskResult(
                    TaskStatus.OK, f"user {user} already absent"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would delete user {user}"
                )
            cmd = "userdel"
            if remove_home:
                cmd += " -r"
            res = ssh.exec(f"{cmd} {qu}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"deleted user {user}")

        if state == "present":
            if exists:
                return TaskResult(TaskStatus.OK, f"user {user} exists")
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would create user {user}"
                )
            parts = ["useradd"]
            if system:
                parts.append("-r")
            if create_home:
                parts.append("-m")
            if shell:
                parts.extend(["-s", shlex.quote(shell)])
            if home:
                parts.extend(["-d", shlex.quote(home)])
            parts.append(qu)
            res = ssh.exec(" ".join(parts))
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"created user {user}")

        return TaskResult(
            TaskStatus.FAILED, error=f"unknown state: {state}"
        )
