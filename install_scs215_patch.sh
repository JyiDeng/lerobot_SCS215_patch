#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "用法：bash install_scs215_patch.sh 原生lerobot目录 [新环境名称]" >&2
  echo "示例：bash install_scs215_patch.sh ../lerobot-scs215 lerobot-scs215" >&2
  exit 1
fi

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(cd "$1" 2>/dev/null && pwd)" || {
  echo "找不到目标目录：$1" >&2
  exit 2
}
ENV_NAME="${2:-lerobot-scs215}"

if [[ ! -f "${TARGET_DIR}/pyproject.toml" || ! -d "${TARGET_DIR}/src/lerobot" ]]; then
  echo "目标目录不是LeRobot源码仓库：${TARGET_DIR}" >&2
  exit 3
fi

BACKUP_DIR="${TARGET_DIR}/.scs215-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}/src/lerobot/motors/feetech" \
  "${BACKUP_DIR}/src/lerobot/motors" \
  "${BACKUP_DIR}/src/lerobot/robots/so_follower" \
  "${BACKUP_DIR}/tools"

backup_and_replace() {
  local source_file="$1"
  local target_file="$2"
  local backup_file="$3"

  if [[ -f "${target_file}" ]]; then
    cp "${target_file}" "${backup_file}"
  fi
  cp "${source_file}" "${target_file}"
  echo "已替换 ${target_file#${TARGET_DIR}/}"
}

backup_and_replace \
  "${BUNDLE_DIR}/tables.py" \
  "${TARGET_DIR}/src/lerobot/motors/feetech/tables.py" \
  "${BACKUP_DIR}/src/lerobot/motors/feetech/tables.py"

backup_and_replace \
  "${BUNDLE_DIR}/motors_bus.py" \
  "${TARGET_DIR}/src/lerobot/motors/motors_bus.py" \
  "${BACKUP_DIR}/src/lerobot/motors/motors_bus.py"

backup_and_replace \
  "${BUNDLE_DIR}/so_follower.py" \
  "${TARGET_DIR}/src/lerobot/robots/so_follower/so_follower.py" \
  "${BACKUP_DIR}/src/lerobot/robots/so_follower/so_follower.py"

backup_and_replace \
  "${BUNDLE_DIR}/scs215_registers.py" \
  "${TARGET_DIR}/tools/scs215_registers.py" \
  "${BACKUP_DIR}/tools/scs215_registers.py"

chmod +x "${TARGET_DIR}/tools/scs215_registers.py"

echo
echo "替换完成。原文件备份在：${BACKUP_DIR}"
echo "目标仓库：${TARGET_DIR}"
echo "环境名称：${ENV_NAME}"
echo "请进入目标仓库后，按照项目安装说明创建或激活 Conda 环境。"
