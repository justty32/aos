"""固定回歸矩陣（五）：一定要真 daemon 的項（A2-04、A2-06、A2-07 daemon 部分、A2-11、A2-13）。只留必要的幾個。

**AOS7_TEST_* 環境變數只給測試用**（這個檔沒用到；daemon 照正常環境跑）。

矩陣維度與判定：

1. **A2-04 已登記 node 被換成符號連結** × 換法 ∈ {`same_inode`：mv a moved; ln -s moved a、`outside`：ln -s <root 外> a、
   `parent`：登記 p/a，mv p p2; ln -s <root 外（裡面有 a/）> p} → 2 秒內 phase `missing`；same_inode 時任務被收、
   moved 的回合不再前進；outside／parent 時 root 外沒被建 `.aos`。另外 register 本身是符號連結、或路徑經過符號連結的 node → 回條 ok:false。
2. **A2-06 rounds 按 owner**：A、B 都 pause；A `resume --rounds 1`（B 還擋著）；B `resume --rounds 3` → 跑一回合後 A 自動再 pause，
   `steps_left`＝`{"B": 2}`；A 再 resume 後 B 照扣，再跑兩回合 B 自動 pause。
3. **A2-13**：`pause --owner A` 與 `--owner B` 寫出不同檔名；daemon 起來後 paused.json 兩個 owner 都在。
4. **A2-07**：`.aosd/` 與 `.aosd/ctl/` 的死 pid 暫存在 daemon 跑起來幾秒內清掉。
5. **A2-11**（early_tock、interval 1500ms、任務 sleep 0.4）：回合中送 wake → 下一個 tick 不早於這回合 tick 後約 1.3 秒；
   idle 時送 wake 照樣馬上開（< 0.5 秒）。
"""
import datetime
import os
import shutil
import tempfile
import time
import unittest

from base import SLEEP, DaemonCase
from _matrix import alive, dead_pid
from aos7_fs import read_json


def ts(s):
    return datetime.datetime.fromisoformat(s)


