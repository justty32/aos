"""真 daemon 長跑：一個 node 掛取樣器、發布者、讀者三個 keep 任務，跑到 N 回合，
全程盯 events/ 檔數、舊段有沒有被刪、daemon 與任務的記憶體／開檔數，最後印並存 summary.json。

用法：python3 longrun.py --root <空資料夾> [--rounds 300] [--interval-ms 100] [--segment-bytes 8192]
退出碼：0 全部判準通過、1 有判準沒過、2 用法或環境錯。
"""
import argparse
import json
import re
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.dirname(os.path.dirname(HERE))
P = os.path.dirname(os.path.dirname(EV))
sys.path[:0] = [EV, os.path.join(P, "lib")]
import aos7_events_read as reader  # noqa: E402
import aos7_events_store as store  # noqa: E402
from aos7_fs import proc_starttime, read_json  # noqa: E402

NODE = "n1"
MAX_FILES = 12
SEG = re.compile(r"(obs|must)\.[0-9]{12}\.jsonl")


def ctl(*args):
    subprocess.run([sys.executable, os.path.join(P, "bin", "aos7-ctl"), *args], check=True, stdout=subprocess.DEVNULL)


def procs_of(root):
    """環境 AOS7_ROOT 指到本 root 的程序（任務經 runner 脫離 daemon 的子樹，只能這樣認）。"""
    out = []
    want = b"AOS7_ROOT=" + root.encode()
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/environ" % d, "rb") as f:
                    if want in f.read().split(b"\0"):
                        out.append(int(d))
            except OSError:
                pass
    return out


def proc_info(pid):
    """回 (cmdline, rss_kb, fds)；程序沒了回 None。"""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            cmd = f.read().split(b"\0")
        rss = 0
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
        return [c.decode(errors="replace") for c in cmd], rss, len(os.listdir("/proc/%d/fd" % pid))
    except OSError:
        return None


def snapshot(daemon_pid, root):
    """daemon 與三個任務的 rss／fds；任務以 argv[1] 的檔名認（runner 包裝程式不算）。"""
    out = {}
    for pid in [daemon_pid] + procs_of(root):
        info = proc_info(pid)
        if info is None:
            continue
        cmd, rss, fds = info
        name = os.path.basename(cmd[1]) if len(cmd) > 1 else ""
        key = {"aos7-daemon": "daemon", "aos7-events": "events", "pub_task.py": "pub_task",
               "reader_task.py": "reader_task"}.get(name)
        if key:   # 同角色多個程序（雙開）會留成清單，判準要求每角色恰一個
            out.setdefault(key, []).append({"pid": pid, "start": proc_starttime(pid), "rss_kb": rss, "fds": fds})
    return out


