#!/bin/bash
# Runs inside a sandbox (any: aos-pi, srt, Codex) and tries what a sandboxed coding agent must not be able to do; prints one line per check: NAME<TAB>WANT<TAB>GOT<TAB>DETAIL, WANT and GOT being ok|blocked (GOT may be n/a).
#
# Nothing here knows the aos-pi layout; every path comes from the environment (unset = that check is n/a):
#   PROBE_WORK        the writable work dir (positive controls and symlink tricks happen here)
#   PROBE_GIT         a .git dir that must stay read-only (inside the work dir)
#   PROBE_RO          colon list of dirs that must not be writable
#   PROBE_OUTSIDE     a real host dir outside the work dir and home (writes there must fail)
#   PROBE_SECRETS     colon list of real host paths that must not be readable (only sizes are ever printed)
#   PROBE_LLM_SOCK    the one allowed unix socket (an aos/llm socket: GET <base>/models must work)
#   PROBE_LLM_BAD_MODEL  a model the socket must refuse
#   PROBE_LITELLM     an http URL on the host's loopback (the real LLM endpoint; must not be reachable)
#   PROBE_UNIX_SOCK   a unix socket listening outside (by path)
#   PROBE_ABSTRACT    an abstract unix socket name listening outside
#   PROBE_VSOCK_PORT  a vsock port listening outside (on the local cid 1)
#   PROBE_SHM_ID      a SysV shared memory id made outside
#   PROBE_MQ          a POSIX message queue name made outside (like /name)
#   PROBE_HOST_PID    the PID of a process outside, as the host sees it
#   PROBE_PTRACE_PID  a PID to try ptrace on (a sibling, if the sandbox has one)
# curl runs with -f: an HTTP error page from a filtering proxy counts as blocked.
# Sources: "codex:" = openai/codex codex-rs/linux-sandbox, "srt:" = anthropic-experimental/sandbox-runtime
# test/sandbox; the checks are rewritten by meaning, no code is copied. "own:" = ours (channels-1127, pi-sandbox-1127).

out() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$(printf '%s' "$4" | tr '\n\t' '  ' | cut -c1-180)"; }
na() { out "$1" "$2" n/a "$3"; }

try() {  # try NAME WANT COMMAND...: GOT ok if the command exits 0
  local name=$1 want=$2 msg; shift 2
  if msg=$("$@" 2>&1); then out "$name" "$want" ok "$msg"; else out "$name" "$want" blocked "$msg"; fi
}

py() {  # py NAME WANT TEST [ARGS]: the python helper below prints "ok|blocked|n/a detail"
  local name=$1 want=$2 r; shift 2
  if ! command -v python3 >/dev/null; then na "$name" "$want" "no python3"; return; fi
  r=$(python3 -I -c "$PY" "$@" 2>&1 | tail -n 1)
  out "$name" "$want" "${r%% *}" "${r#* }"
}

