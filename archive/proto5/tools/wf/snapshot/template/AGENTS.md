# {{專案名}} — AI agent 專案備忘

{{專案名}} = **{{一句話：這專案是什麼、產出什麼}}**。本檔是最頂層路由器，只指向下一層；細節不寫這裡（分層原則見 [STRUCTURE.md](STRUCTURE.md)）。

## 開場與入口

- 每個 session 先跑 `grep -c '^- \[' SESSION-LOG.md WAIT_USER.md`：非 0 才開 [SESSION-LOG.md](SESSION-LOG.md)（進度）/ [WAIT_USER.md](WAIT_USER.md)（等使用者）。
<!-- wf-insert:AGENTS -->
- **要你動手做事** → [WORKFLOWS.md](WORKFLOWS.md) 依意圖派發，再讀該工作流入口檔。
- **想看專案結構** → [INDEX.md](INDEX.md)。
- 使用者偏好與邊界 → [workflows/common/user.md](workflows/common/user.md)。

## 鐵律（always-on，隨時適用）

1. 重構 / 整理**不改原意**：開發＝行為不變且驗證綠燈（{{測試 / build / lint 指令}}）；非開發＝原意不變，照 `Done when:` 驗收。
2. **不可逆或對外的動作**（push、刪除、對外送出、動 DB）要有**授權來源**：使用者當場確認，或他親自登記在清單裡（routines / schedule）。都沒有就先問。
3. **條列走資料檔、導航留 md**：給 AI 消化的表／清單 >1 KB 存 `.json`／`.csv`（契約 `wf-table/1`，見 [data-files](workflows/common/data-files.md)），用 `tools/tabledb.py` 讀寫、不整份讀進 context；給人點的導航連結留 md。
4. **具體流程**在各工作流入口檔，不在頂層。

> 〔模板說明〕鐵律 3–5 條，且必須「任何時刻都適用」才夠格；只在特定場景適用的規矩下放該工作流。填完後刪除本段。

<!-- wf-kernel v0.6 (2026-09-02) -->
