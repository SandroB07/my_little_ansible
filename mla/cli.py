"""Command-line interface for MyLittleAnsible.

Author: Sandro Bakuradze.
"""

import sys

import click

from .logging_config import get_logger, setup_logging
from .runner import run_playbook


@click.command(
    name="mla",
    help=(
        "MyLittleAnsible - execute a YAML playbook against an "
        "inventory over SSH."
    ),
)
@click.option(
    "-f",
    "--file",
    "tasks_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the tasks YAML file.",
)
@click.option(
    "-i",
    "--inventory",
    "inventory_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the inventory YAML file.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logging and show full stack traces on failure.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what would change without modifying remote hosts.",
)
def main(
    tasks_file: str,
    inventory_file: str,
    debug: bool,
    dry_run: bool,
) -> None:
    """Parse CLI arguments and run the playbook."""
    setup_logging(debug=debug)
    log = get_logger()
    try:
        exit_code = run_playbook(tasks_file, inventory_file, debug, dry_run)
    except Exception as exc:
        if debug:
            log.exception("fatal error")
        else:
            log.error(f"fatal error: {exc}")
        sys.exit(2)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
