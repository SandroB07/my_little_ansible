"""systemd service management module.

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule

VALID_STATES = {"started", "stopped", "restarted", "enabled", "disabled"}


class ServiceModule(BaseModule):
    """Start, stop, restart, enable or disable a systemd unit."""

    name = "service"

    def process(self, ssh, dry_run=False):
        svc = self.require("name")
        state = self.require("state")
        if state not in VALID_STATES:
            return TaskResult(
                TaskStatus.FAILED, error=f"unknown state: {state}"
            )
        q = shlex.quote(svc)

        if state == "started":
            status = ssh.exec(f"systemctl is-active {q}")
            if status.ok and status.stdout.strip() == "active":
                return TaskResult(
                    TaskStatus.OK, f"{svc} already running"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would start {svc}"
                )
            res = ssh.exec(f"systemctl start {q}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"started {svc}")

        if state == "stopped":
            status = ssh.exec(f"systemctl is-active {q}")
            if not (status.ok and status.stdout.strip() == "active"):
                return TaskResult(
                    TaskStatus.OK, f"{svc} already stopped"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would stop {svc}"
                )
            res = ssh.exec(f"systemctl stop {q}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"stopped {svc}")

        if state == "restarted":
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would restart {svc}"
                )
            res = ssh.exec(f"systemctl restart {q}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"restarted {svc}")

        if state == "enabled":
            status = ssh.exec(f"systemctl is-enabled {q}")
            if status.ok and status.stdout.strip() == "enabled":
                return TaskResult(
                    TaskStatus.OK, f"{svc} already enabled"
                )
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED, f"would enable {svc}"
                )
            res = ssh.exec(f"systemctl enable {q}")
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            return TaskResult(TaskStatus.CHANGED, f"enabled {svc}")

        # disabled
        status = ssh.exec(f"systemctl is-enabled {q}")
        if not status.ok or status.stdout.strip() != "enabled":
            return TaskResult(TaskStatus.OK, f"{svc} already disabled")
        if dry_run:
            return TaskResult(
                TaskStatus.CHANGED, f"would disable {svc}"
            )
        res = ssh.exec(f"systemctl disable {q}")
        if not res.ok:
            return TaskResult(TaskStatus.FAILED, error=res.stderr)
        return TaskResult(TaskStatus.CHANGED, f"disabled {svc}")
