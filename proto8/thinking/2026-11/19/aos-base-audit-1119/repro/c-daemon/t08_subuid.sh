# t08: limits.user "sub:N" for real: uid in /proc, what it can read/write outside its cell (read-only probes, no content printed), mail, owners, stop/rm/shutdown, orphans.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t08 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/peer.sh" 'echo "peer secret-ish line" > "$AOS_STACK/peer_note.txt"; exec sleep 600'
cat > "$D/probe.sh" <<'EOF'
#!/bin/sh
# probe body run as a subuid: report what it can do, never print file contents
O="$AOS_STACK/probe.txt"; : > "$O"
r() { if [ -r "$1" ] && head -c1 "$1" >/dev/null 2>&1; then echo "READ yes $1" >> "$O"; else echo "READ no  $1" >> "$O"; fi; }
l() { if ls "$1" >/dev/null 2>&1; then echo "LIST yes $1" >> "$O"; else echo "LIST no  $1" >> "$O"; fi; }
w() { if ( : > "$1/.probe_w" ) 2>/dev/null; then echo "WRITE yes $1" >> "$O"; rm -f "$1/.probe_w"; else echo "WRITE no  $1" >> "$O"; fi; }
echo "id: $(id)" >> "$O"
grep -E '^(Uid|Gid|Groups):' /proc/self/status >> "$O"
echo "HOME=$HOME" >> "$O"
r "$PEER/peer_note.txt"; r "$PEER/stderr.txt"; l "$PEER"
r "$SUB6/probe.txt"; l "$SUB6"
r "$AOS_DAEMON/procs_state.json"; l "$AOS_DAEMON/procs_requests/new"
r "$ROOTD/daemon.json"; r "$ROOTD/peer.sh"
r "$HOMEDIR/repo/aos/README.md"; l "$HOMEDIR/repo/aos"; l "$HOMEDIR/repo/aos/proto8"
r "$HOMEDIR/.bashrc"; r "$HOMEDIR/.profile"; r "$HOMEDIR/.gitconfig"; l "$HOMEDIR/.ssh"; l "$HOMEDIR/.config"; l "$HOMEDIR"
r "$HOMEDIR/.aos/scratch/aos-base-audit-1119/BRIEF.md"; l "$HOMEDIR/.aos/scratch"; l "$HOMEDIR/.aos"
w "$PEER"; w "$AOS_DAEMON"; w "$AOS_DAEMON/procs_requests/new"; w "$ROOTD"; w /tmp; w "$AOS_STACK"; w "$HOMEDIR/.aos/scratch"
kill -0 "$PEERPID" 2>/dev/null && echo "SIGNAL peer yes" >> "$O" || echo "SIGNAL peer no" >> "$O"
kill -0 "$DPID" 2>/dev/null && echo "SIGNAL daemon yes" >> "$O" || echo "SIGNAL daemon no" >> "$O"
echo "mine" > "$AOS_STACK/made_by_sub.txt"
if timeout 8 aos-daemon-ctl -d "$AOS_DAEMON" ping >> "$O" 2>&1; then echo "MAIL ping ok" >> "$O"; else echo "MAIL ping failed" >> "$O"; fi
sleep 601 & echo $! > "$AOS_STACK/kid.pid"
echo done >> "$O"
exec sleep 600
EOF
chmod +x "$D/probe.sh"
ctl add --name peer "$D/peer.sh" >/dev/null; waitphase peer running; PEERPID=$(ppid_of peer)
# sub6 first so sub5 can probe it; the subuid env whitelist drops unknown vars, so pass them as env(1) args
ARGS="PEER=$S/procs/peer SUB6=$S/procs/sub6 ROOTD=$D HOMEDIR=$HOME PEERPID=$PEERPID DPID=$(dpid) $D/probe.sh"
ctl add --name sub6 --limits '{"user": "sub:6"}' /usr/bin/env -- $ARGS; sleep 1.5
ctl add --name sub5 --limits '{"user": "sub:5", "procs": 20}' /usr/bin/env -- $ARGS
sleep 4; rows
echo "== letter format check (mailbox warnings)"; python3 -c "import json;print(json.load(open('$S/state_flux.json')).get('mailbox_warning'))"
for n in sub5 sub6; do
  P=$(ppid_of $n); echo "== $n pid $P"; grep -E '^(Uid|Gid):' /proc/$P/status 2>/dev/null | tr '\n' ' '; echo
  echo "  cell perms: $(stat -c '%a %U:%G' $S/procs/$n)  getfacl-ish: $(python3 -c "import os;print(len(os.getxattr('$S/procs/$n','system.posix_acl_access')))" 2>&1) bytes ACL"
  echo "  files: $(ls -ln $S/procs/$n | awk 'NR>1{print $3":"$4" "$9}' | tr '\n' ' ')"
done
echo "== sub5 probe results"; cat $S/procs/sub5/probe.txt
echo "== user (me) can still read/append its file? $(cat $S/procs/sub5/made_by_sub.txt 2>&1) / $(echo x >> $S/procs/sub5/made_by_sub.txt 2>&1 && echo append-ok)"
K5=$(cat $S/procs/sub5/kid.pid 2>/dev/null); P5=$(ppid_of sub5)
echo "== rm sub5: main $P5 kid $K5"; t0=$(now); ctl rm sub5 >/dev/null; for i in $(seq 60); do [ "$(phase sub5)" = NOROW ] && break; sleep 0.2; done
echo "  after $(since $t0)s: row $(phase sub5); main $(alive $P5); kid (sleep 601 inside the sub ns) $(alive $K5) uid=$(grep ^Uid: /proc/$K5/status 2>/dev/null | awk '{print $2}')"
echo "== shutdown with sub6 running"; P6=$(ppid_of sub6); K6=$(cat $S/procs/sub6/kid.pid 2>/dev/null)
shut >/dev/null; echo "  daemon $(alive $(dpid)); sub6 main $(alive $P6); sub6 kid $(alive $K6)"
echo "== can I (uid 1000, ns owner) kill the leftover subuid kids?"
for k in $K5 $K6; do [ "$(alive $k)" = alive ] && { killmine 9 $k; sleep 0.2; echo "  kid $k after kill: $(alive $k)"; }; done
echo "== leftover files owned by subuid in my subdir:"; find "$D" -uid 100004 -o -uid 100005 2>/dev/null | head; find "$D" \( -uid 100004 -o -uid 100005 \) 2>/dev/null | wc -l
