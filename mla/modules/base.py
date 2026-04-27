"""Base class for all MyLittleAnsible modules.

Author: Sandro Bakuradze.
"""

from ..result import TaskResult
from ..ssh_client import SSHConnection


class BaseModule:
    """Common parent for every module.

    Subclasses set :attr:`name` to the YAML module identifier and
    implement :meth:`process`.
    """

    name: str = "anonymous"

    def __init__(self, params: dict):
        self.params = params or {}

    def require(self, key: str):
        """Fetch ``key`` from ``self.params`` or raise ``KeyError``."""
        if key not in self.params:
            raise KeyError(
                f"module '{self.name}' requires param '{key}'"
            )
        return self.params[key]

    def process(
        self,
        ssh: SSHConnection,
        dry_run: bool = False,
    ) -> TaskResult:
        """Execute the module against ``ssh`` and return a ``TaskResult``."""
        raise NotImplementedError
