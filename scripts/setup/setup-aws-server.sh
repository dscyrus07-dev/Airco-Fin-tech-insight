#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="full"
PROJECT_DIR="/home/ec2-user/airco-insights"
ARCHIVE="/tmp/airco-insights-ec2.tar.gz"
SSL_DIR="/opt/airco/ssl"
LOGS_SERVICE=""
COMPOSE_BIN=()
SUDO=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action)
      ACTION="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --archive)
      ARCHIVE="$2"
      shift 2
      ;;
    --ssl-dir)
      SSL_DIR="$2"
      shift 2
      ;;
    --logs-service)
      LOGS_SERVICE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

setup_sudo() {
  if [[ "${EUID}" -ne 0 ]]; then
    SUDO=(sudo)
  fi
}

detect_os() {
  if [[ ! -f /etc/os-release ]]; then
    echo "Unsupported OS: missing /etc/os-release" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-unknown}"
}

docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  else
    "${SUDO[@]}" docker "$@"
  fi
}

detect_compose() {
  if docker_cmd compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker_cmd compose)
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
    return
  fi

  echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
}

compose() {
  "${COMPOSE_BIN[@]}" -f "$PROJECT_DIR/infra/docker/docker-compose.yml" -f "$PROJECT_DIR/infra/docker/docker-compose.ec2.yml" --env-file "$PROJECT_DIR/.env" "$@"
}

install_packages() {
  case "$OS_ID" in
    amzn|amazon)
      "${SUDO[@]}" dnf install -y docker curl git tar openssl
      ;;
    ubuntu|debian)
      "${SUDO[@]}" apt-get update -y
      "${SUDO[@]}" apt-get install -y docker.io curl git tar openssl
      ;;
    *)
      echo "Unsupported OS for automated bootstrap: $OS_ID" >&2
      exit 1
      ;;
  esac
}

install_compose_if_missing() {
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    return
  fi

  log "Installing standalone docker-compose..."
  "${SUDO[@]}" curl -L "https://github.com/docker/compose/releases/download/v2.39.2/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
  "${SUDO[@]}" chmod +x /usr/local/bin/docker-compose
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker is already installed."
  else
    log "Installing Docker..."
    install_packages
  fi

  "${SUDO[@]}" systemctl enable docker
  "${SUDO[@]}" systemctl start docker
  install_compose_if_missing

  if id -nG "$USER" | grep -qw docker; then
    :
  else
    "${SUDO[@]}" usermod -aG docker "$USER" || true
  fi
}

prepare_directories() {
  log "Preparing directories..."
  "${SUDO[@]}" mkdir -p "$PROJECT_DIR" "$SSL_DIR"
  "${SUDO[@]}" chown -R "$USER":"$USER" "$PROJECT_DIR"
}

clear_project_dir() {
  if [[ ! -d "$PROJECT_DIR" ]]; then
    mkdir -p "$PROJECT_DIR"
    return
  fi

  local env_backup=""
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    env_backup="$(mktemp)"
    cp "$PROJECT_DIR/.env" "$env_backup"
  fi

  find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +

  if [[ -n "$env_backup" && -f "$env_backup" ]]; then
    cp "$env_backup" "$PROJECT_DIR/.env"
    rm -f "$env_backup"
  fi
}

extract_archive() {
  [[ -f "$ARCHIVE" ]] || {
    echo "Archive not found: $ARCHIVE" >&2
    exit 1
  }

  log "Refreshing project directory from archive..."
  clear_project_dir
  tar -xzf "$ARCHIVE" -C "$PROJECT_DIR"
}

seed_env_if_missing() {
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    return
  fi

  if [[ -f "$PROJECT_DIR/.env.ec2.example" ]]; then
    cp "$PROJECT_DIR/.env.ec2.example" "$PROJECT_DIR/.env"
    log "Created .env from .env.ec2.example. Fill in secrets before production use."
    return
  fi

  echo "Missing $PROJECT_DIR/.env and .env.ec2.example" >&2
  exit 1
}

ensure_ssl_files() {
  local cert_path key_path
  cert_path="$SSL_DIR/fullchain.pem"
  key_path="$SSL_DIR/privkey.pem"

  if [[ -f "$cert_path" && -f "$key_path" ]]; then
    return
  fi

  log "Creating temporary self-signed SSL certificate in $SSL_DIR..."
  "${SUDO[@]}" openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$key_path" \
    -out "$cert_path" \
    -days 365 \
    -subj "/CN=localhost"
  "${SUDO[@]}" chmod 600 "$key_path"
}

fix_project_permissions() {
  log "Fixing common upload/build permissions..."
  chmod -R u+rwX "$PROJECT_DIR"
  rm -rf "$PROJECT_DIR/frontend/.next" "$PROJECT_DIR/frontend/node_modules" "$PROJECT_DIR/backend/.pytest_cache" 2>/dev/null || true
  find "$PROJECT_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
}

run_deploy() {
  detect_compose
  ensure_ssl_files
  log "Deploying stack with scripts/deploy-ec2.sh..."
  (cd "$PROJECT_DIR" && bash ./scripts/deploy-ec2.sh deploy)
}

show_status() {
  detect_compose
  compose ps
  docker_cmd ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
}

show_logs() {
  detect_compose
  if [[ -n "$LOGS_SERVICE" ]]; then
    compose logs --tail=200 "$LOGS_SERVICE"
  else
    compose logs --tail=200
  fi
}

setup_sudo
detect_os

case "$ACTION" in
  bootstrap)
    install_docker_if_needed
    prepare_directories
    extract_archive
    seed_env_if_missing
    fix_project_permissions
    ensure_ssl_files
    log "Bootstrap complete. Review $PROJECT_DIR/.env and rerun with --action deploy if needed."
    ;;
  deploy)
    install_docker_if_needed
    prepare_directories
    extract_archive
    seed_env_if_missing
    fix_project_permissions
    run_deploy
    ;;
  full)
    install_docker_if_needed
    prepare_directories
    extract_archive
    seed_env_if_missing
    fix_project_permissions
    run_deploy
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  *)
    cat <<'EOF'
Usage:
  bash scripts/setup-aws-server.sh --action [full|bootstrap|deploy|status|logs]

Options:
  --project-dir   Target application directory on EC2
  --archive       Uploaded .tar.gz archive path
  --ssl-dir       Host SSL directory
  --logs-service  Optional compose service name when using --action logs
EOF
    exit 1
    ;;
esac
