# 工作材料與結果

← [基底](README.md)｜[共用契約](../contracts.md)｜[inst](inst.md)

## B-101：固定工作材料〔建議預設，未拍板〕

工作與嘗試的 ID、結果配對以 [共用契約](../contracts.md) 為正本。執行方接納請求後固定該次 inst 與輸入材料，也保留其 base 語意，不因副本位置改變相對路徑基準。

`kernel.work.submit` 的 params 是執行 `aos kernel work submit` 的 [inst](inst.md)，工具 inst 與輸入材料由該指令讀取。工作執行限制：`timeout_ms` 建議預設 60000（〔暫定，第二十批疑-11 未答，照 a〕保留毫秒：程序在格外跑，由 runner 用 monotonic 時鐘量，[B-203](execution.md)）、`output_limit_bytes` 建議每條捕獲串流 1048576。兩者須為正整數，屬工作材料／執行器設定，不加進 inst。stdin 用一般檔案引用；需要固定 bytes 的輸入，隨請求保存成該次材料。固定材料不代表凍結程式、整個 workspace、環境或外部 `$ref`；指示詞仍在目標身分下才解，外部可變輸入的可重現性由呼叫方安排。

〔第十九批依方案 A 從 [P-402](../protocol/work.md) 搬上〕**掛載行程的身分**：掛到 daemon 跑的工作（[B-613](../settled/deferred/daemon/channel.md)），外層 inst 用工作所屬 node 已授權的有效身分；內層（工具）inst 省略 `user` 時繼承這個身分，寫了就必須解成同一個 UID，否則照 [inst](inst.md) 回 125。kernel 替成員派工時不可讓工具繼承 kernel 自己較高的權限。

派送、消費與失敗恢復以 [Q1／Q2](../settled/tick.md)（收件、投件與 git 任務，B-623、B-624）為正本。

**驗收：**排隊後改來源 inst，已接納工作仍用固定的那份；固定的 stdin 副本不跟著來源改。送出後在結果發布前崩潰，不因重啟再執行同一 attempt。

<a id="b-102特權與解析分界建議預設未拍板"></a>
## B-102：特權與解析分界

（09-29 重寫：已刪／併入 [B-303](../settled/deferred/helper.md)；切身分後才解析見 [inst](inst.md)。）

## B-103：結果檔〔建議預設，未拍板〕

執行器為每個 attempt 完整發布一份結果檔，至少帶工作／嘗試 ID、結束原因、可取得的退出碼或 signal、stdout／stderr 的檔案引用、保存的 bytes 與截斷標記。沒有的資料明示缺失，不編造內容。可辨別正常退出、訊號、啟動失敗、逾時、取消、已證實的 OOM、輸出超限，以及無可信結果的 unknown；不再套多層結果封套。完整發布與消費照[儲存](storage.md)，程序收尾照[執行器](execution.md)。

inst 的 `exit` 檔只記程序結束碼，不能代替這份執行結果。argv 寫到 stdout 的文字也不能冒充執行器證據。檔案 JSON-RPC 的成功回應使用同一工作結果格式，表示所請指令的執行結果。〔使用者方向 2026-09-30，第十八批〕當格就做完的本地動作（例如 `agent.say`、`work.cancel`）也要讓結果可被引用：stdout 存成追蹤的 `.stdout` 檔、跟消費副本同組提交，回應的 stdout 指向它，不填 null（落點見 [P-306](../protocol/messages.md)）。exit 0 且完整收尾只表示程序正常結束，產品任務是否成功由上層判斷。

捕獲輸出達上限後仍排空 pipe、丟棄超額 bytes，並發起收尾；結果標輸出超限與截斷，不能堵住子程序或繼續無限保存。這個上限只管執行器捕獲的串流，不限制工具自行寫檔；磁碟政策見 [B-304](identity-resources.md)。保存不完整也要可見，不能靠自動重跑找回輸出。

**驗收：**無限輸出得到有界且標示截斷的失敗結果；退出 7 可查到原碼；exit 0 不直接宣布整輪任務成功。
