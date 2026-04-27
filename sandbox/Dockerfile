# Local SSH sandbox for MyLittleAnsible.
#
# A minimal Ubuntu 22.04 container that runs systemd as PID 1 and
# an openssh-server. A "mla" user with passwordless sudo is created
# at build time; its authorized_keys is mounted at run time.

FROM ubuntu:22.04

ENV container=docker
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# Force IPv4 for apt: IPv6 on the Docker / WSL2 bridge is often
# black-holed and causes 90s per-host timeouts before falling back
# to IPv4 — which makes apt-get update / install crawl.
RUN printf 'Acquire::ForceIPv4 "true";\n' \
        > /etc/apt/apt.conf.d/99force-ipv4

RUN apt-get update && apt-get install -y --no-install-recommends \
        systemd systemd-sysv \
        openssh-server sudo \
        python3 ca-certificates \
        nginx \
        git curl procps iproute2 vim-tiny \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Canonical systemd-in-docker cleanup: neutralise units we don't need
# and that typically break in an unprivileged container.
RUN cd /lib/systemd/system/sysinit.target.wants/ && \
        ls | grep -v systemd-tmpfiles-setup | xargs rm -f \
 && rm -f /lib/systemd/system/multi-user.target.wants/* \
          /etc/systemd/system/*.wants/* \
          /lib/systemd/system/local-fs.target.wants/* \
          /lib/systemd/system/sockets.target.wants/*udev* \
          /lib/systemd/system/sockets.target.wants/*initctl* \
          /lib/systemd/system/basic.target.wants/* \
          /lib/systemd/system/anaconda.target.wants/*

# Sandbox user — matches examples/inventory-sandbox.yml.
RUN useradd -m -s /bin/bash mla \
 && echo 'mla ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/mla \
 && chmod 0440 /etc/sudoers.d/mla \
 && mkdir -p /home/mla/.ssh \
 && chmod 700 /home/mla/.ssh \
 && chown -R mla:mla /home/mla/.ssh

# sshd readiness.
RUN mkdir -p /run/sshd && ssh-keygen -A && systemctl enable ssh

# systemd-user-sessions.service removes /run/nologin once
# multi-user.target is reached — without it pam_nologin blocks every
# login with "System is booting up" even after boot completes. The
# unit is 'static' so `systemctl enable` is a no-op; we create the
# wants/ symlink manually.
#
# Belt-and-suspenders: a drop-in on ssh.service also removes
# /run/nologin before sshd starts, in case boot ordering leaves the
# file behind on very fast container starts.
RUN mkdir -p /etc/systemd/system/multi-user.target.wants \
 && ln -sf /lib/systemd/system/systemd-user-sessions.service \
    /etc/systemd/system/multi-user.target.wants/systemd-user-sessions.service \
 && mkdir -p /etc/systemd/system/ssh.service.d \
 && printf '[Service]\nExecStartPre=-/bin/rm -f /run/nologin\n' \
    > /etc/systemd/system/ssh.service.d/10-remove-nologin.conf

STOPSIGNAL SIGRTMIN+3
EXPOSE 22
CMD ["/sbin/init"]
