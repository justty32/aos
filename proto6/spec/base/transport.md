# 通訊與交接

← [基底](README.md)｜[共用契約](../contracts.md)

## B-501：認證入口與 envelope〔建議預設，未拍板〕

Owner：控制接入口。JSON-RPC 2.0 欄位及 Error 遵守 C-04；不接受 batch、notification、浮點或 null request ID。單封 UTF-8 JSON 最大 256 KiB；拒絕重複 key、未知欄位及版本。可信 sender 取自受控 socket peer 身分或每 UID 獨立受管提交通道，不能取 payload 的 sender／owner。管理者操作與 agent 操作分權；同 UID 的 tick 與工具不是相互隔離的安全主體，工具可使用 owner 所允許的普通操作，但不能提交缺乏 live claim 授權的 checkpoint。

檔案傳送可用管理者持有的共用 spool：非特權入口先以 sender 身分讀取候選、限長並導入唯讀快照，再由控制端解析純資料。禁止 root 跟隨 sender 指定 symlink、開 redirect 或執行 inst。只往 agent home 隨意放檔不算正式接件，不承諾喚醒；正式入口須保存 durable spool，給定消息由控制層投遞到 home。

**Given** A 把 params.agent_id 改 B 或造 sender 欄位；**When** 投件；**Then** 未授權時拒絕，沒有 B 的 run／ready 更新。損壞 JSON 得解析錯誤，沒有部分接件。

## B-502：最小操作集合〔建議預設，未拍板〕

params 欄位未註可省均必填，型別 ID／BlobRef 依共用契約；所有操作先認證授權，查詢亦同。標準接納回覆為 C-04 accepted，不表示完成。

操作與欄位正本見 [methods.json](methods.json)。包含 agent.submit／get、run.get／pause／resume／cancel／resolve／outputs、attempt.get／cancel、checkpoint.commit 與 result.ack；各method的params、授權與result只在該資料檔定義。

run.cancel 的接納交易先寫取消意圖；取消未啟動 job 可直接終態 canceled，有程序者交 B-203。run 何時成 canceled 由排程規格判斷，仍存活不明不得冒充停止。工具結果不是可由工具自行 RPC 宣告的成功：supervisor 以可信內部通道提交 B-103 及 Outcome。tick 消費結果時 ack 與 checkpoint 交易共同提交，不能提前 result.ack；此 method 供已保存持久消費證據的其他可信接收端使用。

**Given** 接納 agent.submit 後立刻查 run；**When** 工具尚未完成；**Then** run.get 顯示 queued／active 等當前狀態，不能把 accepted 當 final。未授權的 result.ack 被拒且結果仍保留。

## B-503：去重與三種確認〔建議預設，未拍板〕

去重鍵固定 `(authenticated sender,target agent_id,method,request_id)`；target agent_id 由已授權目標解析（run／attempt 查帳本歸屬）；canonical digest 使用 RFC 8785 JSON canonicalization 的 method＋params（包含 agent_id、payload version 與 BlobRef），不得含傳輸檔名或重送時間。首接成功保存鍵、digest 與原回覆，同交易建立 run／操作意圖。相同鍵同 digest 回原回覆；不同 digest 回 conflict。不把相同文字、不同 request ID 自動去重。保留期限依 C-06。

收件確認表示材料與操作意圖已持久；完成結果表示一個 attempt 終局；消費 ack 表示接收端已持久記錄消費。三者不同。result.ack 摘要亦用同 canonicalization；重複 ack 不重複結算，摘要不符回 conflict。網路／檔案傳送可重複但不遺漏；不承諾外部副作用 exactly-once。

**Given** 收件提交後回覆前中斷；**When** 重送同 ID；**Then** 返回同 run_id，不建第二 run；改正文重送同 ID 則 conflict。

## B-504：通知、重放與遺失〔建議預設，未拍板〕

事件先保存 spool／DB 意圖再通知；通知可合併或遺失。控制層維持持久巡檢游標，補查週期、批次與覆蓋時間語意以 [S-202](../scheduling/admission.md) 為唯一預設，不另承諾完整巡回時限。正常路徑只處理受影響 agent，不掃全部 home。inotify overflow／重啟設定需修復，按游標重新對帳，仍須接新件；冷 agent 不為巡檢而起程序。

接入口不可用時 caller 得明確錯誤或未確認結果，使用原 request ID 重試；不能當成已接件。查詢已回收內容回 gone，保留 tombstone 防重建。準確逐字串流不屬首版，輸出完整性仍按 B-103。

**Given** 故意丟通知並重啟控制端；**When** 執行補查；**Then** 所有持久未交接請求在預算內恢復，重複通知不多開 tick，沒有啟動一萬個 idle 程序。

canonicalization 機制依據：[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)。數字須符合契約整數範圍，拒絕非有限數；canonical JSON 只規定 digest 材料，不授予欄位權限。

## B-505：Blob 導入、讀出與對話輸出〔建議預設，未拍板〕

責任為認證入口的可信本機 adapter，不要求新增獨立 daemon。`import_blob(principal,agent_id,read_fd,expected_sha256,length)` 接收呼叫者以自身權限打開的普通檔案 fd；length非負整數、預設單blob上限16MiB。adapter驗證principal可向該owner導入、限長快照並重算摘要，保存至該agent受管內容庫且（啟用時）計projectquota後，才回C-03 BlobRef。它不接受任意host路徑由root代開；未讀完、摘要不同、額度不足分別回invalid_record／conflict／quota_exceeded，不發成功引用。import只保存材料，不建立run，沒有接件承諾。

`export_blob(principal,agent_id,ref,write_fd)` 驗證owner讀權及ref歸屬，再向呼叫者已打開的輸出fd傳送已驗證內容；缺失／回收回gone、毀損回integrity_error，不以ref.key拼任意檔案路徑。大資料用fd有界串流，JSON-RPC 256KiB上限不因此放大。對話輸出由run.outputs按output_seq增量列取已提交Output，再用此adapter讀其引用；未提交進度不可偽裝final。

人的普通投件路徑因此是：客戶端產生A-201輸入JSON→import_blob取得ref→agent.submit→run.outputs/run.get→按需export_blob。CLI語法與網路遠端upload後續再定，本地adapter的認證和錯誤契約已足以實作。tick的proposal內容同樣先導入再commit，adapter授權本身不授予live claim。

**Given** 使用者僅有文字而沒有BlobRef；**When** 經adapter導入、提交、查輸出；**Then** 可完成完整往返。另一agent拿到ref.key仍不能讀出；quota滿不回引用也不建立幽靈run。

## 待使用者拍板與現況

操作名稱、傳輸上限與修復門檻為建議預設；介面供程式使用，不直接等同人用 CLI argv。尚未實作。
