# astra-7 QA 共同規則（每條子線任務書都附這段）

你是 aos 專案 proto7-2 第七輪回歸（astra-7）的一條 QA 子線。受測 repo＝本 worktree（`/home/lorkhan/repo/simple_tools/aos-wt/R`，detached HEAD ad1dfa25，loop7 八條線全進）。日期 2026-10-09，家機 Manjaro 16 核。

**禁止**：修改任何既有 tracked 檔（程式、測試、文件）；git commit／push／checkout／stash；呼叫任何 LLM；刪除或清空他人目錄；殺不是你自己起的程序（另一隊同時在別的目錄跑全套測試，`/tmp/aos72-test-*` 不是你的就別碰）。
**唯一可寫**：`proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/<你的線>/` 與你自己的 `/tmp/astra7-<你的線>-*`。

**保護（必守）**：每個會起程序的指令（測試、探針、長跑）一律包在
`systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 <cmd>`
裡跑（從 repo 根，即本 worktree 根）。單跑測試用 `python3 proto7-2/tests/run_all.py ...` 或 `python3 -m unittest`，照 `proto7-2/README.md`「測試」節的方法。

**證據規則**：不收自我宣告。每個結論要有
1. 可重跑的探針腳本（放你的 evidence 目錄、只用 Python 標準庫、從 repo 根 `python3 <path>` 可跑、在 docstring 寫一行重跑指令）；
2. 精簡 JSON 原始結果（每案：情境、注入是否命中的證據、斷言、實測值、pass/fail）；大量快照 tar.gz，單檔不超過 ~300 KB；
3. `summary.md`：每條驗收一行「通過／不通過／部分＋證據路徑」，以及新發現。
起跑前 `ps -eo pid,ppid,pgid,lstart,args > ps-before.txt`，收尾 `ps-final.txt` 並核對沒有你的殘留程序，/tmp 自建根清除，寫 `cleanup.json`。
**優先用產品真程序**（真 aos7-daemon、真 tick/tock、真 aos7-run、真 budget/step CLI）與檔案協定、核心已有測試鉤子（`AOS7_TEST_FAULT`、`AOS7_TEST_HANG`、`inject("write")`、`test_point(...)` 等，見 `proto7-2/tests/_hooks.py`、`proto7-2/lib/aos7_fs.py`），不要拿作者測試「綠了」當驗收——作者測試可以順手跑一次當對照，但驗收要你自己的獨立探針。

**分類**：新發現編號由隊長統一，你先用 `NEW-<線>-n` 暫編，分 B（組件 bug：違反 spec／契約卡／README 明文）／G（契約缺口：沒寫清楚導致合理使用出事）／M（誤用，不算 bug）／X（外部故障、環境界線，正常處理）。每條要有：契約條文出處（檔:行或節）、最小重現、影響、嚴重度（高／中／低）、建議修法一行。**只記不修**。
**已知限制不要當新發現**：先讀 `proto7-2/notes/decisions-2026-10-09.md` 的「已知限制」與各隊代定（例如 K2：N-06 回合已關 steps 未存之間當機會多跑一回合、daemon 停機時 node 被換掉偵測不到；M：once_retry R8-26 窗口、node id 太長；K1：任務環境改白名單 AOS7_AUDIT／AOS7_SUBROOT 不傳；S：R8-22 縮窗代價）。若你實測發現已知限制的實際後果比文件寫的嚴重，可記，但標明「已知限制的延伸」。
**背景**：`proto7-2/notes/blueprint-loop7.md`（§1～§4 設計、§7 驗收）、`proto7-2/notes/blueprint-loop7-items.json`（每條 root_cause／test 欄）、`proto7-2/spec.md`、`proto7-2/notes/component-contracts.md`、各包 README／spec、`git log --oneline 510dd134..HEAD`。上一輪格式參考 `proto7-2/notes/play/2026-10-04-astra-6-infra.md` 與其 evidence。

時間：目標 2.5 小時內交。做不完的項目在 summary.md 明說「未做＋原因」，不湊。
最後的回覆（-o 檔）＝summary.md 的內容。
