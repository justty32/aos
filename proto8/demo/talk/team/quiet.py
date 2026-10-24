# quiet.py - daemon 每次的身體：看名冊上每隻 member（human 的不看）是不是都沒事做了
#   都沒事（信箱的 tmp/、new/、cur/ 都是空的）＝退 10，daemon 收工、收掉子 loop
#   有 member 的子 loop 已經失敗結束（小格 state.json 的 phase 是 done／stopped、code 非 0）＝stderr 一行、退 1（信會卡在那裡沒人收）
#   其他＝退 0，下一次再看
import json, os, sys

roster_path, stack = os.environ.get("AOS_ROSTER"), os.environ.get("AOS_STACK", ".")
try:
    with open(roster_path, encoding="utf-8") as f:
        members = json.load(f)["members"]
except (TypeError, OSError, ValueError, KeyError) as e:
    print("team: RosterBad %s 讀不了：%s" % (roster_path, e), file=sys.stderr)
    sys.exit(1)
base = os.path.dirname(os.path.abspath(roster_path))
busy = []
for name, m in members.items():
    if m.get("human"):
        continue
    try:
        with open(os.path.join(stack, name, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        if st.get("phase") in ("done", "stopped") and st.get("code") not in (0, None):
            print("team: MemberFailed %s 的 loop 以 %s 結束（看 .stack/%s/stderr.txt）" % (name, st.get("code"), name), file=sys.stderr)
            sys.exit(1)
    except (OSError, ValueError):
        pass
    box = os.path.join(base, m.get("mailbox", name))
    for d in ("tmp", "new", "cur"):
        p = os.path.join(box, d)
        if os.path.isdir(p) and any(not n.startswith(".") for n in os.listdir(p)):
            busy.append(name)
            break
sys.exit(0 if busy else 10)
