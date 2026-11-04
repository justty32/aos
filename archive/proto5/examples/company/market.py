#!/usr/bin/env python3
"""市場層的指令（本體 proto5/lib/aos_market.py；規則 proto5/spec/team/market.md）。

要先設 AOS_COST_HOME（財務部帳本，帳戶在裡面）與 AOS_MARKET_HOME（或 --market）。
  python3 market.py open c1 ~/tmp/company-run/c1            # 開戶＋開辦費
  python3 market.py score c1 --eval <eval 結果.json>         # 記這輪的品質（成功張數、董事等的秒數自動算）
  python3 market.py rank                                    # 排名
  python3 market.py grant [--dry-run] [--usd c3=0]           # 照排名撥額度（從總池出）
  python3 market.py bankrupt | close c3                     # 倒閉／經理人裁撤：剩的配額與名額回總池
  python3 market.py pool                                    # 總池：錢、名額
  python3 market.py slots c1 --llm-cpu 1                    # 從總池撥名額
  python3 market.py merge --dry-run                         # 剩兩家時合併（先看計畫）
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'lib'))

import aos_market  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(aos_market.main())
