# using-aos-agent.sh - 給人的殼 source 用（不是跑）：之後直接打 say／listen／chat／status，像命名空間（11-04 aos-agent 02）。
#
#   source proto8/lib/aos/apps/agent/using-aos-agent.sh bob  # 帶名字＝export AOS_AGENT=bob；不帶＝只定義函數
#   say 現在幾點 && listen                             # ＝aos-agent say 現在幾點 && aos-agent listen
#   echo 題 | say && listen > 答.txt                   # 11-05：say 沒給話＝讀 stdin（一則）；listen 的 stdout 只有回答
#   cat 長題.md | say > /dev/null && listen | less
#   say --target ann 你好                             # 旗標照常過
#   chat                                              # 一直聊，Ctrl-C 退出
#
# 只定義 say、listen、chat、status 四個（跟系統指令不撞）；ctl rm、ctl ls、open、ctl start、ctl stop 這些照打 aos-agent …（rm 尤其危險）。
# 帶的名字不查表、不報錯；不改 PATH。函數叫的是同一個家的 bin/aos-agent（這份檔在 <家>/lib/aos/apps/agent/，往上四層；bash、zsh 都能 source）。
# AOS_DAEMON 不替你設（使用者 11-21「-d不能省略，要麼-d明確指定，要麼export AOS_DAEMON指定」）：先 export AOS_DAEMON=<daemon 的 $AOS_STACK>；
#   沒設，函數照樣定義；站在 <daemon stack>/procs/<名>/ 裡 aos-agent 自己往上兩層找得到 daemon，別處報 DaemonMissing。不帶名字、cd 進 agent 的 stack 也找得到對象。
if [ -n "${BASH_SOURCE:-}" ]; then _aos_agent_here=${BASH_SOURCE[0]}; else _aos_agent_here=$0; fi
_aos_agent_bin="$(cd "$(dirname "$_aos_agent_here")/../../../.." && pwd)/bin/aos-agent"
unset _aos_agent_here
if [ -n "${1:-}" ]; then export AOS_AGENT="$1"; fi
say()    { "$_aos_agent_bin" say "$@"; }
listen() { "$_aos_agent_bin" listen "$@"; }
chat()   { "$_aos_agent_bin" chat "$@"; }
status() { "$_aos_agent_bin" ctl status "$@"; }
