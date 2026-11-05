# using-aos-agent.sh - 給人的殼 source 用（不是跑）：之後直接打 say／listen／chat／status，像命名空間（11-04 aos-agent 02）。
#
#   source proto8/extras/agent/using-aos-agent.sh bob   # 帶名字＝export AOS_AGENT=bob；不帶＝只定義函數
#   say 現在幾點 && listen                             # ＝aos-agent say 現在幾點 && aos-agent listen
#   say --target ann 你好                             # 旗標照常過
#   chat                                              # 一直聊，Ctrl-C 退出
#
# 只定義 say、listen、chat、status 四個（跟系統指令不撞）；rm、ls、open、start、stop 這些照打 aos-agent …（rm 尤其危險）。
# 帶的名字不查表、不報錯；不改 PATH。函數叫的是這份檔旁邊的 bin/aos-agent（bash、zsh 都能 source）。
# AOS_DAEMON 沒設＝export 成 $PWD/.stack（11-05 portable-flow 題 3：在 ws 裡 source，daemon 在 ws 起的 stack 就是它；
#   不查在不在，不對就 aos-agent 報 DaemonMissing）；有設照用。
if [ -n "${BASH_SOURCE:-}" ]; then _aos_agent_here=${BASH_SOURCE[0]}; else _aos_agent_here=$0; fi
_aos_agent_bin="$(cd "$(dirname "$_aos_agent_here")" && pwd)/bin/aos-agent"
unset _aos_agent_here
if [ -n "${1:-}" ]; then export AOS_AGENT="$1"; fi
if [ -z "${AOS_DAEMON:-}" ]; then export AOS_DAEMON="$PWD/.stack"; fi
say()    { "$_aos_agent_bin" say "$@"; }
listen() { "$_aos_agent_bin" listen "$@"; }
chat()   { "$_aos_agent_bin" chat "$@"; }
status() { "$_aos_agent_bin" status "$@"; }
