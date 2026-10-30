"""test_eca - 外部 coding agent 範本 demo/eca-claude、demo/eca-codex（eca B 結論 1、實作第 5 步）：
aos-say → aos-exec 跑範本（aos-loop 包 lib/eca/turn）→ aos-listen 拿回答；射後不理（ECA_ON_EMPTY=stop）跑完就結束，
停著等（範本本身，idle）背景跑、ctl.json paused 時信留 new/、aos-listen --status 看得到 paused。

用 test_fay 的假 claude／codex，不花額度。設計：proto8/thinking/2026-10-30-eca.md。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, FAKE_CODEX, SYS_PATH  # noqa: E402
HUMAN = ROOT / "extras" / "human" / "bin"
TEMPLATES = {k: ROOT / "demo" / ("eca-" + k) for k in ("claude", "codex")}
TURN = ROOT / "lib" / "eca" / "turn"
CLEAR = ("AOS_HUB", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "TMUX", "ECA_ON_EMPTY",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")


class Eca(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, src in (("claude", FAKE_CLAUDE), ("codex", FAKE_CODEX)):
            (self.bin / name).write_text(src)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"

    def env(self):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log), FAKE_TRANSCRIPTS="1",
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"), CODEX_HOME=str(self.tmp / "codex-home"))
        return e

    def run_(self, argv, timeout=60):
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=self.env(),
                              stdin=subprocess.DEVNULL, timeout=timeout)

    def say(self, text):
        r = self.run_([HUMAN / "aos-say", "--ws", self.ws, text])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, *args):
        return self.run_([HUMAN / "aos-listen", "--ws", self.ws] + list(args))

    def fire_and_forget(self, kind):
        """範本複製一份改成射後不理：parts.json 的 turn 指絕對路徑、ECA_ON_EMPTY=stop（複本搬了家，相對路徑會斷）。"""
        d = self.tmp / ("eca-%s-once" % kind)
        shutil.copytree(TEMPLATES[kind], d)
        (d / "parts.json").write_text(json.dumps({"parts": {"turn": {"path": str(TURN), "env": {"ECA_ON_EMPTY": "stop"}}}}))
        return d

    def sid(self, kind):
        return (self.stack / kind / "session.txt").read_text().strip()

    def wait_phase(self, phase, secs=20):
        end = time.time() + secs
        while time.time() < end:
            try:
                if json.loads((self.stack / "state.json").read_text() or "{}").get("phase") == phase:
                    return True
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        return False

    def test_templates_shape(self):
        """兩份範本：_entry 是 aos-loop loop.json 的一行 argv（JSON、不給 +x）、loop.json 停著等版、parts.json 一格 turn（idle）、cli.json 的 kind。"""
        for kind, d in TEMPLATES.items():
            self.assertEqual(json.loads((d / "_entry").read_text()), ["aos-loop", "loop.json"])
            self.assertFalse(os.stat(d / "_entry").st_mode & 0o111, "%s/_entry 不該有 +x" % d.name)
            loop = json.loads((d / "loop.json").read_text())
            self.assertEqual((loop["interval_ms"], loop["ctl"], loop["state"], "max" in loop), (300, "ctl.json", "state.json", False))
            parts = json.loads((d / "parts.json").read_text())["parts"]
            self.assertEqual(list(parts), ["turn"])
            self.assertEqual(parts["turn"]["env"], {"ECA_ON_EMPTY": "idle"})
            self.assertEqual((d / parts["turn"]["path"]).resolve(), TURN.resolve())
            self.assertEqual(json.loads((d / "cli.json").read_text())["kind"], kind)

    def test_fire_and_forget(self):
        """射後不理：say 一句 → aos-exec 跑到 queue 空就收工（turn 退 10、aos-loop 以 0 結束）→ listen 拿到回答。"""
        for kind in ("claude", "codex"):
            sig = self.say("%s 你好" % kind)
            r = self.run_([EXEC, "--ws", self.ws, self.fire_and_forget(kind)])
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.listen("--timeout", "10", sig)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "fake %s[%s]: %s 你好\n" % (kind, self.sid(kind)[:8], kind))
            state = json.loads((self.stack / "state.json").read_text())
            self.assertEqual(state["phase"], "done")
            self.assertTrue((self.stack / kind / "transcripts" / ("%s-%s.jsonl" % (kind, self.sid(kind)))).is_symlink())
            for f in ("state.json", "ctl.json", "eca.json"):                     # 下一隻從乾淨的 stack 開始
                if (self.stack / f).exists():
                    (self.stack / f).unlink()
        self.assertEqual(sorted(os.listdir(self.ws)), [".stack"])              # 工作區本身不長東西

    def test_idle_template_pause(self):
        """範本本身（停著等）背景跑：say 兩句答兩句（同一段對話）；ctl.json paused 後第三句留在 new/、--status 印 paused；
        恢復後答第三句；stopped 收工、退 0。"""
        p = subprocess.Popen([EXEC, "--ws", str(self.ws), str(TEMPLATES["claude"])], stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, env=self.env())
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        answers = []
        for text in ("第一句", "第二句"):
            r = self.listen("--timeout", "20", self.say(text))
            self.assertEqual(r.returncode, 0, r.stderr)
            answers.append(r.stdout)
        sid = self.sid("claude")
        self.assertEqual(answers, ["fake claude[%s]: 第一句\n" % sid[:8], "fake claude[%s]: 第二句\n" % sid[:8]])
        (self.stack / "ctl.json").write_text('{"paused": true}')
        self.assertTrue(self.wait_phase("paused"))
        sig = self.say("第三句")
        time.sleep(1)
        self.assertEqual(sorted(os.listdir(self.stack / "queue" / "new")), [sig])
        r = self.listen("--status")
        self.assertIn("phase paused", r.stdout, r.stdout + r.stderr)
        (self.stack / "ctl.json").write_text('{"paused": false}')
        r = self.listen("--timeout", "20", sig)
        self.assertEqual(r.stdout, "fake claude[%s]: 第三句\n" % sid[:8], r.stderr)
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=20), 0)
        self.assertEqual([m["role"] for m in
                          (json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines())],
                         ["user", "assistant"] * 3)


if __name__ == "__main__":
    unittest.main()
