#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILES=(-f "$PROJECT_ROOT/infra/docker/docker-compose.yml" -f "$PROJECT_ROOT/infra/docker/docker-compose.ec2.yml")
ENV_FILE="$PROJECT_ROOT/.env"
ACTION="${1:-deploy}"
COMPOSE_BIN=()

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

compose() {
  "${COMPOSE_BIN[@]}" "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "$@"
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker compose)
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
    return
  fi

  echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
}

require_files() {
  [[ -f "$ENV_FILE" ]] || {
    echo "Missing $ENV_FILE" >&2
    exit 1
  }

  [[ -f "$PROJECT_ROOT/infra/docker/docker-compose.ec2.yml" ]] || {
    echo "Missing infra/docker/docker-compose.ec2.yml" >&2
    exit 1
  }
}

ensure_ssl_files() {
  local ssl_dir cert_path key_path
  ssl_dir="$(grep -E '^SSL_CERTS_DIR=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  cert_path="$(grep -E '^SSL_CERT_PATH=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  key_path="$(grep -E '^SSL_KEY_PATH=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"

  ssl_dir="${ssl_dir:-/opt/airco/ssl}"
  cert_path="${cert_path:-$ssl_dir/fullchain.pem}"
  key_path="${key_path:-$ssl_dir/privkey.pem}"

  [[ -f "$cert_path" ]] || {
    echo "Missing SSL certificate: $cert_path" >&2
    exit 1
  }

  [[ -f "$key_path" ]] || {
    echo "Missing SSL key: $key_path" >&2
    exit 1
  }
}

validate_config() {
  log "Validating merged docker compose config..."
  compose config >/dev/null
}

build_stack() {
  log "Building images..."
  compose build --pull
}

start_stack() {
  log "Starting stack..."
  compose up -d --remove-orphans
}

show_status() {
  log "Container status"
  compose ps
}

show_health() {
  log "Health summary"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
}

case "$ACTION" in
  deploy)
    detect_compose
    require_files
    ensure_ssl_files
    validate_config
    build_stack
    start_stack
    show_status
    show_health
    ;;
  rebuild)
    detect_compose
    require_files
    ensure_ssl_files
    validate_config
    build_stack
    start_stack
    show_status
    ;;
  restart)
    detect_compose
    require_files
    compose restart
    show_status
    ;;
  status)
    detect_compose
    require_files
    show_status
    show_health
    ;;
  logs)
    detect_compose
    require_files
    compose logs --tail=200 "${2:-}"
    ;;
  stop)
    detect_compose
    require_files
    compose stop
    ;;
  down)
    detect_compose
    require_files
    compose down --remove-orphans
    ;;
  pull)
    detect_compose
    require_files
    compose pull
    ;;
  *)
    cat <<'EOF'
Usage: ./scripts/deploy-ec2.sh [deploy|rebuild|restart|status|logs|stop|down|pull]

Commands:
  deploy   Validate config, build images, and start the full EC2 stack
  rebuild  Rebuild images and restart the stack
  restart  Restart running services
  status   Show compose and container health status
  logs     Show recent logs, optionally for one service
  stop     Stop services without removing containers
  down     Stop and remove containers
  pull     Pull newer images for image-based services
EOF
    exit 1
    ;;
esac
