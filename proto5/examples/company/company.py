#!/usr/bin/env python3
"""公司樣板的指令（本體在 proto5/lib/aos_company.py；格式見 proto5/spec/team/company.md）。

  python3 company.py new ~/tmp/company-run/c1 --prefix c1- --project ~/tmp/company-run/c1/proj
  python3 company.py up     -C ~/tmp/company-run/c1       # 起 kernel、各部門團隊、總機
  python3 company.py order  -C ~/tmp/company-run/c1 "補人物 老財"
  python3 company.py status -C ~/tmp/company-run/c1       # 正式 N/10、cpu N/20、llm cpu N/5＋各部門任務板
  python3 company.py mail   -C ~/tmp/company-run/c1       # 董事收件匣（各部門寄給 human、不是總機單回覆的）
  python3 company.py down   -C ~/tmp/company-run/c1
設了 AOS_COMPANY_HOME 就可以不寫 -C。
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'lib'))

import aos_company  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(aos_company.main(default_src=HERE))
