"""APT package management module.

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class AptModule(BaseModule):
    """Install or remove a Debian/Ubuntu package idempotently."""

    name = "apt"

    def process(self, ssh, dry_run=False):
        pkg = self.require("name")
        state = self.params.get("state", "present")
        update_cache = bool(self.params.get("update_cache", True))
        q = shlex.quote(pkg)

        check = ssh.exec(
            f"dpkg-query -W -f='${{Status}}' {q} 2>/dev/null"
        )
        installed = check.ok and "install ok installed" in check.stdout

        if state == "present":
            if installed:
                return TaskResult(
                    TaskStatus.OK, f"{pkg} already installed"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would install {pkg}"
                )
            if update_cache:
                upd = ssh.exec(
                    "DEBIAN_FRONTEND=noninteractive apt-get update -qq"
                )
                if not upd.ok:
                    return TaskResult(
                        TaskStatus.FAILED, error=upd.stderr
                    )
            res = ssh.exec(
                "DEBIAN_FRONTEND=noninteractive "
                f"apt-get install -y {q}"
            )
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"installed {pkg}")

        if state == "absent":
            if not installed:
                return TaskResult(
                    TaskStatus.OK, f"{pkg} not installed"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would remove {pkg}"
                )
            res = ssh.exec(
                "DEBIAN_FRONTEND=noninteractive "
                f"apt-get remove -y {q}"
            )
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"removed {pkg}")

        return TaskResult(
            TaskStatus.FAILED, error=f"unknown state: {state}"
        )
