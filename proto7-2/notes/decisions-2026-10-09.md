# 2026-10-09 頂層代定清單（使用者出門時）

← [plan-2026-10-09](plan-2026-10-09.md)｜[catch-up](catch-up.md)

使用者 10-09 早上說：出門後大小決策全由頂層先做，回來問「這段時間發生了啥、你做了哪些大決定」時照本檔報告；做錯可以改回來。一行一條：級別（A＝大、B＝中、C＝小）／決定／出處或翻案位置。

## 使用者親裁（10:40）

- loop7 D1～D10 全照預設建議；D7 改「不設行數上限」（開發階段不設，整理階段再濃縮）→ [blueprint-loop7 §5](blueprint-loop7.md)
- T8 系列在家機可重試（加保護），公司 WSL 不跑。

## 頂層代定

- B｜九隊各自 worktree（`loop7/<隊>` 分支），隊長 rebase 後頂層 ff-merge＋push → plan §4
- B｜所有測試跑在 `systemd-run --user --scope -p TasksMax=800 -p RuntimeMaxSec=1200`；同時最多 3 份全套 → plan §5
- B｜`test_budget.py` 改成只印不擋（D7 的落法）→ plan §5
- C｜subd 尾項併入 M 隊、T8-02／T8-04 歸 S／B 隊收尾 → plan §3
- C｜D3 注入點歸 K4 先獨立 commit，K2／T2 等它 → plan §3
- B｜codex 新模型（gpt-6.1-sol 等）級別一律「暫定、待使用者確認」；skyrim 側 team-model 不同步 → X 隊
- C｜R 隊回歸發現只記不修（≤5 行單檔例外）→ plan §3
- B｜寫碼主力改 codex `gpt-6.1-sol`、審查 `gpt-6-astra`（取代 09-30「碰程式碼一律 Opus」）；隊長仍是 Opus 逐行審 → plan §3
- B｜隊伍遇到方向性題不停線、不記 WAIT_USER，回報頂層由頂層代定並記於本檔（照使用者 10-09 指示）

## 執行中新增
- C｜K3：R8-05 選 (b) 旗標改記待結算回合號 `owe_round`，同回合只扣一次 → `aos7_daemon_timeline.py`
- C｜K3：多個 timeline 設定同時不合法只回第一個錯；interval 上限一年（超過用預設並記錯）；錯誤訊息帶值截 60 字
- C｜K3：R8-05 用假 daemon 單元測試（真 daemon 無法穩定只讓 tock 後那次讀取失敗）
- C｜K4：worktree 改放 `../aos-wt/<隊>`；`inject("write")` 放開暫存檔前（打中不留暫存檔）
- C｜T1：行數檢查用 `ENFORCE = False` 開關關掉（不刪斷言，好改回）→ `tests/core/test_budget.py`
- C｜T1：`check_rules()` 遇 `@file` 規則在檢查時才讀檔（跟 daemon 中途換規則一致；代價：檔案中途改了可能放過漏打的規則）
- 觀察｜`test_diag.test_unsure_listed` 在多隊同時跑全套時連紅約九次、單跑全過；暫視為負載造成的時序不穩，再出現就歸 bug 線
- B｜X：新模型級別全部暫定（依據一題各跑一次）：A？gpt-6.1-sol、gpt-6-astra；B？gpt-6-sol；C？gpt-reserve、gpt-5.5；D？Haiku 5.5、gpt-6-luna → [team-model](../../wf/workflows/team-model.md)、[probe](../../wf/workflows/team-model/probe-2026-10-09.json)
- C｜X：碰程式碼仍不派 Sonnet（使用者 09-30 說過）；要兩份獨立 codex 意見時用不同 slug
- C｜T2：T8-05 用 mock `aos7_tock.fact`（藍圖選項 a），不在正式程式加注入點
