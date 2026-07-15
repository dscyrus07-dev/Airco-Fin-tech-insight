#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/airco/app}"
SSL_DIR="${SSL_DIR:-/opt/airco/ssl}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_root_or_sudo() {
  if [[ "${EUID}" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo "This script requires sudo privileges." >&2
      exit 1
    fi
  fi
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker and Docker Compose are already installed."
    return
  fi

  log "Installing Docker Engine and Compose plugin for Ubuntu..."
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg lsb-release

  sudo install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
  fi

  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"

  printf "deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n" "$arch" "$codename" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable docker
  sudo systemctl start docker

  if id -nG "$USER" | grep -qw docker; then
    :
  else
    sudo usermod -aG docker "$USER"
    log "Added $USER to docker group. Log out and back in after bootstrap if docker commands fail without sudo."
  fi
}

prepare_directories() {
  log "Preparing deployment directories..."
  sudo mkdir -p "$DEPLOY_DIR" "$SSL_DIR"
  sudo chown -R "$USER":"$USER" "$(dirname "$DEPLOY_DIR")"
}

validate_env() {
  if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    echo "Missing $PROJECT_ROOT/.env" >&2
    echo "Create it from .env.ec2.example before deployment." >&2
    exit 1
  fi

  if [[ ! -f "$PROJECT_ROOT/docker-compose.ec2.yml" ]]; then
    echo "Missing docker-compose.ec2.yml in $PROJECT_ROOT" >&2
    exit 1
  fi
}

print_summary() {
  log "Bootstrap complete."
  echo "Deployment directory: $DEPLOY_DIR"
  echo "SSL directory: $SSL_DIR"
  echo "Project root: $PROJECT_ROOT"
  echo
  echo "Next steps:"
  echo "1. Copy SSL cert files into $SSL_DIR as fullchain.pem and privkey.pem"
  echo "2. Confirm $PROJECT_ROOT/.env is filled with production values"
  echo "3. Run ./scripts/deploy-ec2.sh"
}

require_root_or_sudo
install_docker
prepare_directories
validate_env
print_summary