class TestDaemonMatrix(DaemonCase):
    def outside(self):
        d = tempfile.mkdtemp(prefix="aos72-matrix-out-")
        self.addCleanup(shutil.rmtree, d, True)   # 比 daemon 早登記：daemon 收掉之後才刪
        return d

    def wait_phase(self, phase, nid="a", timeout=2.0):
        self.wait_for(lambda: self.nstat(nid).get("phase") == phase, timeout,
                      "%s 沒在 %.1f 秒內變成 %s（現在 %r）" % (nid, timeout, phase, self.nstat(nid)))

    # ---------- A2-04 ----------

    def test_symlink_same_inode(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}], interval_ms=150)
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        self.wait_round(2)
        moved = os.path.join(self.root, "moved")
        os.rename(node, moved)
        os.symlink("moved", node)
        self.wait_phase("missing")
        self.wait_for(lambda: not alive(pid), 3, "換成符號連結後任務沒收")
        r1 = (read_json(os.path.join(moved, ".aos", "round.json"), {}) or {}).get("round")
        time.sleep(0.6)
        r2 = (read_json(os.path.join(moved, ".aos", "round.json"), {}) or {}).get("round")
        self.assertEqual(r1, r2, "符號連結後面的資料夾還在跑回合")

    def test_symlink_outside_root(self):
        node = self.mknode("a", interval_ms=150)
        out = self.outside()
        self.start_daemon(register=["a"])
        self.wait_round(2)
        os.rename(node, os.path.join(self.root, "moved"))
        os.symlink(out, node)
        self.wait_phase("missing")
        time.sleep(0.5)
        self.assertFalse(os.path.exists(os.path.join(out, ".aos")), "寫出 root 外")

    def test_symlink_parent_outside_root(self):
        self.mknode("p/a", interval_ms=150)
        out = self.outside()
        os.makedirs(os.path.join(out, "a"))
        self.start_daemon(register=["p/a"])
        self.wait_round(2, "p/a")
        os.rename(os.path.join(self.root, "p"), os.path.join(self.root, "p2"))
        os.symlink(out, os.path.join(self.root, "p"))
        self.wait_phase("missing", "p/a")
        time.sleep(0.5)
        self.assertFalse(os.path.exists(os.path.join(out, "a", ".aos")), "寫出 root 外")

    def test_register_symlink_refused(self):
        os.makedirs(os.path.join(self.root, "real", "a"))
        os.symlink("real", os.path.join(self.root, "ln"))           # 本身是符號連結（指向 root 內）
        os.symlink("real", os.path.join(self.root, "via"))          # 路徑經過符號連結：via/a
        self.start_daemon()
        for nid in ("ln", "via/a"):
            r = self.wait_receipt(self.ctl("register", nid))
            self.assertIs(r["result"]["ok"], False, "登記符號連結的 node %s 被接受：%r" % (nid, r["result"]))
        self.assertNotIn("ln", (read_json(os.path.join(self.root, ".aosd", "nodes.json"), {}) or {}).get("nodes", {}))

    # ---------- A2-06、A2-13 ----------

    def test_rounds_per_owner(self):
        self.mknode("a", interval_ms=120)
        self.start_daemon(register=["a"])
        self.wait_round(1)
        self.wait_receipt(self.ctl("pause", "a", "--owner", "A"))
        self.wait_receipt(self.ctl("pause", "a", "--owner", "B"))
        self.wait_phase("paused", timeout=5)
        n0 = self.node_round()
        self.wait_receipt(self.ctl("resume", "a", "--owner", "A", "--rounds", "1"))
        time.sleep(0.3)
        self.assertEqual(self.node_round(), n0, "B 還在 pause 時跑了回合")
        self.wait_receipt(self.ctl("resume", "a", "--owner", "B", "--rounds", "3"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused" and "A" in self.nstat().get("paused_by", []), 5,
                      "A 的 rounds 1 跑完沒自動再 pause：%r" % self.nstat())
        st = self.nstat()
        self.assertEqual(st["round"], n0 + 1, st)
        self.assertEqual(st.get("steps_left"), {"B": 2}, st)
        self.wait_receipt(self.ctl("resume", "a", "--owner", "A"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused" and self.nstat().get("paused_by") == ["B"], 5,
                      "B 的倒數沒照扣：%r" % self.nstat())
        st = self.nstat()
        self.assertEqual(st["round"], n0 + 3, st)
        self.assertFalse(st.get("steps_left"), st)

    def test_owner_pause_files_distinct(self):
        self.mknode("a", interval_ms=120)
        a = self.ctl("pause", "a", "--owner", "A")
        b = self.ctl("pause", "a", "--owner", "B")
        self.assertNotEqual(a, b, "不同 owner 的 pause 寫成同一個檔，前一個被蓋掉")
        self.start_daemon(register=["a"])
        self.wait_receipt(a)
        self.wait_receipt(b)
        owners = ((read_json(os.path.join(self.root, ".aosd", "paused.json"), {}) or {}).get("paused") or {}).get("a")
        self.assertEqual(sorted(owners or []), ["A", "B"])

    # ---------- A2-07 ----------

    def test_daemon_sweeps_dead_tmp(self):
        dead = dead_pid()
        ctl = os.path.join(self.root, ".aosd", "ctl")
        os.makedirs(ctl)
        files = [os.path.join(self.root, ".aosd", ".status.json.tmp.%d" % dead),
                 os.path.join(ctl, ".foo.json.tmp.%d" % dead)]
        for p in files:
            with open(p, "w") as f:
                f.write("{")
        self.start_daemon()
        self.wait_for(lambda: not any(os.path.exists(p) for p in files), 5,
                      "daemon 沒清死 pid 的暫存：%r" % [p for p in files if os.path.exists(p)])

    # ---------- A2-11 ----------

    def test_wake_not_kept_from_running_to_idle(self):
        node = self.mknode("a", [{"name": "s", "argv": ["sleep", "0.4"]}], interval_ms=1500, early=True)
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.nstat().get("phase") == "running", 5)
        r = self.node_round()
        rc = self.wait_receipt(self.ctl("wake", "a"))
        self.wait_for(lambda: self.last_round(node).get("round") == r, 5)
        lr = self.last_round(node)
        self.assertLess(rc["result"]["at"], lr["tock_at"], "測試時序不成立：wake 在回合結束後才處理")
        self.wait_for(lambda: self.round_json(node).get("round") == r + 1, 5)
        gap = (ts(self.round_json(node)["tick_at"]) - ts(lr["tick_at"])).total_seconds()
        self.assertGreaterEqual(gap, 1.3, "回合中的 wake 被留到 idle，下一回合提早開（間隔 %.3f 秒）" % gap)
        # idle 時送 wake：馬上開
        self.wait_for(lambda: self.nstat().get("phase") == "idle" and self.round_json(node).get("open") is False, 5)
        t0 = datetime.datetime.now()
        self.ctl("wake", "a")
        self.wait_for(lambda: self.round_json(node).get("round") == r + 2, 3)
        lag = (ts(self.round_json(node)["tick_at"]) - t0).total_seconds()
        self.assertLess(lag, 0.5, "idle 時 wake 沒有馬上開（%.3f 秒）" % lag)


if __name__ == "__main__":
    unittest.main()
