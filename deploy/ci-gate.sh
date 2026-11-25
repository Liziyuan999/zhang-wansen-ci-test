#!/usr/bin/env bash
# ============================================================
# 知寻 KnowSeek 测试门禁（手动执行版）
# ------------------------------------------------------------
# 作用：在不构建镜像的前提下，快速判断"这次改动能不能上线"。
# 用法：
#     bash deploy/ci-gate.sh          # 跑全部检查
#     bash deploy/ci-gate.sh backend  # 只跑后端单元测试
#     bash deploy/ci-gate.sh frontend # 只跑前端构建
#
# 退出码：0=通过  1=前端构建失败  2=后端测试失败  3=环境缺失
#
# 说明：真正的自动化门禁已内建在 server/Dockerfile 的 tester 阶段，
# 每次 docker compose build 都会自动跑同一套单元测试，失败则镜像构建失败、
# deploy.sh 中止、旧容器继续服务。本脚本只是本地预检的快捷方式。
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="${1:-all}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${YELLOW}[门禁]${NC} $*"; }
pass()  { echo -e "${GREEN}[通过]${NC} $*"; }
fail()  { echo -e "${RED}[失败]${NC} $*"; }

# ---------- 后端单元测试 ----------
run_backend() {
  info "后端单元测试（server/tests/test_unit_core.py）"
  cd "${ROOT_DIR}/server" || return 3
  if command -v python3 >/dev/null 2>&1; then PY=python3; elif command -v python >/dev/null 2>&1; then PY=python; else
    fail "未找到 python，无法执行后端测试"; return 3
  fi
  if ! ${PY} -c "import pytest" >/dev/null 2>&1; then
    fail "当前 Python 环境缺少 pytest，请先 pip install pytest"
    return 3
  fi
  if ${PY} -m pytest tests/ -q; then
    pass "后端单元测试全部通过"
  else
    fail "后端单元测试未通过，本次改动不允许上线"
    return 2
  fi
}

# ---------- 前端构建 ----------
run_frontend() {
  info "前端构建（web: npm run build）"
  cd "${ROOT_DIR}/web" || return 3
  if ! command -v npm >/dev/null 2>&1; then
    fail "未找到 npm，无法执行前端构建"; return 3
  fi
  [ -d node_modules ] || { info "node_modules 不存在，先执行 npm ci"; npm ci || return 3; }
  if npm run build; then
    pass "前端构建成功"
  else
    fail "前端构建失败，本次改动不允许上线"
    return 1
  fi
}

RC=0
case "${TARGET}" in
  backend)  run_backend  || RC=$? ;;
  frontend) run_frontend || RC=$? ;;
  all)
    run_backend  || RC=$?
    [ ${RC} -ne 0 ] || { run_frontend || RC=$?; }
    ;;
  *) echo "用法: bash deploy/ci-gate.sh [all|backend|frontend]"; exit 3 ;;
esac

echo "------------------------------------------------------------"
if [ ${RC} -eq 0 ]; then
  pass "门禁全部通过，可以执行 git push 触发自动部署"
else
  fail "门禁未通过（退出码 ${RC}），已阻止上线"
fi
exit ${RC}
