"""Inventory YAML loader.

Author: Sandro Bakuradze.
"""

from pathlib import Path

import yaml


class InventoryError(Exception):
    """Raised when the inventory file is missing or malformed."""


def load_inventory(path: str) -> dict:
    """Load and validate an inventory YAML file.

    The file must contain a top-level ``hosts`` mapping where each entry
    provides at least an ``ssh_address``. ``ssh_port`` defaults to 22.
    """
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or "hosts" not in data:
        raise InventoryError(
            f"Inventory {path} must contain a top-level 'hosts' mapping"
        )
    hosts = data["hosts"]
    if not isinstance(hosts, dict) or not hosts:
        raise InventoryError(
            f"Inventory {path}: 'hosts' must be a non-empty mapping"
        )
    for name, cfg in hosts.items():
        if not isinstance(cfg, dict) or "ssh_address" not in cfg:
            raise InventoryError(
                f"Host '{name}' is missing required 'ssh_address'"
            )
        cfg.setdefault("ssh_port", 22)
    return hosts