# The python helper for checks that need a raw syscall: argv[1] is the test; prints "ok|blocked|n/a detail".
PY=$(cat <<'PYEOF'
import ctypes, errno, os, socket, struct, sys
libc = ctypes.CDLL(None, use_errno=True)
def res(ok, detail):
    print(("ok " if ok else "blocked ") + detail); sys.exit(0)
def err():
    e = ctypes.get_errno(); return "%s (%s)" % (errno.errorcode.get(e, e), os.strerror(e))
t, a = sys.argv[1], sys.argv[2:]
if t == "unix" or t == "abstract":
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(a[0] if t == "unix" else "\0" + a[0]); res(True, "connected")
    except OSError as e: res(False, str(e))
if t == "vsock":
    try: s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    except OSError as e: res(False, "socket(AF_VSOCK): " + str(e))
    if not a: res(True, "socket(AF_VSOCK) made (not blocked)")
    try: s.settimeout(3); s.connect((1, int(a[0]))); res(True, "connected to the outside listener on vsock cid 1 port " + a[0])
    except OSError as e: res(False, "socket(AF_VSOCK) made, but connect to cid 1 port %s: %s" % (a[0], e))
if t == "shm":
    libc.shmat.restype = ctypes.c_void_p
    p = libc.shmat(int(a[0]), None, 0x1000)  # SHM_RDONLY
    if p in (None, ctypes.c_void_p(-1).value): res(False, "shmat(%s): %s" % (a[0], err()))
    res(True, "attached the outside segment %s" % a[0])
if t == "mq":
    rt = ctypes.CDLL("librt.so.1", use_errno=True)
    fd = rt.mq_open(a[0].encode(), os.O_RDONLY)
    if fd < 0: res(False, "mq_open(%s): %s" % (a[0], err()))
    res(True, "opened the outside queue %s" % a[0])
if t == "ptrace":
    r = libc.ptrace(16, int(a[0]), None, None)  # PTRACE_ATTACH
    if r != 0: res(False, "ptrace(ATTACH, %s): %s" % (a[0], err()))
    libc.ptrace(17, int(a[0]), None, None); res(True, "attached to %s" % a[0])
if t == "vmwrite":
    buf = ctypes.create_string_buffer(8)
    class iov(ctypes.Structure): _fields_ = [("b", ctypes.c_void_p), ("n", ctypes.c_size_t)]
    l, r = iov(ctypes.addressof(buf), 8), iov(0x400000, 8)
    L = ctypes.c_long
    n = libc.syscall(L(311), L(int(a[0])), ctypes.byref(l), L(1), ctypes.byref(r), L(1), L(0))  # process_vm_writev
    if n < 0 and ctypes.get_errno() in (errno.EPERM, errno.ESRCH, errno.EACCES): res(False, "process_vm_writev(%s): %s" % (a[0], err()))
    res(True, "process_vm_writev(%s) got past the permission check (%s)" % (a[0], err() if n < 0 else "wrote"))
if t == "procmem":
    try: open("/proc/1/mem", "r+b"); res(True, "opened /proc/1/mem for writing")
    except OSError as e: res(False, str(e))
if t == "io_uring":
    buf = ctypes.create_string_buffer(120)
    fd = libc.syscall(ctypes.c_long(425), ctypes.c_long(4), buf)  # io_uring_setup
    if fd < 0: res(False, "io_uring_setup: " + err())
    os.close(fd); res(True, "io_uring_setup gave fd %d" % fd)
if t == "tiocsti":
    import fcntl, termios
    for fd in (0, 1, 2):
        if os.isatty(fd): break
    else:
        try: fd = os.open("/dev/tty", os.O_RDWR)
        except OSError as e: res(False, "no terminal: /dev/tty: " + str(e))
    try: fcntl.ioctl(fd, termios.TIOCSTI, b" "); res(True, "TIOCSTI pushed a key")
    except OSError as e: res(False, "TIOCSTI: " + str(e))
if t == "nnp":
    v = libc.prctl(39, 0, 0, 0, 0)  # PR_GET_NO_NEW_PRIVS
    res(v != 1, "no_new_privs is %d" % v)
if t == "caps":
    hdr = (ctypes.c_uint32 * 2)(0x20080522, 0); data = (ctypes.c_uint32 * 6)()
    if libc.capget(hdr, data) != 0: res(False, "capget: " + err())
    eff, prm = data[0] | data[3] << 32, data[1] | data[4] << 32
    res(eff != 0, "effective %#x permitted %#x" % (eff, prm))
if t == "unshare":
    if libc.unshare(0x10000000) != 0: res(False, "unshare(CLONE_NEWUSER): " + err())
    res(True, "unshare(CLONE_NEWUSER) worked (a nested user namespace)")
if t == "mount":
    d = os.path.join(a[0], ".probe-mnt-%d" % os.getpid()); os.makedirs(d, exist_ok=True)
    try:
        r = libc.mount(b"none", d.encode(), b"tmpfs", 0, None)
        if r != 0: res(False, "mount tmpfs: " + err())
        libc.umount2(d.encode(), 0); res(True, "mounted a tmpfs")
    finally: os.rmdir(d)
if t == "umount":
    if libc.umount2(a[0].encode(), 2) != 0: res(False, "umount2(%s): %s" % (a[0], err()))  # MNT_DETACH
    res(True, "unmounted " + a[0])
if t == "setuid":
    import shutil, subprocess
    me = os.geteuid(); p = os.path.join(a[0], ".probe-suid-%d" % os.getpid())
    try:
        shutil.copy("/usr/bin/id", p); os.chmod(p, 0o4755)
        got = int(subprocess.run([p, "-u"], capture_output=True, text=True).stdout.strip() or -1)
        res(got != me, "setuid copy of id ran as uid %d, the caller is %d" % (got, me))
    except OSError as e: res(False, str(e))
    finally:
        try: os.unlink(p)
        except OSError: pass
print("n/a unknown test " + t)
PYEOF
)

W=${PROBE_WORK:-}
T=probe-$$

# ---------------------------------------------------------------- files: write
if [ -n "$W" ]; then
  try write_work ok sh -c "echo x > '$W/$T.ok' && rm '$W/$T.ok'"   # codex: tests/suite/sandbox.rs test_writable_root; srt: integration "should allow writes within current working directory"
