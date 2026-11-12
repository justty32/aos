"""Test chat's line input in a real pty: Chinese + Backspace, arrow keys, long lines, pastes and EOF are read whole (11-12 chat-utf8)."""
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import termios
import time
import unittest


sys.dont_write_bytecode = True
MOD = Path(__file__).resolve().parents[1] / "aos_agent" / "read_line.py"
IUTF8 = getattr(termios, "IUTF8", 0o40000)
# 子行程：直接載 read_line.py（不經套件 __init__），一行一行讀，每行印一行 RESULT 到 stderr（終端機）。
CHILD = r'''
import importlib.util, sys, termios
spec = importlib.util.spec_from_file_location("read_line", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
a = termios.tcgetattr(0); a[0] &= ~m.IUTF8; termios.tcsetattr(0, termios.TCSANOW, a)   # 照 WSL 預設：-iutf8
while True:
    try:
        line = m.read_line()
    except UnicodeError:
        sys.stderr.write("RESULT BAD\n"); sys.stderr.flush(); continue
    sys.stderr.write("RESULT %s\n" % ascii(line)); sys.stderr.flush()
    if not line:
        break
'''


def run(keys, stdout_tty=True):
    """在 pty 裡跑 CHILD、照順序打 keys（每段之間停一下），回 (各行 RESULT, 結束後 pty 的 iflag)。"""
    pid, fd = pty.fork()
    if pid == 0:
        try:
            if not stdout_tty:
                null = os.open(os.devnull, os.O_WRONLY)
                os.dup2(null, 1)
            os.execv(sys.executable, [sys.executable, "-c", CHILD, str(MOD)])
        finally:
            os._exit(127)
    out = b""

    def pump(t):
        nonlocal out
        end = time.monotonic() + t
        while time.monotonic() < end:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                try:
                    d = os.read(fd, 65536)
                except OSError:
                    return False
                if not d:
                    return False
                out += d
        return True

    pump(0.5)
    for k in keys:
        os.write(fd, k)
        pump(0.15)
    os.write(fd, b"\x04")                         # Ctrl-D：讀到結束
    end = time.monotonic() + 10
    while b"RESULT ''" not in out and time.monotonic() < end and pump(0.2):
        pass
    iflag = termios.tcgetattr(fd)[0]
    os.waitpid(pid, 0)
    os.close(fd)
    text = out.decode("utf-8", "replace").replace("\r", "")
    return [l.split("RESULT ", 1)[1] for l in text.split("\n") if "RESULT " in l], iflag


def lit(s):
    return ascii(s)


class TtyReadLine(unittest.TestCase):
    def test_backspace_erases_whole_chinese_character(self):
        got, _ = run(["你好".encode(), b"\x7f", "嗎\r".encode()])
        self.assertEqual(got, [lit("你嗎\n"), lit("")])

    def test_arrow_keys_move_instead_of_typing_escapes(self):
        got, _ = run(["你好".encode(), b"\x1b[D", "嗎\r".encode()])
        self.assertEqual(got, [lit("你嗎好\n"), lit("")])

    def test_long_line_over_tty_buffer_is_whole(self):
        s = "a" + "中" * 1700                       # 5101 bytes：超過 cooked 模式 4096 上限，且不落在字的邊界
        got, _ = run([s.encode() + b"\r"])
        self.assertEqual(got, [lit(s + "\n"), lit("")])

    def test_bracketed_paste_with_newline_is_one_line(self):
        got, _ = run([b"\x1b[200~" + "第一行\n第二行".encode() + b"\x1b[201~", b"\r"])
        self.assertEqual(got, [lit("第一行\n第二行\n"), lit("")])

    def test_two_lines_then_eof(self):
        got, _ = run(["一\r".encode(), "二\r".encode()])
        self.assertEqual(got, [lit("一\n"), lit("二\n"), lit("")])

    def test_stdout_not_tty_sets_iutf8_and_restores_it(self):
        got, iflag = run(["你好".encode(), b"\x7f", "嗎\r".encode()], stdout_tty=False)
        self.assertEqual(got, [lit("你嗎\n"), lit("")])
        self.assertFalse(iflag & IUTF8)            # 結束時還原成原本的 -iutf8


class PipeReadLine(unittest.TestCase):
    def run_pipe(self, data):
        code = CHILD.replace("a = termios.tcgetattr(0); a[0] &= ~m.IUTF8; termios.tcsetattr(0, termios.TCSANOW, a)", "")
        r = subprocess.run([sys.executable, "-c", code, str(MOD)], input=data, capture_output=True, timeout=30)
        return [l.split("RESULT ", 1)[1] for l in r.stderr.decode().splitlines() if "RESULT " in l], r.stdout

    def test_pipe_reads_by_line_and_bad_line_does_not_spoil_others(self):
        got, out = self.run_pipe("好\n".encode() + b"\xe4\xbd\n" + "再一句\n".encode())
        self.assertEqual(got, [lit("好\n"), "BAD", lit("再一句\n"), lit("")])
        self.assertEqual(out, b"")                 # 提示符在 stderr，stdout 沒東西


if __name__ == "__main__":
    unittest.main()
