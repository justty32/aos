#!/usr/bin/env bash
# 端到端測試：真的把 daemon 跑起來，用真的 CLI 打它。
# 重點是證明 stdin 是串流的 —— 尤其是「超過單一訊框 8 MiB 上限」的輸入。
#
# 用法：e2e.sh <aos-daemon 路徑> <aos 路徑>
set -euo pipefail

daemon_binary="${1:?需要 aos-daemon 的路徑}"
cli_binary="${2:?需要 aos 的路徑}"

workspace="$(mktemp -d)"
export AOS_SOCKET="${workspace}/aos.sock"
daemon_pid=""

cleanup() {
  if [[ -n "${daemon_pid}" ]] && kill -0 "${daemon_pid}" 2>/dev/null; then
    kill "${daemon_pid}" 2>/dev/null || true
    wait "${daemon_pid}" 2>/dev/null || true
  fi
  rm -rf "${workspace}"
}
trap cleanup EXIT

failures=0
check() {
  local name="$1" expected="$2" actual="$3"
  if [[ "${expected}" == "${actual}" ]]; then
    echo "ok   - ${name}"
  else
    echo "FAIL - ${name}：預期 <${expected}>，實際 <${actual}>" >&2
    failures=$((failures + 1))
  fi
}

"${daemon_binary}" >"${workspace}/daemon.log" 2>&1 &
daemon_pid=$!

# 等 socket 出現，最多 5 秒。
for _ in $(seq 1 100); do
  [[ -S "${AOS_SOCKET}" ]] && break
  sleep 0.05
done
if [[ ! -S "${AOS_SOCKET}" ]]; then
  echo "daemon 沒有在 5 秒內建立 socket，log：" >&2
  cat "${workspace}/daemon.log" >&2
  exit 1
fi

# 1. 最基本的往返。
check "ping" "pong" "$("${cli_binary}" ping </dev/null)"

# 2. exit code 有正確傳回來（沒給命令時是 2）。
set +e
"${cli_binary}" </dev/null >/dev/null 2>&1
no_command_status=$?
set -e
check "沒給命令時 exit code 是 2" "2" "${no_command_status}"

# 3. stdin 從 pipe 進來。
check "echo 走 pipe" "hello" "$(printf 'hello' | "${cli_binary}" echo)"

# 4. stdin 從一般檔案重導向進來（epoll 收不了一般檔案，走的是另一條程式路徑）。
printf 'from a regular file' >"${workspace}/input.txt"
check "echo 走檔案重導向" "from a regular file" \
  "$("${cli_binary}" echo <"${workspace}/input.txt")"

# 5. 二進位安全：含 NUL 的資料要原封不動回來。
printf 'a\0b' >"${workspace}/binary.bin"
"${cli_binary}" echo <"${workspace}/binary.bin" >"${workspace}/binary.out"
check "含 NUL 的資料" \
  "$(cksum <"${workspace}/binary.bin")" "$(cksum <"${workspace}/binary.out")"

# 6. 這題是重點：20 MiB，遠超過單一訊框 8 MiB 的上限。
#    舊版會直接失敗，現在應該原樣流回來。
head -c $((20 * 1024 * 1024)) /dev/urandom >"${workspace}/big.bin"
"${cli_binary}" echo <"${workspace}/big.bin" >"${workspace}/big.out"
check "20 MiB 串流往返" \
  "$(cksum <"${workspace}/big.bin")" "$(cksum <"${workspace}/big.out")"

# 7. daemon 是常駐的：兩次呼叫之間狀態會累積（順便測到子命令派發）。
first_served="$("${cli_binary}" daemon status </dev/null | awk '/served/ {print $3}')"
second_served="$("${cli_binary}" daemon status </dev/null | awk '/served/ {print $3}')"
check "daemon 狀態跨呼叫累積" "$((first_served + 1))" "${second_served}"

# 8. 沒讀 stdin 的命令，也不能被還在灌資料的 client 卡死。
check "ping 忽略大量 stdin" "pong" \
  "$(head -c $((4 * 1024 * 1024)) /dev/zero | "${cli_binary}" ping)"

# 9. 只打分組名稱時，列出子命令並回傳 2。
set +e
group_output="$("${cli_binary}" daemon </dev/null 2>&1)"
group_status=$?
set -e
check "分組節點的 exit code 是 2" "2" "${group_status}"
case "${group_output}" in
  *status*stop*) echo "ok   - 分組節點列出子命令" ;;
  *) echo "FAIL - 分組節點沒列出子命令：<${group_output}>" >&2; failures=$((failures + 1)) ;;
esac

if (( failures > 0 )); then
  echo "${failures} 項端到端檢查失敗" >&2
  exit 1
fi
echo "全部端到端檢查通過"
