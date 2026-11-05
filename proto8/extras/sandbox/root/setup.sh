#!/bin/sh
# setup.sh - 沙箱的「身分層」要 root 做的事：裝 s6 到 /usr/local、建帳號 aos-run、給它一個工作的地方、讓我（$SUDO_USER）能換成它
#
#   sh setup.sh [--apply]                  帳號那一套（下面 1～4）
#   sh setup.sh --mailbox 信箱 [--apply]   只做一件：讓 aos-run 寫得到這個 LLM kernel 信箱（帳號要先建好）
#   另外三個旗標換預設值（11-01 起取代環境變數）：--me 名（我＝跑 kernel 的人；預設 $SUDO_USER 或自己，測試在假 root 裡給數字）、
#   --s6-bin 路徑（s6 的 bin；預設試驗場 /home/<我>/code/try/sandbox/s6-root/bin）、--runner 名（跑不信任函數的帳號與群組；預設 aos-run）
# 預設乾跑：只把要做的指令印出來，什麼都不動。看過沒問題再用 root 跑一次：
#   sudo sh proto8/extras/sandbox/root/setup.sh --apply
# 設計與為什麼：proto8/thinking/2026-10/24/sandbox.md（「要 root 的步驟」、S17）。
# 不要 root 的那半（bwrap 看得到什麼、斷網、s6-softlimit 上限）現在就能用，不必跑這支。
# 誰能用 kernel、碰哪些檔都交給 Linux 的使用者、群組、權限位（使用者 10-24「只要我們預先設定好使用者，設定好權限，一切都好說」）。
set -eu

APPLY=0
MAILBOX=
ME=
BIN=
RUNNER=
while [ $# -gt 0 ]; do
	case "$1" in
	--apply) APPLY=1 ;;
	--mailbox|--me|--s6-bin|--runner)
		[ $# -ge 2 ] || { echo "setup.sh: ArgumentsBad $1 needs a value" >&2; exit 1; }
		case "$1" in --mailbox) MAILBOX="$2" ;; --me) ME="$2" ;; --s6-bin) BIN="$2" ;; --runner) RUNNER="$2" ;; esac
		shift ;;
	*) echo "setup.sh: FlagUnknown $1 (usage: setup.sh [--mailbox MAILBOX] [--me NAME] [--s6-bin PATH] [--runner NAME] [--apply])" >&2; exit 1 ;;
	esac
	shift
done
ME="${ME:-${SUDO_USER:-$(id -un)}}"                 # 我（跑 kernel 的人）；--me 給測試在假 root 裡用數字
BIN="${BIN:-/home/$ME/code/try/sandbox/s6-root/bin}"   # 試驗場編好的 s6（靜態連 skalibs，只靠 libc）
RUNNER="${RUNNER:-aos-run}"                         # 跑「不信任的函數」用的帳號與它的群組（沒有家目錄、不能登入）
AREA=/srv/aos-run                                   # 它能寫的地方：放函數複本與暫時工作區

run() {
	echo "+ $*"
	if [ "$APPLY" = 1 ]; then "$@"; fi
}

if [ "$APPLY" = 1 ] && [ "$(id -u)" != 0 ]; then
	echo "setup.sh: UserBad must run as root (sudo sh $0 --apply)" >&2
	exit 1
fi
[ "$APPLY" = 1 ] || echo "# dry run: none of the commands below were run. Run as root with --apply to do them."

