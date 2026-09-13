# 用法：source playground/env.sh   （每開一個新終端機都要 source 一次）
# 只做三件事：把遊樂場與五個 proto 的指令放進 PATH、決定遊樂場放哪、決定 daemon 的家。
_AOS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")/.." && pwd)"
export AOS_ROOT="$_AOS_ROOT"
export PATH="$AOS_ROOT/playground:$AOS_ROOT/proto4-3:$AOS_ROOT/proto4-4:$AOS_ROOT/proto4-5:$AOS_ROOT/proto4-6:$AOS_ROOT/proto4-7:$HOME/.local/bin:$PATH"
export AOS_PLAY="${AOS_PLAY:-$HOME/aos-play}"      # 遊樂場，在 repo 外面，玩壞了整個資料夾刪掉就好
export AOS_DAEMON_HOME="$AOS_PLAY/home"            # daemon 的家（硬體）
export K="$AOS_PLAY/K"                              # kernel 的家
echo "aos 遊樂場 AOS_PLAY=$AOS_PLAY"
echo "kernel 的家 K=$K   daemon 的家 AOS_DAEMON_HOME=$AOS_DAEMON_HOME"
echo "指令：play-up 上電開機 ／ play-down 收工 ／ play-reset 全部重來"
