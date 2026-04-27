"""Result types shared by the runner and modules.

Author: Sandro Bakuradze.
"""

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Final status reported for a module execution."""

    OK = "OK"
    CHANGED = "CHANGED"
    FAILED = "FAILED"

    @property
    def val(self):
        return self.value.lower() 

@dataclass
class CmdResult:
    """Outcome of a single remote shell command."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    @property
    def ok(self) -> bool:
        """Return ``True`` when the command exited with status 0."""
        return self.exit_code == 0


@dataclass
class TaskResult:
    """Outcome of a single task on a single host."""

    status: TaskStatus
    message: str = ""
    error: str = ""
    extras: dict = field(default_factory=dict)
