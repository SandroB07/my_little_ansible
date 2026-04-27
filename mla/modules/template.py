"""Jinja2 template rendering module.

Author: Sandro Bakuradze.
"""

import hashlib
import shlex
import tempfile
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..result import TaskResult, TaskStatus
from .base import BaseModule


def _sha256_bytes(data: bytes) -> str:
    """Return the sha256 hex digest of a bytes payload."""
    return hashlib.sha256(data).hexdigest()


def _remote_sha256(ssh, remote_path: str) -> Optional[str]:
    """Return the sha256 of a remote file, or ``None`` if missing."""
    res = ssh.exec(
        f"sha256sum {shlex.quote(remote_path)} 2>/dev/null"
    )
    if not res.ok or not res.stdout.strip():
        return None
    return res.stdout.split()[0]


class TemplateModule(BaseModule):
    """Render a Jinja2 template locally and upload it to the host."""

    name = "template"

    def process(self, ssh, dry_run=False):
        src = Path(self.require("src")).expanduser()
        dest = self.require("dest")
        variables = self.params.get("vars", {}) or {}

        if not src.is_file():
            return TaskResult(
                TaskStatus.FAILED, error=f"template not found: {src}"
            )

        env = Environment(
            loader=FileSystemLoader(str(src.parent)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        try:
            rendered = env.get_template(src.name).render(**variables)
        except Exception as exc:
            return TaskResult(
                TaskStatus.FAILED, error=f"render error: {exc}"
            )

        rendered_bytes = rendered.encode("utf-8")
        local_hash = _sha256_bytes(rendered_bytes)
        remote_hash = _remote_sha256(ssh, dest)

        if remote_hash == local_hash:
            return TaskResult(TaskStatus.OK, f"{dest} is up to date")
        if dry_run:
            return TaskResult(
                TaskStatus.CHANGED, f"would render {src} -> {dest}"
            )

        parent = str(Path(dest).parent)
        if parent:
            ssh.exec(f"mkdir -p {shlex.quote(parent)}")
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(rendered_bytes)
                tmp_path = tmp.name
            try:
                ssh.put_file(tmp_path, dest)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as exc:
            return TaskResult(TaskStatus.FAILED, error=str(exc))
        return TaskResult(
            TaskStatus.CHANGED, f"rendered {src} -> {dest}"
        )
