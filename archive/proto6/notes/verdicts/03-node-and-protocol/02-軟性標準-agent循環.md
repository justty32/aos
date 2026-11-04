← [2026-09-29 使用者裁定（三）：node 與協議篇](../03-node-and-protocol.md)（分檔 2/3）｜[上一份](01-第六至十一批.md)｜[下一份](03-第十二批-協議細節.md)

## 軟性標準：一步一步走完整套 agent 循環（同日）

〔使用者方向 2026-09-29，軟性標準〕以一整套 agent 循環為目標：從零開始（寫 daemon 設定、開 daemon、建頂層 node、設 LLM 池、建 agent node、登記、傳訊、看它 tick、看回覆、處理待辦、清理、停機），每一步都要能讓人用指令推進、看得到結果。CLI 規格以這條走查檢驗：走不下去的地方就是缺指令或缺協議。
- **CLI 結構**〔使用者方向 2026-09-29〕：`aos <用途> <動作> ...`，第一層依用途分（daemon／kernel／agent／node 等），子命令後還能再接子命令；不怕多、不怕深，常用的用 alias 縮短。中間層也可以是用途，例如 `aos agent tools add ...`（agent 用途下的 tools 用途）。
- **停 daemon**：首版就用前景 Ctrl-C（SIGINT／SIGTERM 照停機流程），不做跨終端 `aos daemon stop`。
- **下一輪**：定 agent 與 kernel 的最小預設任務程式與 `aos node new` 範本，補走查缺口；CLI 改大白話、加入工具改成 `aos agent tools add/rm/ls`。
- **LLM 請求送去哪＝agent 設定裡的一個位址**〔使用者方向 2026-09-29，取代「一律交給自己的 kernel」〕：請求／結果格式只有一種，agent 照設定的位址送（node id），不管對面是誰。路線由開 agent 的 kernel 在建立時決定，牽涉權限與資源管理路徑：
  - **kernel 全部都管**：位址設成自己；kernel 裝「LLM 轉交」module，收請求、扣額度、排隊，再交給自己的池、上層 kernel 或別的 kernel。
  - **kernel 不管**：開 agent 時給它權限，直接往管池的 kernel（LLM kernel）收件區丟；kernel 改裝「用量收集」module，定期讀 agent 自己記的用量。
- **kernel 別每格都重新註冊**〔使用者方向 2026-09-29，要考慮負擔〕：重新註冊成員只在需要時做（daemon 重開後、成員清單變動時），不要每格都全部重送。
- **agent 日常對話沿用 proto5**〔使用者方向 2026-09-29〕：`aos agent say`（投一句話）／`aos agent listen`（看回話，含 `--last`／`--wait`／`--follow`），承襲 proto5 aos-agent 的 say／listen。
- **收件分兩格，名字沿 proto5**〔使用者方向 2026-09-29〕：`inbox/` 拆成 `requests/`（別人問我）與 `responses/`（我問別人、別人回我）。回應仍**投回發問者家**的 `responses/<id>.json`（不像 proto5 留在回答者家等人來拿、也不用 ack）：node 不常駐，tick 只看自己家就好。兩格都在 `.gitignore`；`reply_to` 指發問者 node，回應落在它的 `responses/`。
- **啟動失敗旁檔改名**〔使用者方向 2026-09-29〕：inst 檔名後面直接加 `.err`，例如 `job.json` → `job.json.err`；取代 `.launch-error.json`。
- **node id 唯一性不另防**〔使用者方向 2026-09-29〕：同一資料夾經 symlink 有兩個路徑、同一路徑先後給不同 node、跨機器重名，這三種都不在考慮範圍內，風險由使用者自行承擔；spec 不加展開 symlink、世代號或跨機檢查。
- **`inbox` 這個名字保留**〔使用者方向 2026-09-29〕：之後要拿去做工具，node 布局不用 `inbox/` 當資料夾名；收件就是根下的 `requests/`、`responses/`。
- **daemon 的待處理事項盡量走 IPC**〔使用者方向 2026-09-29〕：平常靠 IPC 查；磁碟上的資料夾只為 daemon 關掉重開後接續用。
