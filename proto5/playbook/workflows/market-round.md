# 一輪市場：打分 → 排名 → 撥款 → 倒閉 → 合併

← [workflows](README.md)｜規則：[spec/team/market.md](../../spec/team/market.md)｜來源：[notes/2026-09-25-company](../../notes/2026-09-25-company/README.md)

**適合什麼活**：同一種活交給幾支一樣的隊（公司）做，用表現決定資源往哪裡流。經理人（aos 外）拿機械指令做決定，參數可調、可覆寫。

1. 各家做同一批單（每家自己的專案副本）。
2. `market.py score 名 --eval 結果.json`：品質（機械 40％＋證據 40％＋評審 20％）；秒數、跳數從總機單自動算。
3. `market.py rank`：品質 0.6、快 0.25、省 0.15（都是參數）。省＝這一輪花的 token，不是累計。
4. `market.py grant [--dry-run]`：照名次分這一輪的總額；總池不夠就照比例縮。
5. `market.py bankrupt`：花光的停、封存；剩的配額與名額回總池；`close 名` 是經理人主動裁撤（剩多少收多少）。
6. 剩兩家：`market.py merge --dry-run` 看計畫（經理只留一個、名額滿了改臨時工）→ `merge`。

- **在哪停下來看**：先 `--dry-run`；排名第一但品質低於門檻的（快又省但做壞了）要設 `min_quality`。
- **注意**：並行的單照單算 token 會變成整隊的（品管部 09-25），市場用整家一輪的總數就沒這問題。
