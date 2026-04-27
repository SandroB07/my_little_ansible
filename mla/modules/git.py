"""Git repository clone / update module (bonus).

Author: Sandro Bakuradze.
"""

import shlex

from ..result import TaskResult, TaskStatus
from .base import BaseModule


class GitModule(BaseModule):
    """Clone a repository, or fast-forward it to a requested version."""

    name = "git"

    def process(self, ssh, dry_run=False):
        repo = self.require("repo")
        dest = self.require("dest")
        version = self.params.get("version")
        update = bool(self.params.get("update", True))

        qdest = shlex.quote(dest)
        qrepo = shlex.quote(repo)
        is_repo = ssh.exec(
            f"test -d {shlex.quote(dest + '/.git')}"
        ).ok

        if not is_repo:
            if dry_run:
                return TaskResult(
                    TaskStatus.CHANGED,
                    f"would clone {repo} into {dest}",
                )
            clone_cmd = f"git clone {qrepo} {qdest}"
            res = ssh.exec(clone_cmd)
            if not res.ok:
                return TaskResult(TaskStatus.FAILED, error=res.stderr)
            if version:
                co = ssh.exec(
                    f"git -C {qdest} checkout {shlex.quote(version)}"
                )
                if not co.ok:
                    return TaskResult(TaskStatus.FAILED, error=co.stderr)
            return TaskResult(
                TaskStatus.CHANGED, f"cloned {repo} to {dest}"
            )

        before = ssh.exec(f"git -C {qdest} rev-parse HEAD")
        before_sha = before.stdout.strip() if before.ok else ""

        if not update:
            short = before_sha[:7] if before_sha else "?"
            return TaskResult(
                TaskStatus.OK, f"{dest} already a repo ({short})"
            )

        if dry_run:
            target = version or "remote HEAD"
            return TaskResult(
                TaskStatus.CHANGED, f"would update {dest} to {target}"
            )

        fetch = ssh.exec(f"git -C {qdest} fetch --all --quiet")
        if not fetch.ok:
            return TaskResult(TaskStatus.FAILED, error=fetch.stderr)
        if version:
            co = ssh.exec(
                f"git -C {qdest} checkout {shlex.quote(version)}"
            )
            if not co.ok:
                return TaskResult(TaskStatus.FAILED, error=co.stderr)
        pull = ssh.exec(f"git -C {qdest} pull --ff-only --quiet")
        if not pull.ok:
            return TaskResult(TaskStatus.FAILED, error=pull.stderr)

        after = ssh.exec(f"git -C {qdest} rev-parse HEAD")
        after_sha = after.stdout.strip() if after.ok else ""

        if before_sha == after_sha:
            short = after_sha[:7] if after_sha else "?"
            return TaskResult(
                TaskStatus.OK, f"{dest} already at {short}"
            )
        return TaskResult(
            TaskStatus.CHANGED,
            f"updated {dest}: {before_sha[:7]} -> {after_sha[:7]}",
        )
