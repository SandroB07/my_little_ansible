"""SSH connection helpers built on top of paramiko.

Supports the three authentication modes required by the spec:

* default SSH configuration (agent and discovered keys),
* username + password,
* username + private key file.

A per-connection ``become`` flag (bonus feature) causes every
subsequent :meth:`exec` to run under ``sudo -n -E bash -c``.

Author: Sandro Bakuradze.
"""

import getpass
import shlex
import uuid
from pathlib import Path
from typing import Optional

import paramiko

from .result import CmdResult


class SSHConnection:
    """Thin wrapper around ``paramiko.SSHClient`` for a single host."""

    def __init__(self, host_name: str, host_config: dict):
        self.host_name = host_name
        self.address = host_config["ssh_address"]
        self.port = int(host_config.get("ssh_port", 22))
        self.user = host_config.get("ssh_user")
        self.password = host_config.get("ssh_password")
        self.key_file = host_config.get("ssh_key_file")
        self.client: Optional[paramiko.SSHClient] = None
        self.become: bool = False

    def connect(self) -> None:
        """Open the SSH connection using the configured credentials."""
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs = {
            "hostname": self.address,
            "port": self.port,
            "timeout": 15,
        }
        if self.password:
            kwargs["username"] = self.user
            kwargs["password"] = self.password
            kwargs["look_for_keys"] = False
            kwargs["allow_agent"] = False
        elif self.key_file:
            kwargs["username"] = self.user
            kwargs["key_filename"] = str(Path(self.key_file).expanduser())
            kwargs["look_for_keys"] = False
            kwargs["allow_agent"] = False
        else:
            kwargs["username"] = self.user or getpass.getuser()
            kwargs["look_for_keys"] = True
            kwargs["allow_agent"] = True

        client.connect(**kwargs)
        # Send a keepalive every 30s so long-running remote commands
        # (e.g. `apt-get install nginx`) do not drop the transport.
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        self.client = client

    def exec(self, command: str) -> CmdResult:
        """Run ``command`` remotely; wrap with ``sudo`` when become is set."""
        assert self.client is not None, "SSH client not connected"
        actual = command
        if self.become:
            actual = "sudo -n -E bash -c " + shlex.quote(command)
        _, stdout, stderr = self.client.exec_command(actual)
        exit_code = stdout.channel.recv_exit_status()
        return CmdResult(
            stdout=stdout.read().decode("utf-8", errors="replace"),
            stderr=stderr.read().decode("utf-8", errors="replace"),
            exit_code=exit_code,
        )

    def sftp(self) -> paramiko.SFTPClient:
        """Open an SFTP channel over the existing SSH connection."""
        assert self.client is not None, "SSH client not connected"
        return self.client.open_sftp()

    def put_file(self, local_path: str, remote_path: str) -> None:
        """Upload a file, transparently handling ``become`` via ``sudo mv``.

        When :attr:`become` is false the file is sent straight to
        ``remote_path``. When true, the file is first uploaded to a
        random path under ``/tmp`` (as the SSH user) and then moved to
        the final destination with ``sudo``.
        """
        if not self.become:
            sftp = self.sftp()
            try:
                sftp.put(local_path, remote_path)
            finally:
                sftp.close()
            return

        staging = f"/tmp/mla-{uuid.uuid4().hex}"
        qstage = shlex.quote(staging)
        qdest = shlex.quote(remote_path)

        was_become = self.become
        self.become = False
        try:
            sftp = self.sftp()
            try:
                sftp.put(local_path, staging)
            finally:
                sftp.close()
        finally:
            self.become = was_become

        res = self.exec(f"mv {qstage} {qdest}")
        if not res.ok:
            self.become = False
            try:
                sftp = self.sftp()
                try:
                    sftp.remove(staging)
                except Exception:
                    pass
                finally:
                    sftp.close()
            finally:
                self.become = was_become
            raise RuntimeError(
                f"sudo mv failed: {res.stderr.strip()[:200]}"
            )

    def close(self) -> None:
        """Close the underlying SSH connection if one is open."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self) -> "SSHConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
