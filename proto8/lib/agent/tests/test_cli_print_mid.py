"""驗 print_claude 的開關（wake-1114 主案 S）：cli.json 寫 "live_mail": true 又給了 more＝走 cli_stream（argv 多 MID_FLAGS、
回答＝每個 result 用空行接起來）；開關沒開、不是 true、沒給 more＝照舊走 run_claude_stream，argv 跟以前逐字一樣。live_mail_cap 的格式。"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
from agent import cli_cell, cli_cfg, cli_print, cli_stream  # noqa: E402

RESULT = lambda text: json.dumps({"type": "result", "result": text, "session_id": "s"}) + "\n"


class Died(Exception):
    def __init__(self, code, reason):
        super().__init__("%s %s" % (code, reason))
        self.code = code


class PrintMid(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.seen = {}

    def load(self, **cfg):
        (self.d / "cli.json").write_text(json.dumps(dict({"kind": "claude"}, **cfg)))
        with patch.dict(os.environ, self.env, clear=True):
            return cli_cfg.load_cfg(str(self.d))

    def old(self, argv, prompt, ws, timeout_ms, live_path, handed=None, env=None):
        self.seen.update(path="old", argv=argv, prompt=prompt, timeout=timeout_ms)
        return 0, [RESULT("one")]

    def mid(self, argv, prompt, ws, seconds, live_path, handed=None, env=None, more=None, cap=None, preexec_fn=None):
        self.seen.update(path="mid", argv=argv, prompt=prompt, timeout=seconds, more=more, cap=cap)
        return 0, [RESULT("one"), json.dumps({"type": "user", "isReplay": True}) + "\n", RESULT("two")]

    def ask(self, cfg, more):
        cell = cli_cell.Cell(str(self.d / "cell"))
        with patch.object(cli_print, "run_claude_stream", self.old), patch.object(cli_print, "run_claude_stream_mid", self.mid), \
                patch.object(cli_print, "mcp_argv", return_value=[]), patch.object(cli_print, "mark_session"), \
                patch.object(cli_print.uuid, "uuid4", return_value="11111111-1111-1111-1111-111111111111"), \
                patch.object(cli_print.cli_base, "die", side_effect=lambda code, reason: (_ for _ in ()).throw(Died(code, reason))):
            return cli_print.print_claude(cfg, cell, str(self.d), str(self.d), "hi", None, "", more)

    def test_switch_off_or_no_more_is_the_old_path_word_for_word(self):
        self.assertEqual(self.ask(self.load(), None), "one")
        base = self.seen["argv"]
        for cfg, more in ((self.load(), object()), (self.load(live_mail=True), None), (self.load(live_mail="true"), object()),
                          (self.load(live_mail=1), object())):
            self.seen.clear()
            self.assertEqual(self.ask(cfg, more), "one")
            self.assertEqual((self.seen["path"], self.seen["argv"], self.seen["prompt"]), ("old", base, "hi"))
        self.assertNotIn("--input-format", base)
        self.assertNotIn("--replay-user-messages", base)

    def test_switch_on_with_more_goes_mid_and_joins_results(self):
        more = object()
        self.assertEqual(self.ask(self.load(live_mail=True, timeout_ms=120000), more), "one\n\ntwo")
        self.assertEqual(self.seen["path"], "mid")
        self.assertIs(self.seen["more"], more)
        self.assertEqual(self.seen["timeout"], 120)
        self.assertEqual(self.seen["cap"], cli_stream.CAP)
        argv = self.seen["argv"]
        i = argv.index(cli_stream.MID_FLAGS[0])
        self.assertEqual(argv[i:i + len(cli_stream.MID_FLAGS)], cli_stream.MID_FLAGS)
        self.assertEqual(argv.count("--input-format"), 1)

    def test_live_hint_only_when_switch_on(self):
        self.ask(self.load(live_mail=True), object())
        argv = self.seen["argv"]
        self.assertEqual(argv.count(cli_stream.LIVE_HINT), 1)
        self.assertEqual(argv[argv.index(cli_stream.LIVE_HINT) - 1], "--append-system-prompt")
        self.assertEqual(argv.count("--system-prompt-snapshot"), 1)              # 沒宣告 system 也補上 off（不然 --resume 送不到）
        self.assertEqual(argv[argv.index("--system-prompt-snapshot") + 1], "off")
        for cfg, more in ((self.load(), object()), (self.load(live_mail=True), None)):
            self.ask(cfg, more)
            self.assertNotIn(cli_stream.LIVE_HINT, self.seen["argv"])
            self.assertNotIn("--append-system-prompt", self.seen["argv"])

    def test_live_hint_keeps_one_snapshot_flag_with_a_declared_system(self):
        (self.d / "interfaces.json").write_text(json.dumps({"aos-agent": {"system": "system.txt"}}))
        (self.d / "system.txt").write_text("own words\n")
        self.ask(self.load(live_mail=True), object())
        argv = self.seen["argv"]
        self.assertEqual(argv.count("--system-prompt-snapshot"), 1)
        self.assertIn("--append-system-prompt-file", argv)
        self.assertIn(cli_stream.LIVE_HINT, argv)

    def test_cap_merges_and_bad_cap_is_cfgbad(self):
        self.ask(self.load(live_mail=True, live_mail_cap={"letters": 2}), object())
        self.assertEqual(self.seen["cap"], dict(cli_stream.CAP, letters=2))
        for bad in ([5], {"letters": -1}, {"letters": True}, {"mails": 3}, {"seconds": "300"}):
            with self.assertRaises(Died) as cm:
                self.ask(self.load(live_mail=True, live_mail_cap=bad), object())
            self.assertEqual(cm.exception.code, "CfgBad")
        self.ask(self.load(live_mail_cap=[5]), object())                     # 開關沒開：不看 cap
        self.assertEqual(self.seen["path"], "old")

    def test_error_result_still_dies_on_the_mid_path(self):
        def mid(*a, **k):
            return 1, [json.dumps({"type": "result", "is_error": True, "result": "usage limit reached", "session_id": "s"}) + "\n"]
        cell = cli_cell.Cell(str(self.d / "cell"))
        with patch.object(cli_print, "run_claude_stream_mid", mid), patch.object(cli_print, "mcp_argv", return_value=[]), \
                patch.object(cli_print, "mark_session"), patch.object(cli_print, "transcripts", return_value=True), \
                patch.object(cli_print.cli_base, "die", side_effect=lambda code, reason: (_ for _ in ()).throw(Died(code, reason))):
            with self.assertRaises(Died) as cm:
                cli_print.print_claude(self.load(live_mail=True), cell, str(self.d), str(self.d), "hi", None, "s", object())
        self.assertEqual(cm.exception.code, "CliFailed")
        self.assertIn("usage limit", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
