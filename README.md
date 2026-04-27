# MyLittleAnsible

A minimal, Ansible-inspired playbook runner written in Python. Reads a YAML
playbook and an inventory file, connects to each target host over SSH, and
executes a sequence of modules (apt, copy, template, service, sysctl, command,
plus several bonus modules).

**Author:** Sandro Bakuradze

---

## Table of contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Trying it out locally (Docker sandbox)](#trying-it-out-locally-docker-sandbox)
5. [CLI usage](#cli-usage)
6. [Inventory format](#inventory-format)
7. [Playbook format](#playbook-format)
8. [Module reference](#module-reference)
9. [Output format](#output-format)
10. [Exit codes](#exit-codes)
11. [Development](#development)

---

## Features

### Required modules

| Module      | Purpose                                     |
|-------------|---------------------------------------------|
| `apt`       | Install / remove Debian / Ubuntu packages   |
| `command`   | Run an arbitrary shell command              |
| `copy`      | Upload a file or a whole directory          |
| `service`   | Manage systemd units                        |
| `sysctl`    | Set kernel parameters (runtime + persisted) |
| `template`  | Render a Jinja2 template and upload it      |

### Bonus modules

| Module        | Purpose                                                   |
|---------------|-----------------------------------------------------------|
| `debug`       | Emit a log message from inside a playbook                 |
| `file`        | Manage file / directory / symlink state, mode, owner      |
| `git`         | Clone a repository or fast-forward it to a given version  |
| `lineinfile`  | Ensure an exact line is present / absent in a file        |
| `user`        | Create / remove local user accounts                       |

### Bonus playbook features

- **`name:`** — human-friendly task labels surfaced in the logs.
- **`become: true`** — wraps the module's commands in `sudo -n -E bash -c`.
  Works for shell-based modules and (via a stage-in-`/tmp` + `sudo mv` dance)
  for `copy` and `template` too.
- **Handlers** — `notify:` fires a named handler exactly once per host, and
  only if the notifying task actually reported `CHANGED`.
- **Idempotency** — every module checks the current state of the host before
  acting; re-running a playbook should report `OK` for already-applied tasks.
- **`--dry-run`** — report what would change without touching any host.
- **`--debug`** — include full stack traces when a task raises.
- **Play recap** — per-host summary of `ok` / `changed` / `failed` /
  `unreachable` at the end of the run.
- **Three SSH auth modes** — default SSH config (agent / discovered keys),
  private key file, or username + password. All configured from the inventory.

---

## Requirements

- Python **3.9+**
- Third-party packages (listed in `requirements.txt`):
  - `paramiko` — SSH client
  - `jinja2` — template engine
  - `click` — command-line interface
  - `pyyaml` — YAML parsing

Only standard library + those four packages are used.

---

## Installation

```bash
# 1. Clone and enter the project
git clone <your-fork-url> MyLittleAnsible
cd MyLittleAnsible

# 2. (Recommended) create a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

To confirm the install worked:

```bash
python -m mla --help
```

---

## Trying it out locally (Docker sandbox)

The repo ships a self-contained SSH sandbox under `sandbox/` so you can
run playbooks end-to-end without pointing the tool at real servers.

It builds an Ubuntu 22.04 container running **systemd + openssh-server**,
creates a `mla` user with passwordless sudo, and publishes sshd on
`localhost:2222`. A matching inventory already lives at
`examples/inventory-sandbox.yml`.

**Requirements:** Docker + `docker compose` (or the legacy
`docker-compose`). On Linux this typically means `sudo apt-get install
docker.io docker-compose-plugin` or Docker Desktop.

### Start it

```bash
./sandbox/setup.sh
```

On the first run this will:

1. Generate an ed25519 key pair at `sandbox/id_mla` / `sandbox/id_mla.pub`
   (both `.gitignore`'d).
2. Build the image and launch the container.
3. Wait for `sshd` to accept connections on `localhost:2222`.

### Use it

```bash
# End-to-end demo (apt install, copy, template, services, handlers, ...)
python -m mla -f examples/tasks.yml -i examples/inventory-sandbox.yml

# Individual module demos
python -m mla -f examples/modules/apt.yml        -i examples/inventory-sandbox.yml
python -m mla -f examples/modules/file.yml       -i examples/inventory-sandbox.yml
python -m mla -f examples/modules/service.yml    -i examples/inventory-sandbox.yml
python -m mla -f examples/modules/lineinfile.yml -i examples/inventory-sandbox.yml

# Run any playbook twice to see idempotency in action:
# the first run shows CHANGED, the second shows OK.
python -m mla -f examples/modules/apt.yml -i examples/inventory-sandbox.yml
python -m mla -f examples/modules/apt.yml -i examples/inventory-sandbox.yml

# Preview without mutating the sandbox
python -m mla -f examples/tasks.yml -i examples/inventory-sandbox.yml --dry-run
```

You can also ssh in manually:

```bash
ssh -i sandbox/id_mla -p 2222 mla@127.0.0.1
```

### Stop it

```bash
./sandbox/teardown.sh
```

This runs `docker compose down -v` and removes the container. Your
`sandbox/id_mla` key pair is kept so you can start the sandbox again
later without re-authorising.

### Troubleshooting

- **"permission denied" from sshd.** Run `./sandbox/teardown.sh` then
  `./sandbox/setup.sh` again — this regenerates a fresh sandbox and
  remounts your public key into `authorized_keys`.
- **Host key mismatch in paramiko / known_hosts.** `setup.sh` clears any
  previous entry for `[127.0.0.1]:2222` with `ssh-keygen -R`. If you ran
  it before that patch, run
  `ssh-keygen -R '[127.0.0.1]:2222'` manually.
- **`systemd` fails to start inside the container.** Your Docker version
  may not support `cgroup: host` in compose. Either upgrade Docker, or
  remove that line from `sandbox/docker-compose.yml` and keep
  `privileged: true`.

---

## CLI usage

The program is invoked as a Python module:

```bash
python -m mla [OPTIONS]

Options:
  -f, --file FILE       Path to the tasks YAML file.  [required]
  -i, --inventory FILE  Path to the inventory YAML file.  [required]
  --debug               Enable debug logging and show full stack traces.
  --dry-run             Report what would change without modifying hosts.
  --help                Show this message and exit.
```

### Common invocations

```bash
# Full run of the bundled demo playbook
python -m mla -f examples/tasks.yml -i examples/inventory.yml

# Preview — connect to hosts, plan actions, but never mutate anything
python -m mla -f examples/tasks.yml -i examples/inventory.yml --dry-run

# Same as above, but also show full tracebacks on any error
python -m mla -f examples/tasks.yml -i examples/inventory.yml --debug --dry-run

# Run a single-module playbook (e.g. just the apt examples)
python -m mla -f examples/modules/apt.yml -i examples/inventory.yml

# Capture the full log to a file
python -m mla -f examples/tasks.yml -i examples/inventory.yml 2>&1 | tee mla.log
```

### Per-module example playbooks

Every built-in module has a focused, self-contained example in
`examples/modules/`:

```bash
python -m mla -f examples/modules/apt.yml        -i examples/inventory.yml
python -m mla -f examples/modules/command.yml    -i examples/inventory.yml
python -m mla -f examples/modules/copy.yml       -i examples/inventory.yml
python -m mla -f examples/modules/debug.yml      -i examples/inventory.yml
python -m mla -f examples/modules/file.yml       -i examples/inventory.yml
python -m mla -f examples/modules/git.yml        -i examples/inventory.yml
python -m mla -f examples/modules/lineinfile.yml -i examples/inventory.yml
python -m mla -f examples/modules/service.yml    -i examples/inventory.yml
python -m mla -f examples/modules/sysctl.yml     -i examples/inventory.yml
python -m mla -f examples/modules/template.yml   -i examples/inventory.yml
python -m mla -f examples/modules/user.yml       -i examples/inventory.yml
```

---

## Inventory format

The inventory YAML must contain a top-level `hosts` mapping. Every host needs
at least an `ssh_address`; `ssh_port` defaults to `22`.

```yaml
hosts:
  # Auth mode 1 — default SSH config (agent / discovered private keys)
  local-dev:
    ssh_address: 127.0.0.1
    ssh_port: 22

  # Auth mode 2 — private key file
  webserver:
    ssh_address: 192.168.1.22
    ssh_port: 2222
    ssh_user: ubuntu
    ssh_key_file: ~/.ssh/id_rsa

  # Auth mode 3 — username + password
  bastion:
    ssh_address: 192.168.1.24
    ssh_port: 22
    ssh_user: admin
    ssh_password: example-password
```

Auth mode is selected per host from the keys you set:

- `ssh_password` present → password auth
- `ssh_key_file` present → key-file auth
- neither → default SSH config (agent + `~/.ssh/id_*`)

---

## Playbook format

Two shapes are accepted — both are valid and interchangeable.

### Minimal (flat list)

```yaml
- module: apt
  params:
    name: nginx
    state: present

- module: service
  params:
    name: nginx
    state: started
```

### With names, `become`, and handlers

```yaml
tasks:
  - name: install nginx
    module: apt
    become: true
    params:
      name: nginx
      state: present

  - name: render site config
    module: template
    become: true
    notify: reload nginx        # fires the handler on CHANGED
    params:
      src: ./examples/default.conf.j2
      dest: /etc/nginx/sites-enabled/default
      vars:
        server_name: example.com
        root_dir: /var/www/public

  - name: ensure nginx is running
    module: service
    become: true
    params:
      name: nginx
      state: started

handlers:
  - name: reload nginx
    module: service
    become: true
    params:
      name: nginx
      state: restarted
```

Per-task options:

| Key        | Type             | Description                                         |
|------------|------------------|-----------------------------------------------------|
| `module`   | string, required | Module name, e.g. `apt`, `copy`, `service`          |
| `params`   | mapping          | Module-specific parameters                          |
| `name`     | string           | Label shown in the logs                             |
| `become`   | bool             | Run via `sudo -n -E bash -c`                        |
| `notify`   | string or list   | Handler name(s) to fire when this task is `CHANGED` |

---

## Module reference

Every module returns one of three statuses: **`OK`** (already in the desired
state), **`CHANGED`** (state was modified), or **`FAILED`**.

### `apt`

Install or remove a Debian/Ubuntu package.

| Param          | Type   | Default   | Description                                   |
|----------------|--------|-----------|-----------------------------------------------|
| `name`         | string | required  | Package name                                  |
| `state`        | string | `present` | `present` or `absent`                         |
| `update_cache` | bool   | `true`    | `apt-get update` before installing a package  |

```yaml
- module: apt
  become: true
  params:
    name: curl
    state: present
```

### `command`

Run an arbitrary shell command. Always `CHANGED` on exit 0, `FAILED` otherwise.

| Param     | Type   | Default     | Description            |
|-----------|--------|-------------|------------------------|
| `command` | string | required    | Command to execute     |
| `shell`   | string | `/bin/bash` | Shell used via `-c`    |

```yaml
- module: command
  params:
    command: "ls /etc | wc -l"
```

### `copy`

Upload a local file or directory tree. sha256 is checked per-file, so re-runs
on unchanged input report `OK`.

| Param    | Type   | Default  | Description                              |
|----------|--------|----------|------------------------------------------|
| `src`    | string | required | Local path (file or directory)           |
| `dest`   | string | required | Remote path                              |
| `backup` | bool   | `false`  | Copy existing remote file(s) to `*.bak`  |

```yaml
- module: copy
  become: true
  params:
    src: ./examples/public
    dest: /var/www/public
    backup: true
```

### `debug`

Emit a message into the playbook log. Always `OK`.

| Param  | Type   | Default | Description        |
|--------|--------|---------|--------------------|
| `msg`  | string | `""`    | Message to log     |

```yaml
- module: debug
  params:
    msg: "provisioning starting"
```

### `file`

Manage file / directory / symlink state and attributes.

| Param   | Type            | Default | Description                                         |
|---------|-----------------|---------|-----------------------------------------------------|
| `path`  | string          | req.    | Remote path                                         |
| `state` | string          | `file`  | `file`, `directory`, `link`, or `absent`            |
| `src`   | string          | —       | Symlink target (required when `state: link`)        |
| `mode`  | int or string   | —       | Octal permissions, e.g. `"0755"`                    |
| `owner` | string          | —       | Owner username                                      |
| `group` | string          | —       | Group name                                          |

```yaml
- module: file
  become: true
  params:
    path: /srv/mla-demo
    state: directory
    mode: "0755"
    owner: root
    group: root
```

### `git`

Clone a repository, or fast-forward an existing checkout.

| Param     | Type   | Default  | Description                             |
|-----------|--------|----------|-----------------------------------------|
| `repo`    | string | required | Repository URL                          |
| `dest`    | string | required | Local destination on the remote host    |
| `version` | string | —        | Branch, tag, or SHA to check out        |
| `update`  | bool   | `true`   | If `false`, only clone, never update    |

```yaml
- module: git
  become: true
  params:
    repo: https://github.com/octocat/Hello-World.git
    dest: /opt/hello-world
    version: master
```

### `lineinfile`

Ensure an exact line is present or absent in a file.

| Param    | Type   | Default   | Description                                    |
|----------|--------|-----------|------------------------------------------------|
| `path`   | string | required  | Target file                                    |
| `line`   | string | required  | The exact line                                 |
| `state`  | string | `present` | `present` or `absent`                          |
| `create` | bool   | `false`   | Create the file (with the line) if missing     |

```yaml
- module: lineinfile
  become: true
  params:
    path: /etc/motd
    line: "Managed by MyLittleAnsible"
    state: present
    create: true
```

### `service`

Manage a systemd unit.

| Param   | Type   | Default  | Description                                                 |
|---------|--------|----------|-------------------------------------------------------------|
| `name`  | string | required | Unit name (without `.service`)                              |
| `state` | string | required | `started`, `stopped`, `restarted`, `enabled`, or `disabled` |

```yaml
- module: service
  become: true
  params:
    name: nginx
    state: started
```

### `sysctl`

Set a kernel parameter, optionally persisted across reboots in
`/etc/sysctl.d/99-mla.conf`.

| Param        | Type     | Default | Description                            |
|--------------|----------|---------|----------------------------------------|
| `attribute`  | string   | req.    | sysctl key, e.g. `net.ipv4.ip_forward` |
| `value`      | scalar   | req.    | Target value                           |
| `permanent`  | bool     | `false` | Also persist into the conf file        |

```yaml
- module: sysctl
  become: true
  params:
    attribute: net.ipv4.ip_forward
    value: 1
    permanent: true
```

### `template`

Render a local Jinja2 template (with `StrictUndefined`) and upload the result.
Idempotent via sha256 comparison of rendered output vs. remote file.

| Param  | Type    | Default  | Description                |
|--------|---------|----------|----------------------------|
| `src`  | string  | required | Local template path        |
| `dest` | string  | required | Remote destination         |
| `vars` | mapping | `{}`     | Template variables         |

```yaml
- module: template
  become: true
  params:
    src: ./examples/default.conf.j2
    dest: /etc/nginx/sites-enabled/default
    vars:
      server_name: example.com
      root_dir: /var/www/public
```

### `user`

Create or remove a local user account.

| Param         | Type   | Default   | Description                                   |
|---------------|--------|-----------|-----------------------------------------------|
| `name`        | string | required  | Username                                      |
| `state`       | string | `present` | `present` or `absent`                         |
| `shell`       | string | —         | Login shell                                   |
| `home`        | string | —         | Home directory                                |
| `system`      | bool   | `false`   | Create as a system account (`useradd -r`)     |
| `create_home` | bool   | `true`    | Create the home directory (`-m`)              |
| `remove_home` | bool   | `false`   | On `absent`, also remove home (`userdel -r`)  |

```yaml
- module: user
  become: true
  params:
    name: deploy
    shell: /bin/bash
    create_home: true
```

---

## Output format

Every log line has this shape:

```txt
YYYY-MM-DD HH:MM:SS [<host-ip>] <LEVEL> - <message>
```

Example run:

```txt
2026-04-16 13:15:01 [-]            INFO  - Loaded 10 task(s) from examples/tasks.yml
2026-04-16 13:15:01 [-]            INFO  - Loaded 1 handler(s)
2026-04-16 13:15:01 [-]            INFO  - Target hosts (2): 192.168.1.22, 192.168.1.24
2026-04-16 13:15:01 [192.168.1.22] INFO  - connecting (webserver)
2026-04-16 13:15:02 [192.168.1.22] INFO  - task 1 [debug] 'say hello' -> OK | DEBUG: starting MyLittleAnsible run
2026-04-16 13:15:03 [192.168.1.22] INFO  - task 2 [apt] 'install nginx' -> CHANGED | installed nginx-common
2026-04-16 13:15:04 [192.168.1.22] ERROR - task 5 [service] 'ensure foo' -> FAILED | stderr: Unit foo.service not found...
...
2026-04-16 13:15:30 [-]            INFO  - ============================================================
2026-04-16 13:15:30 [-]            INFO  - PLAY RECAP
2026-04-16 13:15:30 [-]            INFO  - 192.168.1.22 : ok=6  changed=4  failed=0  unreachable=0
2026-04-16 13:15:30 [-]            INFO  - 192.168.1.24 : ok=0  changed=0  failed=0  unreachable=1
```

Notes:

- stderr from failing commands is truncated to the first **200 characters**.
- The program uses the `logging` module exclusively; there are no `print`
  calls in the codebase.

---

## Exit codes

| Code | Meaning                                             |
|------|-----------------------------------------------------|
| `0`  | Every task on every host finished as OK or CHANGED  |
| `1`  | At least one task failed, or a host was unreachable |
| `2`  | Fatal error (bad YAML, missing file, bad CLI args)  |

---

## Development

```bash
# PEP8 lint (strict 79-char lines)
python3 -m pycodestyle mla/

# Byte-compile smoke-test
python3 -m compileall -q mla

# Verify every bundled example playbook parses
python3 -c "
from mla.tasks import load_tasks
import glob
for f in sorted(glob.glob('examples/**/*.yml', recursive=True)):
    pb = load_tasks(f)
    print(f'{f}: tasks={len(pb[\"tasks\"])}, handlers={len(pb[\"handlers\"])}')
"
```

Project layout:

```ast
MyLittleAnsible/
├── README.md
├── requirements.txt
├── .gitignore
├── sandbox/                          # local Docker SSH test target
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── setup.sh
│   └── teardown.sh
├── examples/
│   ├── inventory.yml                 # 3 auth modes
│   ├── inventory-sandbox.yml         # targets the Docker sandbox
│   ├── tasks.yml                     # full-stack demo (handlers + become)
│   ├── default.conf.j2
│   ├── greeting.txt.j2
│   ├── public/
│   │   └── index.html
│   └── modules/
│       ├── apt.yml           command.yml   copy.yml
│       ├── debug.yml         file.yml      git.yml
│       ├── lineinfile.yml    service.yml   sysctl.yml
│       ├── template.yml      user.yml
└── mla/
    ├── __init__.py           __main__.py
    ├── cli.py                runner.py
    ├── inventory.py          tasks.py
    ├── logging_config.py     result.py
    ├── ssh_client.py
    └── modules/
        ├── __init__.py       base.py
        ├── apt.py            command.py   copy.py
        ├── debug.py          file.py      git.py
        ├── lineinfile.py     service.py   sysctl.py
        ├── template.py       user.py
```