def count_tree(path):
    return sum(len(fs) + len(ds) for _, ds, fs in os.walk(path))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--rounds", type=int, default=300)
    ap.add_argument("--interval-ms", type=int, default=100)
    ap.add_argument("--segment-bytes", type=int, default=8192)
    ap.add_argument("--keep", type=int, default=4)
    ap.add_argument("--pad", type=int, default=200)
    ap.add_argument("--no-reader", action="store_true", help="不裝讀者：must 沒人 ack，應滿載拒收、檔數仍不超")
    ap.add_argument("--timeout", type=float, default=600, help="牆鐘上限秒數")
    a = ap.parse_args(argv)
    if a.rounds < 1 or a.interval_ms < 0 or a.segment_bytes < 1 or a.pad < 0 or not 1 <= a.keep <= store.MAX_KEEP:
        ap.error("rounds、segment-bytes 須為正，interval-ms、pad 非負，keep 在 1～%d" % store.MAX_KEEP)
    root = os.path.abspath(a.root)
    if os.path.exists(root) and os.listdir(root):
        ap.error("--root 須是空資料夾或不存在")
    os.makedirs(root, exist_ok=True)
    node = os.path.join(root, NODE)
    events = os.path.join(node, "events")

    # 1. 開 node：登記、回合間隔、daemon 流水帳出口
    ctl("daemon", root, "register", NODE)
    os.makedirs(os.path.join(node, ".aos"), exist_ok=True)
    with open(os.path.join(node, ".aos", "timeline.json"), "w") as f:
        json.dump({"interval_ms": a.interval_ms}, f)
    open(os.path.join(root, ".aosd", "log.on"), "w").close()
    # 2. 先建 state 定設定（小段才看得到輪替；之後以 state 為準）
    config = {"keep_segments": a.keep, "segment_bytes": a.segment_bytes}
    if store.recover(events, node=NODE, config=config) is None:
        print("events state 建不起來", file=sys.stderr)
        return 2
    py = sys.executable
    tasks = [
        json.dumps({"name": "events", "mode": "keep",
                    "argv": [py, os.path.join(EV, "aos7-events"), "--status", "--daemon-log",
                             "--keep", str(a.keep), "--segment-bytes", str(a.segment_bytes)]}),
        json.dumps({"name": "pub", "mode": "keep", "argv": [py, os.path.join(HERE, "pub_task.py"), "--pad", str(a.pad)]}),
        json.dumps({"name": "reader", "mode": "keep", "argv": [py, os.path.join(HERE, "reader_task.py")]})]
    ctl("add", node, *(tasks[:2] if a.no_reader else tasks))

    # 3. 起真 daemon，盯到 N 回合
    log = open(os.path.join(root, "daemon.out"), "w")
    daemon = subprocess.Popen([py, os.path.join(P, "bin", "aos7-daemon"), root], stdout=log, stderr=subprocess.STDOUT)
    t0, rnd, max_files, max_names, seen, samples = time.time(), 0, 0, [], set(), []
    max_with_tmp, extra_names = 0, set()
    next_sample = 1
    pids = {}

    def take_sample(r, real):
        snap = snapshot(daemon.pid, root)
        for k, v in snap.items():
            pids.setdefault(k, set()).update((e["pid"], e["start"]) for e in v)
        samples.append({"round": r, "t": round(time.time() - t0, 1), "files": len(real),
                        "segments": sorted(n for n in real if SEG.fullmatch(n)),
                        "root_entries": count_tree(root), "procs": snap})

    try:
        while rnd < a.rounds:
            if daemon.poll() is not None:
                print("daemon 提早退出 rc=%s" % daemon.returncode, file=sys.stderr)
                break
            if time.time() - t0 > a.timeout:
                print("逾時", file=sys.stderr)
                break
            lr = read_json(os.path.join(node, ".aos", "last-round.json"))
            rnd = lr.get("round", rnd) if isinstance(lr, dict) else rnd
            try:
                names = os.listdir(events)
            except OSError:
                names = []
            real = [n for n in names if not n.startswith(".state.json.tmp.")]
            max_with_tmp = max(max_with_tmp, len(names))
            if len(real) > max_files:
                max_files, max_names = len(real), sorted(real)
            seen.update(n for n in real if SEG.fullmatch(n))
            extra_names.update(n for n in real if n not in ("obs.active.jsonl", "must.active.jsonl", "state.json",
                                                             "state.json.lock") and not SEG.fullmatch(n))
            if rnd >= next_sample or rnd >= a.rounds:
                take_sample(rnd, real)
                next_sample = rnd + 25 if rnd >= 1 else 1
            time.sleep(0.02)
    finally:
        # 4. 收：照正規途徑停 daemon（連任務一起殺），等它退
        ctl("daemon", root, "stop", "--kill")
        try:
            daemon.wait(30)
        except subprocess.TimeoutExpired:
            daemon.send_signal(signal.SIGTERM)
            daemon.wait(10)
        log.close()
    leftover = procs_of(root)

    # 5. 事後核對
    st = store.load_state(events) or {}
    ch = st.get("channels", {})
    final_names = sorted(os.listdir(events))
    still = {n for n in final_names if SEG.fullmatch(n)}
    deleted = sorted(seen - still)
    deleted_obs = [n for n in deleted if n.startswith("obs.")]
    deleted_must = [n for n in deleted if n.startswith("must.")]
    final_real = [n for n in final_names if not n.startswith(".state.json.tmp.")]
    final_ok = len(final_real) <= MAX_FILES and all(
        n in ("obs.active.jsonl", "must.active.jsonl", "state.json", "state.json.lock") or SEG.fullmatch(n) for n in final_real) \
        and all(sum(n.startswith(c + ".") and bool(SEG.fullmatch(n)) for n in final_real) <= a.keep for c in ("obs", "must"))
    obs_all, cur, obs_err, obs_gaps = 0, None, [], []
    while True:
        res = reader.read(events, "obs", cur, limit=1000)
        obs_all += len(res["records"])
        obs_err += res["errors"]
        obs_gaps += [g for g in res["gaps"] if g.get("kind") == "retention"]
        if res["next_cursor"] == cur or not res["records"]:
            break
        cur = res["next_cursor"]
    pub = read_json(os.path.join(node, "longrun", "pub.json"), {}) or {}
    rd = read_json(os.path.join(node, "longrun", "reader.json"), {}) or {}
    def must_from(cursor, last_i):
        """從 cursor 讀 must 到底，逐筆要求 i 連號；回 (連號件數, 是否乾淨)。"""
        n, clean = 0, True
        while True:
            res = reader.read(events, "must", cursor, limit=1000)
            if res["errors"] or res["gaps"]:
                clean = False
            for rec in res["records"]:
                payload = rec.get("payload")
                if not isinstance(payload, dict) or payload.get("i") != last_i + n + 1:
                    return n, False
                n += 1
            if not res["records"] or res["next_cursor"] == cursor:
                return n, clean
            cursor = res["next_cursor"]

    # 讀者任務停下時可能還差最後一兩件（同一回合發布在讀之後）：從它存的游標補讀，核對連號到發布者為止
    tail, tail_clean = must_from(rd.get("cursor", 1), rd.get("last_i", 0))
    # 不裝讀者：已接受的 must 全部還在、1 起連號
    kept, kept_clean = must_from(1, 0) if a.no_reader else (None, None)
    first = next((s for s in samples if s["round"] >= 50), samples[0] if samples else None)
    roles = ("daemon", "events", "pub_task") + (() if a.no_reader else ("reader_task",))
    last = samples[-1] if samples else None

    def growth(key, field):
        try:
            return [first["procs"][key][0][field], last["procs"][key][0][field]]
        except (KeyError, TypeError):
            return None

    summary = {
        "rounds": rnd, "wall_s": round(time.time() - t0, 1), "daemon_rc": daemon.returncode,
        "config": config, "max_files": max_files, "max_files_names": max_names,
        "max_files_incl_tmp": max_with_tmp, "unexpected_names": sorted(extra_names),
        "segments_seen": len(seen), "segments_deleted": {"obs": len(deleted_obs), "must": len(deleted_must)},
        "deleted_examples": deleted[:6],
        "final_files": final_names,
        "obs": {k: ch.get("obs", {}).get(k) for k in ("next_seq", "dropped_upto", "torn")},
        "must": {k: ch.get("must", {}).get(k) for k in ("next_seq", "dropped_upto", "acked_upto", "refused", "torn")},
        "obs_readable_now": obs_all, "obs_read_errors": obs_err, "obs_retention_gaps": obs_gaps,
        "publisher": pub, "reader": rd, "reader_tail_after_stop": tail, "must_kept_in_order": kept,
        "sample_rounds": [first["round"], last["round"]] if first and last else None,
        "rss_kb_r50_to_end": {k: growth(k, "rss_kb") for k in ("daemon", "events", "pub_task", "reader_task")},
        "fds_r50_to_end": {k: growth(k, "fds") for k in ("daemon", "events", "pub_task", "reader_task")},
        "task_pids": {k: sorted(p for p, _ in v) for k, v in pids.items()},
        "root_entries_r50_to_end": [first["root_entries"], last["root_entries"]] if first and last else None,
        "leftover_procs": leftover, "samples": samples,
    }
    rss, fds = summary["rss_kb_r50_to_end"], summary["fds_r50_to_end"]
    checks = {
        "rounds_reached": rnd >= a.rounds,
        "files_le_12": 0 < max_files <= MAX_FILES,
        "only_expected_names": not extra_names,
        "final_listing_ok": final_ok,
        "obs_old_segments_deleted": (summary["obs"]["dropped_upto"] or 0) > 0 and bool(deleted_obs),
        "obs_readable_no_errors": not obs_err,
        "one_process_per_role_each_sample": bool(samples) and all(
            sorted(s["procs"]) == sorted(roles) and all(len(v) == 1 for v in s["procs"].values()) for s in samples[1:]),
        "no_task_restarts": all(len(pids.get(k, ())) == 1 for k in roles),
        "publisher_alive_to_end": (pub.get("round") or 0) >= rnd - 3,
        "rss_growth_lt_2mb": all(rss[k] and rss[k][1] - rss[k][0] < 2048 for k in roles),
        "fds_steady": all(fds[k] and fds[k][1] <= fds[k][0] + 2 for k in roles),
        "daemon_clean_exit": daemon.returncode == 0 and not leftover,
    }
    if a.no_reader:   # 必讀通道沒人確認：停收新責任（refused、發布者不推進），不刪未確認段
        checks["must_unacked_segments_kept"] = summary["must"]["dropped_upto"] == 0 and not deleted_must
        checks["must_all_accepted_still_readable"] = kept_clean and kept == pub.get("done_upto")
        checks["must_refused_when_full"] = (summary["must"]["refused"] or 0) > 0 and pub.get("refused", 0) > 0
        checks["publisher_stopped_at_capacity"] = 0 < (pub.get("done_upto") or 0) < rnd
    else:
        checks["must_acked_segments_deleted"] = (summary["must"]["dropped_upto"] or 0) > 0 and bool(deleted_must)
        checks["must_never_refused"] = summary["must"]["refused"] == 0
        checks["reader_in_order_no_errors"] = all(rd.get(k) == 0 for k in ("errors", "out_of_order", "gaps", "dups"))
        checks["reader_caught_up"] = tail_clean and rd.get("last_i", 0) + tail == pub.get("done_upto") \
            and (pub.get("done_upto") or 0) >= 0.9 * a.rounds
    summary["checks"] = checks
    with open(os.path.join(os.path.dirname(root), os.path.basename(root) + "-summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    brief = {k: v for k, v in summary.items() if k != "samples"}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
