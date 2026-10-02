← [整理區：tick 與 daemon 的基礎](../README.md)（分檔 4/5）｜所在段落：疑點｜[上一份](03-疑點-1001第二批與訊息佇列.md)｜[下一份](05-疑點-前輪暫定與已關.md)

### 納入 git 與 cgroup 後，區外的狀況

**已改到不矛盾**（只換掉「本輪／下一步納入」這類句子，沒重寫）：terms T-01、T-06；spec 入口的定位與依賴段；contracts C-01（格數斷電不倒退只在開 `--firstdo-fsync` 時保證）、C-05 殘句、C-07 第 3 點；base [B-202、B-204](../../base/execution.md)（`aos-cg` 改指 B-634）、[storage 篇首與 B-404](../../base/storage.md)、[transport 篇首、B-502、B-503 驗收](../../base/transport.md)、[inst 撤回範圍句](../../base/inst.md)、[B-302](../../base/identity-resources.md)、base/README；[P-603、P-606](../../protocol/ops.md)；[P-305](../../protocol/messages.md)；[A-102](../../agent/configuration.md) 第 15 行；V-01～V-03。

**仍跟新規則衝突、下一輪要改**：

| 篇 | 條號 | 衝突在哪 |
|---|---|---|
| agent | [A-102](../../agent/configuration.md)（第 17、21、24 行） | 「由標準配備的 git 提交」「node 是 dirty 就拒絕」；現在 `config/` 不在 aos 範圍、`aos-config-add` 不提交（2026-10-01 `aos-config-add` 搬暫緩區，A-102 那段已標暫緩） |
| agent | [A-403 等](../../agent/tools.md) | 「標準配備」「cgroup 讀數；備援」字樣 |
| base | [B-503](../../base/transport.md) | 補投從 git 歷史撈 `.aos/outbox/`（檔案收件已不歸 aos） |
| base | [storage](../../base/storage.md) 第 12、31 行 | 「git 還原不碰」與提交語意是整格原子的舊說法 |
| 範本 | [P-814](../../protocol/kernel-tasks.md)、[P-715](../../protocol/agent-tasks.md) | 還沒有有 git 版範本 |
| scheduling | [S-203、S-205](../../scheduling/admission.md) | kernel 資源任務經 `cgroup_limits` 寫上限、沒 cgroup 時只記帳，要核對 |
| CLI | [H-004](../../cli/commands.md)、[H-036](../../cli/walkthrough.md)〔astra 報告必修 9〕 | `aos node new` 建初始 commit、建 `.aos/mq/get/` 並設權限、`--firstdo-fsync` 旗標 |
| 原型程式 | `proto6/proto/aosproto/config.py` | 還把 `cgroup_create` 當合法佈建動作 |

### 納入 git 與 cgroup：原暫定 13 題，已定案

使用者 2026-09-30 對這 13 題說「隨意」，照暫定寫法定案（[裁定](../../../notes/verdicts/11-tick-as-unit.md)），對應條文的「暫定」標記已拿掉。定案內容：

- B-630、P-205：兩個相鄰存檔點之間全是 `kind:"system"` 的段才算 aos 範圍，`kind` 照紀錄 `id` 查任務表；`aos-git mark <路徑…>` 讓使用者任務把自己的檔加進 aos 範圍；失敗還原到往前最近的存檔點。
- B-629：第二個存檔點放在清理之前；範本 `id`（`git-open`、`mark-get`、`mark-user`、`git-close`）。
- B-623、B-624、B-630：作廢那格 `mq-get` 取出的訊息丟失、`mq-post` 已送檔下一格重送，靠 ID 去重。
- B-622：只有開頭檢查算「不能用」，做到一半失敗算故障（擋板＋停格檔，含任務 id 當不了 ref 名）。
- B-625、P-207：`config/` 不在 aos 範圍，`aos-config-add` 不自己提交。
- B-605、B-601：某 node 建框失敗只有它照沒 cgroup 跑、寫事項。
- B-609：`cgroup_limits` 不收本格憑證。
- B-633、B-601：`--firstdo-fsync` 由 daemon 放環境變數 `AOS_TICK_FIRSTDO_FSYNC=1` 傳下去。（2026-10-01 跟落盤一起暫緩，見[暫緩區](../deferred/tick.md)）
- B-614、P-200：佇列授權看收件 tick 的 `.aos/mq/get/`。
- B-624、P-206：失敗紀錄搬到 `.aos/mq/failed/`，由 `mq-post` 下次開始送之前清掉。
- **同 ID 撞檔名（原第 13 題，沒有現成做法，落 spec 者挑最簡單的）**：`.aos/mq/post/` 與 `.aos/mq/failed/` 的檔名改成 `<id>.req.json`（請求）、`<id>.resp.json`（回應），同 ID 的請求與回應各有各的檔（P-206、B-624）。
