#!/bin/sh
# setup.sh - 沙箱的「身分層」要 root 做的事：裝 s6 到 /usr/local、建帳號 aos-run、給它一個工作的地方、讓我（$SUDO_USER）能換成它
#
#   sh setup.sh [--apply]                  帳號那一套（下面 1～4）
#   sh setup.sh --mailbox 信箱 [--apply]   只做一件：讓 aos-run 寫得到這個 LLM kernel 信箱（帳號要先建好）
# 預設乾跑：只把要做的指令印出來，什麼都不動。看過沒問題再用 root 跑一次：
#   sudo sh proto8/extras/sandbox/root/setup.sh --apply
# 設計與為什麼：proto8/thinking/2026-10-24-sandbox.md（「要 root 的步驟」、S17）。
# 不要 root 的那半（bwrap 看得到什麼、斷網、s6-softlimit 上限）現在就能用，不必跑這支。
# 誰能用 kernel、碰哪些檔都交給 Linux 的使用者、群組、權限位（使用者 10-24「只要我們預先設定好使用者，設定好權限，一切都好說」）。
set -eu

APPLY=0
MAILBOX=
while [ $# -gt 0 ]; do
	case "$1" in
	--apply) APPLY=1 ;;
	--mailbox) [ $# -ge 2 ] || { echo "setup.sh: ArgumentsBad --mailbox 後面要有信箱資料夾" >&2; exit 1; }; MAILBOX="$2"; shift ;;
	*) echo "setup.sh: FlagUnknown $1（用法：setup.sh [--mailbox 信箱] [--apply]）" >&2; exit 1 ;;
	esac
	shift
done
ME="${AOS_ME:-${SUDO_USER:-$(id -un)}}"            # 我（跑 kernel 的人）；AOS_ME 給測試在假 root 裡用數字
BIN="${AOS_S6_BIN:-/home/$ME/code/try/sandbox/s6-root/bin}"   # 試驗場編好的 s6（靜態連 skalibs，只靠 libc）
RUNNER="${AOS_RUNNER:-aos-run}"                     # 跑「不信任的函數」用的帳號與它的群組（沒有家目錄、不能登入）
AREA=/srv/aos-run                                   # 它能寫的地方：放函數複本與暫時工作區

run() {
	echo "+ $*"
	if [ "$APPLY" = 1 ]; then "$@"; fi
}

if [ "$APPLY" = 1 ] && [ "$(id -u)" != 0 ]; then
	echo "setup.sh: UserBad 要用 root 跑（sudo sh $0 --apply）" >&2
	exit 1
fi
[ "$APPLY" = 1 ] || echo "# 乾跑：下面的指令都沒執行。用 root 加 --apply 才會真的做。"

if [ -n "$MAILBOX" ]; then
	BOXES="$MAILBOX/tmp $MAILBOX/new $MAILBOX/cur $MAILBOX/done $MAILBOX/reply $MAILBOX/reply/tmp $MAILBOX/reply/new $MAILBOX/reply/cur"
	echo "# 讓 $RUNNER 寫得到信箱 $MAILBOX（kernel 用 $ME 跑）：擁有者 $ME、群組 $RUNNER、2770（別人進不來、看不到信）"
	# shellcheck disable=SC2086
	run install -d -o "$ME" -g "$RUNNER" -m 2770 "$MAILBOX" $BOXES
	echo "#    reply/ 是 aos-llm-send 的回信信箱（10-30 回信走 reply_to）：kernel 寄回信進去、閘門拿，兩邊都要寫得到"
	echo "#    四格加預設 ACL：誰建的信（閘門建資料夾、kernel 寫回信）都讓 $ME 與群組 $RUNNER 讀寫得到，不看各自的 umask"
	# shellcheck disable=SC2086
	run setfacl -m "d:u:$ME:rwx,d:g:$RUNNER:rwx,d:o::---" $BOXES
	echo "#    信箱要放在 $RUNNER 走得到的地方（例 $AREA/mailbox；在 700 的家目錄底下它走不進去）"
	echo "#    沙箱裡要綁進來才看得到：設定的 rw 列 $MAILBOX、env 列 AOS_KERNEL（aos-sandbox 不另設開關）"
	echo "# 不讓 $RUNNER 寫：chmod 700 $MAILBOX（或 chgrp 回 $ME 自己的群組）。kernel 自己建的信箱照 umask（多半 755＝別人讀得到信、寫不進），"
	echo "#    放在 700 的家目錄底下就連看都看不到。"
	echo "# 驗（不用 root；aos-llm-send 寫絕對路徑，sudo 用自己的 PATH）：kernel 開著時"
	echo "#    sudo -n /usr/local/bin/s6-setuidgid $RUNNER env AOS_KERNEL=$MAILBOX /絕對/aos-llm-send 單子.json   # 拿到回信"
	echo "#    chmod 700 $MAILBOX 之後同一行＝aos-llm-send: MkdirFailed（寫不進）；chmod 2770 改回來"
	exit 0
fi

echo "# 1. 把要用的四支 s6 放到 /usr/local/bin——s6-setuidgid 要在 root 的 PATH 上（它照 PATH 叫 s6-applyuidgid）"
run install -o root -g root -m 755 "$BIN/s6-setuidgid" "$BIN/s6-applyuidgid" "$BIN/s6-envuidgid" "$BIN/s6-softlimit" /usr/local/bin/
echo "#    （或改用 AUR 的 s6、execline、skalibs 套件，二選一）"

echo "# 2. 建帳號 $RUNNER：系統帳號、沒有家目錄、不能登入"
if id "$RUNNER" >/dev/null 2>&1; then
	echo "#    $RUNNER 已經有了，跳過"
else
	run useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/bin/nologin "$RUNNER"
fi

echo "# 3. 它工作的地方 $AREA：擁有者 $ME、群組 $RUNNER、2770（新檔跟著群組，兩邊都能讀寫；別人進不來）"
run install -d -o "$ME" -g "$RUNNER" -m 2770 "$AREA"

echo "# 4. 讓 $ME 能「換成 $RUNNER 跑任何指令」（只能換成它，換不成 root）"
RULE="$ME ALL=(root) NOPASSWD: /usr/local/bin/s6-setuidgid $RUNNER *"
echo "#    /etc/sudoers.d/aos-run：$RULE"
if [ "$APPLY" = 1 ]; then
	printf '%s\n' "$RULE" > /etc/sudoers.d/aos-run.tmp
	chmod 440 /etc/sudoers.d/aos-run.tmp
	visudo -cf /etc/sudoers.d/aos-run.tmp
	mv /etc/sudoers.d/aos-run.tmp /etc/sudoers.d/aos-run
fi

echo "# 5. 驗（不用 root）："
echo "#    sudo -n /usr/local/bin/s6-setuidgid $RUNNER id            # 應該印 uid=…($RUNNER)"
echo "#    sudo -n /usr/local/bin/s6-setuidgid $RUNNER cat ~/.bashrc  # 應該 Permission denied（家目錄 700）"
echo "# 拆掉：userdel $RUNNER; rm -r $AREA /etc/sudoers.d/aos-run; rm /usr/local/bin/s6-setuidgid /usr/local/bin/s6-applyuidgid /usr/local/bin/s6-envuidgid /usr/local/bin/s6-softlimit"
