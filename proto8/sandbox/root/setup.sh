#!/bin/sh
# setup.sh - 沙箱的「身分層」要 root 做的事：裝 s6 到 /usr/local、建帳號 aos-run、給它一個工作的地方、讓我（$SUDO_USER）能換成它
#
# 預設乾跑：只把要做的指令印出來，什麼都不動。看過沒問題再用 root 跑一次：
#   sudo sh proto8/sandbox/root/setup.sh --apply
# 設計與為什麼：proto8/thinking/2026-10-24-sandbox.md（「要 root 的步驟」）。
# 不要 root 的那半（bwrap 看得到什麼、斷網、s6-softlimit 上限）現在就能用，不必跑這支。
set -eu

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1
ME="${SUDO_USER:-$(id -un)}"
BIN="${S6_BIN:-/home/$ME/code/try/sandbox/s6-root/bin}"   # 試驗場編好的 s6（靜態連 skalibs，只靠 libc）
RUNNER=aos-run                                      # 跑「不信任的函數」用的帳號（沒有家目錄、不能登入）
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
