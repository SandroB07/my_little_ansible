"""Kernel parameter (sysctl) module.

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule

CONF_PATH = "/etc/sysctl.d/99-mla.conf"


class SysctlModule(BaseModule):
    """Set a kernel parameter, optionally persisting it across reboots."""

    name = "sysctl"

    def process(self, ssh, dry_run=False):
        attr = self.require("attribute")
        value = str(self.require("value"))
        permanent = bool(self.params.get("permanent", False))

        current = ssh.exec(f"sysctl -n {shlex.quote(attr)}")
        if not current.ok:
            return TaskResult(TaskStatus.FAILED, error=current.stderr)
        runtime_value = current.stdout.strip()
        runtime_matches = runtime_value == value

        conf_line = f"{attr} = {value}"
        persisted = False
        if permanent:
            check = ssh.exec(
                f"grep -Fxq {shlex.quote(conf_line)} "
                f"{shlex.quote(CONF_PATH)} 2>/dev/null"
            )
            persisted = check.ok

        needs_runtime = not runtime_matches
        needs_persist = permanent and not persisted

        if not needs_runtime and not needs_persist:
            return TaskResult(TaskStatus.OK, f"{attr}={value}")

        if dry_run:
            parts = []
            if needs_runtime:
                parts.append(f"would set {attr}={value}")
            if needs_persist:
                parts.append(f"would persist to {CONF_PATH}")
            return TaskResult(TaskStatus.CHANGED, "; ".join(parts))

        if needs_runtime:
            res = ssh.exec(
                "sysctl -w "
                f"{shlex.quote(attr)}={shlex.quote(value)}"
            )
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)

        if needs_persist:
            sed_pattern = "/^\\s*" + attr + "\\s*=.*/d"
            remove_cmd = (
                "touch " + shlex.quote(CONF_PATH)
                + " && sed -i " + shlex.quote(sed_pattern)
                + " " + shlex.quote(CONF_PATH)
            )
            res = ssh.exec(remove_cmd)
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            append_cmd = (
                "printf '%s\\n' " + shlex.quote(conf_line)
                + " >> " + shlex.quote(CONF_PATH)
            )
            res = ssh.exec(append_cmd)
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)

        return TaskResult(TaskStatus.CHANGED, f"{attr}={value}")
