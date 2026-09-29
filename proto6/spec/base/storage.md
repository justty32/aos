# 儲存與持久交接

← [基底](README.md)｜[共用契約](../contracts.md)

## B-401：權威與存放位置〔建議預設，未拍板〕

Owner：控制層唯一 SQLite writer。SQLite 保存 owner、ready、due、jobs、attempts、run、claim、generation、checkpoint pointer、消費 cursor 及派工意圖。agent home 保存輸入、歷史及 checkpoint 本體；受管不可變內容庫按 agent 分區，與該 home 在同 filesystem，啟用磁碟額度時指派同 project quota、兩者共用記帳額度（B-304）。內容庫由管理者持有，agent 只經唯讀 fd 取得已提交 blob；可編的配置與 source 草稿仍在 home。這是為完整性及容量閉合新增的可替換預設，不將所有資料複製進無上限 global control。控制庫只保存有界 metadata、登記及小型錯誤；pending jobs 採 [S-203](../scheduling/admission.md) 的部署必填 max_pending_jobs；部署可另設 per-agent pending 額度（正整數），未設不增加第二個隱含預設，達任何適用上限拒絕新提交。agent 不得直接修改 SQLite 或權威 pointer。控制根預設目錄 0700、檔案 0600；跨 UID 讀取只經受控導出，不將整個 DB 給 agent。

BlobRef 依 C-03 以受管 key 定址並保存 SHA-256，禁止把 ID／摘要解讀為任意路徑；所有根由登記取得。尚未導入的 home 候選可被 agent UID 改寫，控制層不能相信名稱：可信導入者以 agent 權限開 fd，限制大小、拒絕 symlink／非普通檔，取快照重算摘要後交控制層。控制層只引用受管庫的已驗證快照；需恢復而受管 blob 已毀損時報完整性錯誤，不執行其內容或改指較舊狀態掩蓋損毀。

**Given** agent 篡改 blob 或放 symlink 指向控制檔；**When** 導入與恢復；**Then** 摘要不符／檔型不符被拒，沒有特權代讀與 pointer 更新。

## B-402：發布與崩潰耐受〔建議預設，未拍板〕

檔案發布流程：同 filesystem 暫存檔→完整寫入→fsync 檔→rename 至唯一正式名→fsync 父目錄。SQLite 使用 WAL、foreign_keys=ON、synchronous=FULL；單一 writer 的交易不得包含等待網路或執行工具。只有檔案與必要 DB/outbox 均完成耐久提交後才向客戶端確認收件。檔案先發布再寫 DB，裂縫以原收件 spool 的持久索引修復；不能只相信另寫一次的 outbox。

控制層對每次出站交接先同交易保存意圖，再嘗試交付；接收後記 ack。啟動／低頻巡檢重放未確認意圖，穩定 ID 保證本機去重。缺 blob 的 DB 引用標完整性錯誤並停相關工作；無引用 blob 僅是待回收候選，不能立即視作完成工作。

**Given** 在 fsync、rename、DB commit、通知之間逐點斷電模擬；**When** 重啟；**Then** 已確認請求可恢復，未確認請求可安全重送；沒有半 JSON、缺檔卻成功或重複派工。

## B-403：checkpoint 提案交易〔建議預設，未拍板〕

tick 輸出共用契約 C-05 的 Proposal，欄位與 JobDraft 不在本篇另定。checkpoint blob 預設最大 16 MiB，提案 JSON 最大 256 KiB。可信導入者快照驗摘要後，控制層確認 generation 等於 current claim、expected_revision 等於目前 revision、消費 IDs 均已交付且未跨 owner／run、job IDs 未衝突。

驗證成功，在同一 SQLite 交易提交 checkpoint_ref、revision+1、消費 cursor、派工意圖及提案收據（claim／名額釋放仍待程序清空）；新到事件保留 ready。交易失敗全部不生效，不得提前 ack 消費結果或派工具。相同 attempt／revision／提案摘要重送回原結果；同鍵不同摘要拒絕；舊 generation 拒絕且不發布副作用。派工由已提交意圖驅動，不能由 tick 提交前直接啟動。

**Given** 結果消費後、交易前 tick 被殺；**When** 新 tick 恢復；**Then** 讀舊 cursor 再處理但不重複已提交工作。交易後回覆前被殺則重送回同一提交結果。

## B-404：滿碟、保留與回收〔建議預設，未拍板〕

管理者必填 control 容量保留政策；僅換目錄不算保留。控制區 ENOSPC／EIO 時停止新准入，禁止確認尚未持久的請求；既有 supervisor 仍應取消與收尾，恢復後無可信結果則 unknown。agent quota 滿依 B-304；控制側每 attempt stdout／stderr 上限依 B-101，其他診斷限 64 KiB，不能用 log 繞過 quota。

終態結果在消費 ack 前不得回收；ack 後仍至少保留至所屬 run 終局後 30 日，審計 metadata／去重 tombstone 同期保留；無 run 的維護結果自終態日起留 30 日；pending／unknown／未結清外部副作用引用一律保留。GC 僅由控制層在交易取得無引用候選，刪檔後提交完成；重啟可重做缺檔刪除。agent 退役不自動刪資料。Blob 導入暫存遇中斷可於確認無活導入者後回收。

**Given** 控制磁碟滿或 GC 中途重啟；**When** 新收件／恢復；**Then** 不虛報 durable success，不刪未 ack 結果，重複清理不影響引用中的 blob。

機制依據：[SQLite synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous)、[fsync 與目錄耐久性](https://man7.org/linux/man-pages/man2/fsync.2.html)。FULL／fsync 的保證以底層檔案系統與裝置遵守同步為前提，不能修復硬體謊報成功。

## 待使用者拍板與現況

所有容量上限、保留天數及 layout 為預設；共用契約決定具體 DB 邏輯欄位，實體 schema 可後定但不得破壞原子提交要求。尚未實作。
