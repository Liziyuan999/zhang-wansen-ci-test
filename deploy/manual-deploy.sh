#!/usr/bin/env bash
# 知寻 KnowSeek 手动化部署脚本（服务器端执行）
# 用法：
#   1) 首次：sudo bash deploy/manual-deploy.sh init     # 检查环境 + 准备 .env
#   2) 部署：sudo bash deploy/manual-deploy.sh deploy   # 构建并启动
#   3) 运维：sudo bash deploy/manual-deploy.sh status | logs | restart | stop
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

ENV_FILE="$APP_DIR/server/.env"
COMPOSE="docker compose"

log()  { echo -e "\033[32m[$(date '+%H:%M:%S')]\033[0m $*"; }
warn() { echo -e "\033[33m[警告]\033[0m $*"; }
die()  { echo -e "\033[31m[失败]\033[0m $*"; exit 1; }

check_env() {
  log "检查 Docker 环境"
  command -v docker >/dev/null 2>&1 || die "未安装 Docker，请先执行：curl -fsSL https://get.docker.com | bash -s docker"
  docker compose version >/dev/null 2>&1 || die "未安装 docker compose 插件"
  systemctl is-active --quiet docker || { warn "Docker 未运行，尝试启动"; systemctl start docker; }
  log "Docker: $(docker --version)"
  log "Compose: $(docker compose version --short)"
}

gen_secret() { python3 -c "import secrets;print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32; }

init_env() {
  check_env
  if [ -f "$ENV_FILE" ]; then
    warn "server/.env 已存在，跳过生成（如需重置请手动备份删除）"
    return
  fi
  log "生成生产环境配置 server/.env"
  cp "$APP_DIR/server/.env.example" "$ENV_FILE"
  local jwt pgpwd
  jwt="$(gen_secret)"
  pgpwd="$(gen_secret)"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${jwt}|" "$ENV_FILE"
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://knowseek:${pgpwd}@db:5432/knowseek|" "$ENV_FILE"
  sed -i "s|^CHROMA_DIR=.*|CHROMA_DIR=/data/chroma_data|" "$ENV_FILE"
  sed -i "s|^UPLOAD_DIR=.*|UPLOAD_DIR=/data/uploads|" "$ENV_FILE"
  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"*\"]|" "$ENV_FILE"
  # docker-compose 读取同一批变量
  cat > "$APP_DIR/.env" <<EOF
POSTGRES_USER=knowseek
POSTGRES_PASSWORD=${pgpwd}
POSTGRES_DB=knowseek
TZ=Asia/Shanghai
EOF
  chmod 600 "$ENV_FILE" "$APP_DIR/.env"
  log "已生成密钥与数据库密码，请补充以下变量后重新执行 deploy："
  echo "  - DEEPSEEK_API_KEY （不填可运行，走本地降级回答）"
  echo "  - MAIL_USER / MAIL_PASS / MAIL_FROM （QQ邮箱 SMTP 授权码，用于注册验证码）"
  echo "  配置路径：$ENV_FILE"
}

deploy() {
  check_env
  [ -f "$ENV_FILE" ] || die "缺少 server/.env，请先执行：bash deploy/manual-deploy.sh init"
  log "构建镜像（首次约 5-10 分钟，耐心等待）"
  $COMPOSE build
  log "启动容器"
  $COMPOSE up -d
  log "等待服务就绪"
  local ok=0
  for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/docs >/dev/null 2>&1 || curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
  done
  [ "$ok" = "1" ] || warn "后端 90 秒内未响应，请查看日志：bash deploy/manual-deploy.sh logs"
  log "容器状态"
  $COMPOSE ps
  log "部署完成：http://$(curl -s --max-time 5 ifconfig.me || echo '服务器公网IP')"
}

case "${1:-deploy}" in
  init)    init_env ;;
  deploy)  deploy ;;
  status)  $COMPOSE ps ;;
  logs)    $COMPOSE logs -f --tail=200 ${2:-} ;;
  restart) $COMPOSE restart ;;
  stop)    $COMPOSE down ;;
  *)       echo "用法: bash deploy/manual-deploy.sh {init|deploy|status|logs|restart|stop}"; exit 1 ;;
esac
