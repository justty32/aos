"""test_fake_slow - the demo endpoint function fake_slow (templates/kernels/llm-kernel) finds lib/tools/base/llm_fake and passes its answer back."""
# 11-19 線 fakedemo-fix-1119：11-18 目錄搬家後 fake_slow 把 llm_fake 算成 lib/aos/base/llm_fake（不存在），fake-demo-slow／fast 起不來。
# 這支用 delay_s 0 直接跑一次 fake_slow（經 AOS_HOME 找裝好的 lib，要先跑過 install.py），不起任何 daemon。
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

PROTO = Path(__file__).resolve().parents[2]
ENTRY = PROTO / "templates" / "kernels" / "llm-kernel" / "fake_slow" / "_entry"


class FakeSlowTest(unittest.TestCase):
    def test_answers_through_llm_fake(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env["AOS_HOME"] = str(PROTO)
        stdin = json.dumps({"endpoint": {"delay_s": 0}, "request": {"messages": [{"role": "user", "content": "hi"}]}})
        run = subprocess.run([sys.executable, str(ENTRY)], input=stdin, capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("FAKE ANSWER to: hi", json.loads(run.stdout)["message"]["content"])


if __name__ == "__main__":
    unittest.main()