if [ -n "$MAILBOX" ]; then
	BOXES="$MAILBOX/tmp $MAILBOX/new $MAILBOX/cur $MAILBOX/reply $MAILBOX/reply/tmp $MAILBOX/reply/new $MAILBOX/reply/cur"
	echo "# let $RUNNER write to mailbox $MAILBOX (the kernel runs as $ME): owner $ME, group $RUNNER, 2770 (others cannot enter or read letters)"
	# shellcheck disable=SC2086
	run install -d -o "$ME" -g "$RUNNER" -m 2770 "$MAILBOX" $BOXES
	echo "#    reply/ is the reply mailbox of aos-llm ask (replies go by reply_to): the kernel sends replies in, aos-llm takes them; both sides must be able to write"
	echo "#    default ACLs on the boxes: whoever creates a letter, $ME and group $RUNNER can read and write it, regardless of umask"
	# shellcheck disable=SC2086
	run setfacl -m "d:u:$ME:rwx,d:g:$RUNNER:rwx,d:o::---" $BOXES
	echo "#    the mailbox must be <llm kernel stack>/mailbox (AOS_LLM_KERNEL = that stack, aos-llm sends into its mailbox/), somewhere $RUNNER can reach (e.g. $AREA/mailbox; not under a 700 home folder)"
	echo "#    inside the sandbox it is visible only if bound: list the mailbox in rw as {\"\$env\": \"AOS_LLM_KERNEL\", \"\$path\": \"/mailbox\"} and AOS_LLM_KERNEL in env (aos-sandbox has no separate switch)"
	echo "# to stop $RUNNER writing: chmod 700 $MAILBOX (or chgrp back to $ME's own group). A mailbox the kernel creates itself follows umask (usually 755 = others can read letters but not write),"
	echo "#    and under a 700 home folder others cannot even see it."
	echo "# check (no root needed; give aos-llm as an absolute path, sudo uses its own PATH), with the kernel running:"
	echo "#    echo '{\"request\":{\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}}' | sudo -n /usr/local/bin/s6-setuidgid $RUNNER env AOS_LLM_KERNEL=\$(dirname $MAILBOX) /absolute/aos-llm ask   # gets a reply"
	echo "#    after chmod 700 $MAILBOX the same line = aos-llm: MkdirFailed (cannot write); chmod 2770 to undo"
	exit 0
fi

echo "# 1. put the four s6 programs in /usr/local/bin; s6-setuidgid must be on root's PATH (it finds s6-applyuidgid by PATH)"
run install -o root -g root -m 755 "$BIN/s6-setuidgid" "$BIN/s6-applyuidgid" "$BIN/s6-envuidgid" "$BIN/s6-softlimit" /usr/local/bin/
echo "#    (or use the s6, execline, skalibs packages from AUR instead)"

echo "# 2. create account $RUNNER: system account, no home folder, no login"
if id "$RUNNER" >/dev/null 2>&1; then
	echo "#    $RUNNER already exists, skipped"
else
	run useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/bin/nologin "$RUNNER"
fi

echo "# 3. its work area $AREA: owner $ME, group $RUNNER, 2770 (new files take the group, both can read and write; others cannot enter)"
run install -d -o "$ME" -g "$RUNNER" -m 2770 "$AREA"

echo "# 4. let $ME run any command as $RUNNER (only as it, never as root)"
RULE="$ME ALL=(root) NOPASSWD: /usr/local/bin/s6-setuidgid $RUNNER *"
echo "#    /etc/sudoers.d/aos-run: $RULE"
if [ "$APPLY" = 1 ]; then
	printf '%s\n' "$RULE" > /etc/sudoers.d/aos-run.tmp
	chmod 440 /etc/sudoers.d/aos-run.tmp
	visudo -cf /etc/sudoers.d/aos-run.tmp
	mv /etc/sudoers.d/aos-run.tmp /etc/sudoers.d/aos-run
fi

echo "# 5. check (no root needed):"
echo "#    sudo -n /usr/local/bin/s6-setuidgid $RUNNER id            # should print uid=...($RUNNER)"
echo "#    sudo -n /usr/local/bin/s6-setuidgid $RUNNER cat ~/.bashrc  # should be Permission denied (home folder is 700)"
echo "# to undo: userdel $RUNNER; rm -r $AREA /etc/sudoers.d/aos-run; rm /usr/local/bin/s6-setuidgid /usr/local/bin/s6-applyuidgid /usr/local/bin/s6-envuidgid /usr/local/bin/s6-softlimit"
