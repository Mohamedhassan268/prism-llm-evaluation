#!/usr/bin/env bash
# Reviewed bootstrap from https://docs.docker.com/engine/install/ubuntu/
set -euo pipefail
test "$(id -u)" -eq 0
. /etc/os-release
test "$ID" = ubuntu
case "$VERSION_CODENAME" in resolute|noble|jammy) ;; *) exit 2 ;; esac
if command -v docker >/dev/null 2>&1; then
  docker --version
  exit 0
fi
for prism_package in docker.io podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$prism_package" 2>/dev/null | grep -q 'install ok installed'; then
    echo "Conflicting installed package $prism_package; no packages removed." >&2
    exit 2
  fi
done
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
if ! test -e /etc/apt/keyrings/docker.asc; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
if ! test -e /etc/apt/sources.list.d/docker.sources; then
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$VERSION_CODENAME" "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/docker.sources
fi
apt-get update
PRISM_DOCKER_VERSION=$(apt-cache policy docker-ce | sed -n 's/^  Candidate: //p')
test -n "$PRISM_DOCKER_VERSION"
test "$PRISM_DOCKER_VERSION" != '(none)'
apt-get install -y --no-install-recommends "docker-ce=$PRISM_DOCKER_VERSION" "docker-ce-cli=$PRISM_DOCKER_VERSION" containerd.io docker-buildx-plugin
systemctl start docker
docker version
dpkg-query -W docker-ce docker-ce-cli containerd.io docker-buildx-plugin
