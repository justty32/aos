#!/usr/bin/env python3
"""玩具寄信工具；同一句覆寫同一個檔案，重跑也安全。"""
import json
from pathlib import Path
import sys


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("hello-send: 要給 run 資料夾與收件人。照 send.py <run_dir> <to> 再試", file=sys.stderr)
        return 2
    run_dir, to = args
    try:
        reply = (Path(run_dir) / "out/reply.txt").read_text(encoding="utf-8")
        if not reply.strip():
            raise ValueError("reply.txt 是空的")
        (Path(run_dir) / "out/sent.txt").write_text("給 %s：%s" % (to, reply), encoding="utf-8")
    except (FileNotFoundError, ValueError) as e:
        reason = "reply.txt 不在" if isinstance(e, FileNotFoundError) else str(e)
        print("hello-send: %s。先寫一句回覆再寄" % reason, file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("hello-send: 不確定：回覆讀寫失敗。確認 out/ 可讀寫後照原樣再試", file=sys.stderr)
        return 3
    print(json.dumps({"sent": to}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