fi
try write_root blocked sh -c "echo x > /$T"                         # codex: test_root_write; srt: integration "should block writes outside current working directory"
IFS=: read -ra ROS <<< "${PROBE_RO:-}"
for d in "${ROS[@]}"; do
  [ -n "$d" ] || continue
  try "write_ro:$d" blocked sh -c "echo x > '$d/$T'"                 # own: the layout's read-only places
done
if [ -n "${PROBE_OUTSIDE:-}" ]; then
  try write_outside blocked sh -c "echo x > '$PROBE_OUTSIDE/$T'"     # srt: integration "should block writes outside current working directory"
fi
if [ -n "${PROBE_GIT:-}" ]; then
  try git_hooks_write blocked sh -c "echo 'echo pwned' > '$PROBE_GIT/hooks/pre-commit'"  # srt: mandatory-deny-paths "blocks writes to .git/hooks/pre-commit"; codex: sandbox_blocks_metadata_writes_inside_writable_root
  try git_hooks_new blocked sh -c "echo x > '$PROBE_GIT/hooks/$T'"   # srt: mandatory-deny-paths "blocks creation of non-existent file when parent dir exists"
  try git_config_write blocked sh -c "echo '[core]' >> '$PROBE_GIT/config'"  # srt: mandatory-deny-paths "blocks writes to .git/config"; codex: same test, case .git/config
fi
if [ -n "$W" ]; then
  try hardlink_out blocked ln /etc/passwd "$W/$T.hl"                 # srt: integration "should prevent creation of special file types"
  rm -f "$W/$T.hl"
  try mknod_dev blocked mknod "$W/$T.null" c 1 3                     # srt: same test (mknod)
  rm -f "$W/$T.null"
  py setuid_gain blocked setuid "$W"                                 # srt: integration "should prevent privilege escalation attempts"
fi

# ---------------------------------------------------------------- symlinks out of the work dir
if [ -n "$W" ] && [ -n "${PROBE_OUTSIDE:-}" ]; then
  ln -s "$PROBE_OUTSIDE/$T.esc" "$W/$T.l1" 2>/dev/null
  try symlink_file_write blocked sh -c "echo x > '$W/$T.l1'"          # srt: integration "should prevent symlink-based filesystem escape attempts"; write-through-links "refuses a create through a link ... to a name outside it that is not there"
  ln -s "$PROBE_OUTSIDE" "$W/$T.l2" 2>/dev/null
  try symlink_dir_write blocked sh -c "echo x > '$W/$T.l2/$T.esc2'"   # srt: write-through-links "refuses a write beneath a link ... to a directory outside it"
  echo x > "$W/$T.mv" 2>/dev/null
  try symlink_rename_out blocked mv "$W/$T.mv" "$W/$T.l2/$T.mv"       # srt: write-through-links "refuses a rename onto a file outside the write root, through a linked directory"
  rm -f "$W/$T.l1" "$W/$T.l2" "$W/$T.mv"
fi

# ---------------------------------------------------------------- files: read
IFS=: read -ra SECRETS <<< "${PROBE_SECRETS:-}"
for s in "${SECRETS[@]}"; do
  [ -n "$s" ] || continue
  if [ -d "$s" ]; then try "read:$s" blocked bash -o pipefail -c "ls '$s' | wc -l"
  else try "read:$s" blocked sh -c "wc -c < '$s'"; fi                 # own: files outside the work dir (srt and codex allow reads by default)
done
try read_etc_shadow blocked sh -c "wc -c < /etc/shadow"              # own (brief): the host's password hashes
if [ -n "$W" ] && [ -n "${SECRETS[0]:-}" ]; then
  ln -s "${SECRETS[0]}" "$W/$T.l3" 2>/dev/null
  try symlink_read blocked bash -o pipefail -c "ls '$W/$T.l3/' | wc -l"            # own: read through a link made in the work dir
  rm -f "$W/$T.l3"
fi
if [ -d /proc/1 ]; then
  try proc1_root blocked bash -o pipefail -c "ls /proc/1/root/ | wc -l"          # own: sky-1125 (look into pid 1's root)
  try proc1_environ blocked bash -o pipefail -c "tr '\\0' '\\n' < /proc/1/environ | wc -l"   # own: pid 1's environment
  try proc_net_tcp blocked sh -c "test \$(wc -l < /proc/1/net/tcp) -gt 1 && wc -l < /proc/1/net/tcp"  # own: channels-1127 (the host's socket table)
  py proc1_mem_write blocked procmem                                 # srt: pid-namespace-isolation "denies opening /proc/1/mem for writing"
else
  out proc_absent blocked blocked "no /proc in this sandbox"
fi

