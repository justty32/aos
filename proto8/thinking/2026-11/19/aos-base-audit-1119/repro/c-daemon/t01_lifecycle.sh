# t01: add/stop/start/sleep/wake/restart on exec and loop procs; how long sleep/rm/shutdown take on a TERM-ignoring proc.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t01 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/sl.sh" 'exec sleep 600'
mkscript "$D/noterm.sh" 'trap "" TERM
while :; do sleep 1; done'
echo '{"exec": ["sleep", "0.3"], "interval_ms": 100}' > "$D/lp.json"

echo "== add exec sl"; ctl add --name sl "$D/sl.sh"; waitphase sl running; row sl
echo "== stop exec sl (exec type, nobody reads ctl)"; ctl stop sl; sleep 3; echo "  after 3s phase=$(phase sl) pid alive? $(alive $(ppid_of sl))"
echo "== sleep sl while stopping"; t0=$(now); ctl sleep sl; waitphase sl stopped 15; echo "  took $(since $t0)s"; rows
echo "== start sl"; ctl start sl; waitphase sl running; rows
echo "== sleep sl (SIGTERM)"; t0=$(now); ctl sleep sl; waitphase sl sleeping 15; echo "  took $(since $t0)s"; rows
echo "== wake sl"; ctl wake sl; waitphase sl running; rows

echo "== add noterm"; ctl add --name nt "$D/noterm.sh"; waitphase nt running; P=$(ppid_of nt); echo "  pid $P"
echo "== sleep nt (TERM ignored)"; t0=$(now); ctl sleep nt; waitphase nt sleeping 25; echo "  sleeping after $(since $t0)s; old pid $(alive $P)"; rows

echo "== loop proc"; ctl add --name lp "$D/lp.json"; waitphase lp running; sleep 1; rows
echo "== stop loop"; t0=$(now); ctl stop lp; waitphase lp stopped 10; echo "  stopped after $(since $t0)s"
echo "== start loop"; ctl start lp; waitphase lp running; rows
echo "== restart subcommand?"; ctl restart lp 2>&1 | head -2

echo "== wake nt, then shutdown with nt running (TERM ignored)"; ctl wake nt; waitphase nt running; P=$(ppid_of nt)
ctl ls
t0=$(now); shut; echo "  shutdown took $(since $t0)s; daemon $(alive $(dpid)); nt old pid $(alive $P)"; rows
echo "== restart daemon: sleeping rows wake"; startd; sleep 1; rows
t0=$(now); shut; echo "  shutdown took $(since $t0)s"
echo "== daemon log tail"; tail -n 30 "$D/daemon.log"; echo "== daemon err"; cat "$D/daemon.err"
