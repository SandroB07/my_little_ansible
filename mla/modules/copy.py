"""File and directory copy module.

Copies are idempotent: sha256 of each local file is compared to the
remote file before any upload happens.

Author: Sandro Bakuradze.
"""

import hashlib
import shlex
from pathlib import Path
from typing import Optional

from ..result import TaskResult, TaskStatus
from .base import BaseModule


def _sha256_file(path: Path) -> str:
    """Return the sha256 hex digest of a local file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _remote_sha256(ssh, remote_path: str) -> Optional[str]:
    """Return the sha256 of a remote file, or ``None`` if missing."""
    res = ssh.exec(
        f"sha256sum {shlex.quote(remote_path)} 2>/dev/null"
    )
    if not res.ok or not res.stdout.strip():
        return None
    return res.stdout.split()[0]


def _remote_mkdir_p(ssh, remote_path: str) -> None:
    """Create ``remote_path`` and any missing parents."""
    ssh.exec(f"mkdir -p {shlex.quote(remote_path)}")


def _walk_local(src: Path):
    """Yield ``(relative_posix_path, absolute_path)`` for files in ``src``."""
    for child in src.rglob("*"):
        if child.is_file():
            yield child.relative_to(src).as_posix(), child


class CopyModule(BaseModule):
    """Copy a local file or directory tree onto the remote host."""

    name = "copy"

    def process(self, ssh, dry_run=False):
        src = Path(self.require("src")).expanduser()
        dest = self.require("dest")
        backup = bool(self.params.get("backup", False))

        if not src.exists():
            return TaskResult(
                TaskStatus.FAILED, error=f"local src not found: {src}"
            )

        if src.is_file():
            return self._copy_file(ssh, src, dest, backup, dry_run)
        if src.is_dir():
            return self._copy_dir(ssh, src, dest, backup, dry_run)
        return TaskResult(
            TaskStatus.FAILED, error=f"unsupported src type: {src}"
        )

    def _copy_file(
        self,
        ssh,
        src: Path,
        dest: str,
        backup: bool,
        dry_run: bool,
    ) -> TaskResult:
        local_hash = _sha256_file(src)
        remote_hash = _remote_sha256(ssh, dest)
        if remote_hash == local_hash:
            return TaskResult(TaskStatus.OK, f"{dest} is up to date")
        if dry_run:
            return TaskResult(
                TaskStatus.CHANGED, f"would copy {src} -> {dest}"
            )
        if backup and remote_hash is not None:
            ssh.exec(
                f"cp -a {shlex.quote(dest)} "
                f"{shlex.quote(dest + '.bak')}"
            )
        parent = str(Path(dest).parent)
        if parent:
            _remote_mkdir_p(ssh, parent)
        try:
            ssh.put_file(str(src), dest)
        except Exception as exc:
            return TaskResult(TaskStatus.FAILED, error=str(exc))
        return TaskResult(
            TaskStatus.CHANGED, f"copied {src} -> {dest}"
        )

    def _copy_dir(
        self,
        ssh,
        src: Path,
        dest: str,
        backup: bool,
        dry_run: bool,
    ) -> TaskResult:
        changed_files: list = []
        failed: list = []

        if not dry_run:
            _remote_mkdir_p(ssh, dest)

        try:
            for rel, abs_path in _walk_local(src):
                remote_path = f"{dest.rstrip('/')}/{rel}"
                local_hash = _sha256_file(abs_path)
                remote_hash = _remote_sha256(ssh, remote_path)
                if remote_hash == local_hash:
                    continue
                if dry_run:
                    changed_files.append(rel)
                    continue
                if backup and remote_hash is not None:
                    ssh.exec(
                        f"cp -a {shlex.quote(remote_path)} "
                        f"{shlex.quote(remote_path + '.bak')}"
                    )
                parent = str(Path(remote_path).parent)
                _remote_mkdir_p(ssh, parent)
                try:
                    ssh.put_file(str(abs_path), remote_path)
                    changed_files.append(rel)
                except Exception as exc:
                    failed.append(f"{rel}: {exc}")
        except Exception as exc:
            return TaskResult(TaskStatus.FAILED, error=str(exc))

        if failed:
            return TaskResult(
                TaskStatus.FAILED, error="; ".join(failed)
            )
        if not changed_files:
            return TaskResult(TaskStatus.OK, f"{dest} is up to date")
        verb = "would copy" if dry_run else "copied"
        return TaskResult(
            TaskStatus.CHANGED,
            f"{verb} {len(changed_files)} file(s) to {dest}",
        )