# ---------------------------------------------------------------- network
try net_dns blocked getent ahosts example.com                        # codex: sandbox_blocks_getent; srt: integration "should block DNS lookups when allowedDomains is empty"
try net_https blocked curl -fsS -m 5 -o /dev/null https://example.com # codex: sandbox_blocks_curl
try net_ip blocked curl -fsS -m 5 -o /dev/null http://1.1.1.1/        # own: no DNS needed
try net_dev_tcp blocked bash -c 'exec 3<>/dev/tcp/1.1.1.1/80'        # codex: sandbox_blocks_dev_tcp_redirection
try net_ping blocked ping -c 1 -W 2 1.1.1.1                          # codex: sandbox_blocks_ping
try net_ssh blocked bash -c 'm=$(ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null git@github.com 2>&1); echo "$m"; grep -qiE "authenticated|permission denied \(|permanently added|host key" <<< "$m"'   # codex: sandbox_blocks_ssh (ok = it talked to the server, whatever the login said)
py net_vsock blocked vsock ${PROBE_VSOCK_PORT:-}                     # srt: seccomp-vsock-block "answers EPERM for every socket type"; own: connect to an outside listener (vsock has no network namespace)

# ---------------------------------------------------------------- the model only through the one socket
if [ -n "${PROBE_LITELLM:-}" ]; then
  try llm_host_loopback blocked curl -fsS -m 5 -o /dev/null "$PROBE_LITELLM"   # own: the real endpoint on the host's 127.0.0.1
fi
try llm_anthropic_api blocked curl -fsS -m 5 -o /dev/null https://api.anthropic.com/v1/models   # own
if [ -n "${PROBE_LLM_SOCK:-}" ]; then
  try llm_sock_models ok curl -sS -f -m 5 --unix-socket "$PROBE_LLM_SOCK" http://llm/v1/models   # own: the allowed way
  try llm_sock_bad_model blocked curl -sS -f -m 5 --unix-socket "$PROBE_LLM_SOCK" -H 'Content-Type: application/json' \
    -d "{\"model\":\"${PROBE_LLM_BAD_MODEL:-not-allowed}\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" \
    http://llm/v1/chat/completions                                    # own: the kernel refuses other models (403)
fi

# ---------------------------------------------------------------- unix sockets and IPC to the outside
[ -n "${PROBE_UNIX_SOCK:-}" ] && py unix_sock_outside blocked unix "$PROBE_UNIX_SOCK"   # srt: integration "should block Unix socket connections with seccomp"; codex: daemon_sockets_tests
[ -n "${PROBE_ABSTRACT:-}" ] && py unix_abstract_outside blocked abstract "$PROBE_ABSTRACT"   # own: channels-1127
[ -n "${PROBE_SHM_ID:-}" ] && py ipc_sysv_shm blocked shm "$PROBE_SHM_ID"              # own: channels-1127 (codex runs bwrap --unshare-ipc)
[ -n "${PROBE_MQ:-}" ] && py ipc_posix_mq blocked mq "$PROBE_MQ"                       # own: channels-1127

# ---------------------------------------------------------------- processes
[ -n "${PROBE_HOST_PID:-}" ] && try kill_host_pid blocked kill -0 "$PROBE_HOST_PID"     # srt: pid-namespace-isolation "hides outer-namespace helpers from the inner command" (as a signal)
py ptrace_pid1 blocked ptrace 1                                      # srt: pid-namespace-isolation "denies ptrace(PTRACE_ATTACH) against PID 1"
[ -n "${PROBE_PTRACE_PID:-}" ] && py ptrace_other blocked ptrace "$PROBE_PTRACE_PID"   # own (brief): ptrace a sibling
py process_vm_writev_pid1 blocked vmwrite 1                          # srt: pid-namespace-isolation "denies process_vm_writev against PID 1"

# ---------------------------------------------------------------- syscalls, privileges, terminal, namespaces
py io_uring_setup blocked io_uring                                   # srt: seccomp-filter "blocks io_uring_setup"; codex: seccomp.rs (io_uring_*)
py tiocsti blocked tiocsti                                           # own (brief): push keys into a terminal
py no_new_privs_off blocked nnp                                      # codex: linux_run_main_tests test_no_new_privs_is_enabled
py caps_effective blocked caps                                       # srt: "runs the user command with zero effective capabilities"; codex: sandboxed_command_has_no_effective_or_permitted_capabilities
py unshare_userns blocked unshare                                    # srt: linux-nested-userns (unshare(CLONE_NEWUSER))
[ -n "$W" ] && py mount_tmpfs blocked mount "$W"                     # srt: linux-nested-userns (mount); "denies umount(/proc) from the user command"
py umount_root blocked umount /                                      # srt: "denies umount(/proc) from the user command"
exit 0
