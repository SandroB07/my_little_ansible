"""Emit a message from a playbook (bonus module).

Author: Sandro Bakuradze.
"""

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class DebugModule(BaseModule):
    """Log a user-provided message. Always reports ``OK``."""

    name = "debug"

    def process(self, ssh, dry_run=False):
        msg = self.params.get("msg", "")
        return TaskResult(TaskStatus.OK, f"DEBUG: {msg}")
