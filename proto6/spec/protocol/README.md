# 協議篇：共用約定與分工

← [規格入口](../README.md)｜[共用契約](../contracts.md)｜[通訊](../base/transport.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

本篇把既有規格落成**程式之間**的 argv、資料流、檔案及 JSON 格式。第一階段只訂共用底稿及後續五份文件的邊界，尚未建立正文、schema、範例或實作；本文列出的後續檔名是交付清單。人手操作的 CLI 留待之後。本輪仍依使用者明示範圍，只納入新增掛勾、`aos-clean`、`aos-attend` 的機器交接，不展開手打指令或 y/n 介面。

## P-001．來源、責任與平台〔主編補〕

來源標記沿 [T-01](../terms.md)。[09-29 裁定](../../notes/2026-09-29-verdicts.md) 優先；C／B／A／S 條款保存行為與欄位正本，本篇只決定共同編碼及傳送方式。新增的格式選擇標為〔建議預設，未拍板〕，不藉 schema 替使用者定產品方向。發現正本未定，先列 P-011 待決；不能先增加可呼叫 method，再說只是補格式。

〔使用者方向 2026-09-29〕人用的指令與檔案就是 agent 用的指令與檔案：協議不為 agent 另開一套入口，agent 經權限開放後呼叫同一批程式、讀寫同一批檔案，授權照呼叫者身分判定（見 [spec 入口原則](../README.md#原則能下指令能管檔案就能交給-agent)）。

邏輯 owner 不必各開一個 daemon。同程序模組呼叫不必套 RPC 或丟檔；跨程序／跨故障邊界需要持久交接時，才採本篇。控制帳本、通知副本、候選檔與子程序 stdout 各有責任，不能互相冒充。

〔使用者方向 2026-09-29〕原生 Linux 與 WSL2 使用同一套 JSON、目錄與程式協議，差異只沿[平台一節](../README.md#平台原生-linux-與-wsl)及 B-603／B-604 的部署、恢復與停機設定。Windows interop、Windows 掛載權限與 Windows 磁碟水位不另加檢查；牆鐘與 VM 關機照既有規則。daemon 由 systemd 啟動，主 daemon 非 root，root helper 與 LLM 專用服務 UID 的邊界照裁定，不因本篇改動。

驗收：Given 在兩平台傳入同一請求，When 解碼或重啟補查，Then 欄位與交接語意一致；沒有新增人用 CLI、常駐 CPU worker、串流或孤兒工作接續承諾。

## P-002．JSON、型別與版本〔建議預設，未拍板〕

JSON 使用 UTF-8、無 BOM；一份材料恰好一個 JSON 值，協議 envelope／紀錄根為 object，尾端只可有 JSON 空白，不能接第二份值。解析前先檢查 byte 上限；解析時拒絕無效 UTF-8、重複 key、非有限數及尾隨資料，不採「最後一個 key 勝出」。blob 的原始二進位內容與 text 工具 stdout 不因此必須是 JSON。

基本型別、ID 格式、大小寫、整數範圍、bool 不可代整數、毫秒時間、必填／可省／null、未知欄位及 `extensions` **直接沿 [C-01](../contracts.md)**；Error 與 RPC 直接沿 C-04，入口拒絕條件沿 [B-501](../base/transport.md)。時間欄位以 ms 表達，既有 `cpu_quota_us`／`cpu_period_us` 等明標單位欄位保留其原義，不能把數字原封換成 ms 名稱。逾時用經過時間，排隊用持久序號，不靠檔名、mtime 或牆鐘。

整數限制不等於全面禁止浮點：A-401 工具 schema 明許 `number` 的值仍按該 schema；ID 與指定 integer 欄位不可收浮點或 bool。JSON Schema 不能單獨完成原始 token、重複 key、byte 長度與權限檢查，解析器及語意驗證須另外落實。

持久紀錄必帶 `version:1`，未知版本拒絕。原 JSON-RPC envelope 的版本是 `jsonrpc:"2.0"`，不加未定的 `version`；嵌入的 BlobRef、Error 等也不擅加欄位。需要持久保存 RPC 時使用 P-005 外包裝；工具 arguments 仍為 A-401 原物件，不強加 version。省略值只按正本取預設，不將 `null`、空字串與省略混為一談。

驗收：Given 重複 key、過界整數或未知欄位，When 驗證持久紀錄，Then 拒絕且不部分生效；合法工具 number 不因共通解析器而被誤拒，純 RPC 不因缺少額外 version 而被拒。

## P-003．資料夾與檔名〔建議預設，未拍板〕

各根路徑由可信部署設定給定，不能從輸入 ID 或 payload 自選；下列是**每個已登記提交通道**的相對布局，不是所有服務共用一個可寫大目錄。`channel_id` 綁定可信 principal、UID 及服務用途，名稱本身不授權。

```text
<entry_root>/<channel_id>/
  .tmp/                         sender 寫候選暫存
  requests/<delivery_id>.json    sender 發布候選；尚非 accepted
  responses/<delivery_id>.json   入口受控匯出回覆，sender 唯讀

<spool_root>/<channel_id>/       僅入口／對應接收 owner 可寫
  .tmp/
  requests/<delivery_id>.json    已限長、認證並導入的持久快照
  processing/<delivery_id>.json  已取出處理的交接快照
  responses/<delivery_id>.json   持久協議回覆
  done/<delivery_id>.json        本次交接已得到正常回覆的原件
  failed/<delivery_id>.json      本次交接被拒的原件
```

`delivery_id` 使用 C-01 ID 型別，是一次傳送的檔名識別；不是 request／job／attempt ID，也不當去重鍵。request 與 response 用同一 delivery_id 配對；回覆內 JSON-RPC id 才對應 request_id。重送可用新 delivery_id，但保留原 request_id 與內容。暫存名為 `.tmp/<delivery_id>.<nonce>.tmp`，nonce 亦為 ID；僅正式 `.json` 名稱可進入處理。建立正式名不得覆蓋已有不同內容；撞名回報衝突，不用 mtime 選勝者。檔名不含 owner 宣告、路徑分隔或使用者正文，目錄列舉順序不代表排程順序。

`processing` 只表示接收端正在處理**這次交接**；`done` 只表示已有正常協議回覆，可能僅為 accepted，絕非 job succeeded；`failed` 表示本次入口驗證／交接拒絕，不將 job 失敗移來冒充傳輸錯誤。業務 failed／canceled／unknown 仍在 Outcome／ExecResult／帳本。處理未完成即崩潰者由持久索引重放，不能把留在 processing 的檔案當成程序仍活或已執行證據。拒件診斷也有上限，解析不了的原件由 delivery_id 找回 `id:null` 的錯誤回覆。

這是一般丟檔通道的共用預設；純 socket 不必製造全部目錄。S-405 待處理通知**保留其專用布局**：`<attention_dir>/open/<agent_id>/<item_id>.json`、控制事項的 `open/_control/`、解除後的 `done/`，不套上述 requests／failed。它是帳本通知副本，刪改檔案不解除屏障；done 的相對命名及控制命名碰撞見 P-011。

驗收：Given 收件 accepted 後工具失敗，When 查看 done 與 run.get，Then 前者只證明交接完成，後者仍正確顯示工作結果；任意向 home 放檔不取得正式收件承諾。

## P-004．發布、認證、通知與重送〔建議預設，未拍板〕

所有承諾耐久的檔案發布沿 [B-402](../base/storage.md)：在目標相同 filesystem 寫暫存檔，完整寫入、fsync 檔、rename 至唯一正式名，再 fsync 父目錄。跨兩個目錄移動時同步兩邊目錄；不能以跨 filesystem 複製冒充原子 rename。跨 filesystem 導入先在接收端重作這套發布，再記來源已處理；來源在接收端持久確認前不能當作可丟棄。來源 .tmp 名稱、rename 成功或 inotify 事件都不是 accepted。

來源候選仍可能被 sender 改寫。非特權入口以該 sender 權限開普通檔案 fd、拒絕 symlink／特殊檔、限長取快照，交控制端驗證純資料；可信副本及必要 DB／outbox 提交完成才可回 accepted。root 不代開 sender 路徑，不解讀 redirect 或 inst。只驗檔內 `sender`、`agent_id`、UID 數字或檔案名稱不構成認證。

控制根的預設權限沿 B-401（0700／0600）。entry 的 channel 父目錄由可信管理者持有，sender 只能寫自己的 .tmp／requests，不能改父目錄、rename 或替換 responses；回覆由入口寫、該 sender 讀。跨 UID 的目錄權限由受控 ACL 或入口開好的 fd 提供，不假設 0700 自動允許另一 UID 進入；其他 agent 不得讀寫。跨 UID 用受控 fd／匯出副本交付，不把控制 spool 或 SQLite 開給 agent。root helper 僅接受經 SO_PEERCRED 核對的控制 daemon UID（B-303）；LLM 憑證只屬專用服務 UID（S-301）；管理者／控制端專用的 attention_dir 不給 agent 讀寫。同 UID tick 與工具不是互相隔離的安全主體，checkpoint 還須 live claim 驗證。

發布檔案可能在 fsync／DB 提交前先觸發 inotify；接收者仍須核對持久材料與帳本，事件不代表 accepted。可控制的出站通知則先保存 spool／DB 意圖，再送出通知；門鈴只提示「有事」，可遺失、合併或 overflow。[B-504](../base/transport.md) 與 [S-202](../scheduling/admission.md) 是補查正本：啟動、overflow、交接不一致時分批對帳，平時按持久游標低頻補查；不另承諾每個週期掃完一萬個 agent，不喚醒冷 agent。

重送與 canonical digest 完整沿 **B-503**，不另造檔名／文字內容去重：鍵是 `(authenticated sender,target agent_id,method,request_id)`，digest 是 RFC 8785 的 method＋params。資料夾位置、delivery_id、重送時間及 P-005 包裝不進 digest。三種確認分開：持久收件、attempt 完成、語意消費；原 request 重送回原收據，確定終局重送按 C-03，proposal 重放及消費按 C-05。無回覆表示結果未確認，使用原 request_id 查詢／重送，不能因此換 ID 再派一次。回覆檔被讀走不算消費 ack，更不授權刪結果；保存與清理沿 C-06／B-404。

驗收：Given 在 rename、fsync、DB commit、回覆、門鈴各點中斷，When 重啟或用另一 delivery_id 重送，Then 已確認收件可恢復、同請求不重建操作，未確認者不被說成成功；冒名 UID 或 symlink 不被特權代讀。

## P-005．檔案與 socket 上的 JSON-RPC〔建議預設，未拍板〕

JSON-RPC request／response 形狀沿 C-04／B-501；禁止 batch 與 notification。request id 必為 request_id 字串，錯誤回覆無可用 id 時才用 null。結果與 error 二選一，不能把子程式 stdout 嵌進 RPC 當成可信成功。method、params、授權及 result 的正本是 [methods.json](../base/methods.json)，不是本篇範例。

檔案保存一份持久包裝 `{"version":1,"message":<JSON-RPC object>}`；只有這兩個欄位，request／response 各一檔，sender 身分另由可信通道記錄，不接受包裝宣告。整個檔案（含包裝）不得超過 B-501 的 256 KiB，內層訊息也不得超過該上限；因此貼近上限的 socket 訊息要改走 blob 引用，不能因換傳輸而放寬入口。持久包裝不是 params，不改 method digest。

本機 Unix stream socket 採**一行一份原 JSON-RPC object，加一個 LF**：JSON 內換行須跳脫，不容許 pretty-print 跨行；接收者累積至 LF，JSON 部分上限 256 KiB，不含分隔 LF，超限即拒絕，不等待無限資料。一次連線可依序送多份，每份仍有獨立 id；不得把同一讀取區塊誤當一封。半行斷線不是完整請求；送出後斷線不表示操作未生效。stdio 的單次 RPC adapter 則讀到 EOF 取得一份原 envelope，stdout 回一份 envelope；若需要落盤，再套持久包裝。

root helper、LLM 派送／回報與 fd adapter 屬可信內部交接，不因有 socket 就自動成為公開 JSON-RPC method；它們由分工文件定 versioned request／reply、受控 fd 角色與認證。需要傳 fd 時不得把本機 fd 數字當成跨程序可用憑證；各篇須指明實際繼承或 Unix fd 傳遞、數量、唯讀／可寫、壽命及關閉責任。一般 RPC 不接受任意 fd 編號或 host 路徑代開。

驗收：Given socket 一次讀到半封或兩封、或回覆前斷線，When 解框與重送，Then 不部分執行、不合併兩個 request、不換 request_id；檔案包裝 version 不污染原 RPC 欄位。

## P-006．錯誤格式及 code 表〔主編補〕

領域 Error 的 `code/message/retryable/details` 與 JSON-RPC `error.code/message/data:Error` **只以 [C-04](../contracts.md) 為共同正本**，整數 RPC code 對應表也在該處，不在五份文件各複製一張。各領域已定的 `config_invalid`、`tool_result_invalid`、`budget_exceeded`、`gone` 等 string code 按原條款列入領域 schema；未特列 RPC 數碼者使用 C-04「其餘」映射，不自增另一套編號。新增 code 或發現正本缺漏須提出待決，不由實作者各取一個值。

只有可用 request_id 才回相同 id；解析錯誤、未知 method 及無可用 id 的處理直接引用 C-04。Error.retryable 不能當重派授權，限流的例外僅沿 S-303。錯誤回覆可對應 delivery_id，不能在 message 洩漏其他 owner 正文、憑證或任意控制路徑。

驗收：Given 收件已成功但之後 attempt unknown，When 查原收據與狀態，Then 原收據不改成 RPC 失敗，狀態保留 result_unknown；用不同傳輸不改 code 意義。

## P-007．程式 argv、資料流與環境〔建議預設，未拍板〕

repo 仍只有一支 `aos` 執行檔；本篇以 `aos <機器子命令> [明列選項]` 表示啟動形狀，具體子命令由分工文件各自定義。控制 daemon、root helper、tick runner、工具 runner／supervisor、LLM 代發服務、blob adapter、清理程式與待辦處理程式是程序角色，不預設都拆為獨立程序。既有規格的 `aos-clean`／`aos-attend` 在此當作角色名，後續以 `aos` 子命令承接機器用途；不新增人手投件、查詢或操作指令。

每個可啟動角色的正文須列完整 argv 陣列、必填／可省選項、輸入輸出 fd、UID、持久輸入輸出、環境與退出語意。argv 直接 exec，不隱含 shell、字串拆詞或插值；傳複雜資料用 JSON／受控 fd，不把完整 JSON、prompt 或 key 塞 argv。只有既有 B-101 工作的明示 shell argv 才執行 shell。

單次機器 adapter 預設 stdin 讀一份 JSON 至 EOF，stdout 寫一份契約結果，stderr 寫有界診斷；JSON 發送後的換行只屬傳輸，A-401 工具 arguments 的 canonical stdin **不加換行**。常駐服務預設 stdin 關閉、協議走指定 socket／spool、stdout 不混協議與 log。工具 stdin／stdout／stderr 依 B-101／A-401／A-403：stdin 是 arguments，stdout 是不可信工具結果，stderr 是診斷；supervisor 的可信 ExecResult 走另外的回報通道。二進位 blob 導出使用專用資料 fd，不混入 JSON stdout。

aos 自有環境變數統一使用 `AOS_` 前綴，各篇必列名字、型別、預設、讀取者與能否往 child 傳；環境不是 UID、准入、claim 或 owner 的授權來源。argv 明列選項優先於同義的已允許環境變數，兩者皆缺且必填就拒絕啟動，不能猜部署值。工作環境沿 B-102 的乾淨集合及 HOME／TMPDIR 保護；不改名既有 PATH／HOME／TMPDIR／LANG，也不禁止工具自己的合法 env key。不得把服務 key、loader env 或控制 socket 傳給 agent／工具；LLM endpoint 的憑證引用由專用服務在可信設定中解析。

驗收：Given argv 含空白參數且 stderr 有診斷，When 啟動 adapter／工具，Then 參數不被重新拆詞、stdout 仍符合各自契約；agent 不因環境自稱 owner 而換 UID，也讀不到代發 key。

## P-008．程式結束碼〔建議預設，未拍板〕

下表適用 aos 的機器包裝程式本身；不是 RPC code，也不是 run 終局。若 RPC adapter 已完整傳回合法的 JSON-RPC error，仍屬一次完成的協議交換，退出 0；呼叫方必須讀 envelope。沒有得到持久收件／提交確認時，任何退出碼都不能拿來猜操作未發生。

| 結束碼 | 包裝程式本身的意義 |
|---|---|
| `0` | 本次交換及約定輸出完成；常駐服務則是按停機契約正常結束 |
| `125` | 自身執行、I/O、輸出發布或內部失敗，未能完成約定輸出；沿 proto5 aos-exec 的自身失敗碼 |
| `2` | argv／部署設定／啟動前輸入不合法，尚未進入正常交換 |
| 其餘 | 首版不分配新的 aos 包裝器意義；被信號終止由父程序的 wait 狀態判斷，不解析 shell 的 `128+signal` 猜測 |

工具的原 exit code（含 1、2、7、125 等）與 signal **只按 B-103 保存在 ExecResult**，不拿工具碼當 runner／supervisor 自身碼。工具 exit 7 且回報已完整持久發布時，包裝程式可 exit 0，ExecResult 仍 failed／exit、exit_code=7；反之工具 exit 0 而回報丟失，不能由 wrapper 退出狀態宣稱 attempt 成功。spawn_error、timeout、取消、OOM、截斷與 unknown 都保留 B-103 具體原因。daemon 停機未清空／逾時依 B-604 非零，另保留未清空 attempts 證據。

驗收：Given 工具 exit 7、spawn 失敗、包裝器寫結果失敗各一例，When 上層讀回，Then 能分辨子程式結果與包裝器自身失敗，沒有靠 exit 0 宣告 run 成功。

## P-009．Schema、範例與交付規則〔主編補〕

後續 schema 放 `proto6/spec/protocol/schemas/*.schema.json`，採 JSON Schema 2020-12、`$schema` 指向該版；同份文件可用 `$defs` 分拆型別，跨檔使用相對 `$ref`，不依賴運行時上網。協議 schema 可以使用完整 2020-12；這不放寬 A-401 **被嵌入的工具 input_schema／result_schema** keyword 白名單，需另有 meta-schema 及登記驗證。未知欄位關閉沿 C-01，擴充只在明列 extensions；schema 的 default 只是說明，實作仍須按契約套預設。

所有 schema 檔名以分工前綴命名，基本型別只在 `control-common.schema.json` 的 `$defs` 定義；公開片段固定為 `#/$defs/ID`、`#/$defs/BlobRef`、`#/$defs/Error`、`#/$defs/Outcome`、`#/$defs/Run`、`#/$defs/Job`、`#/$defs/Attempt`，作者不能各自更名。其他作者以 `$ref` 使用，不各抄 ID、BlobRef、Error、Outcome、Run、Job、Attempt。檔案名以 kebab-case，`version:1` 為資料內版本，不在首版檔名另加 v1。schema 不自定網路 `$id` 網域。

範例放 `proto6/spec/protocol/examples/<文件名不含.md>/`，命名 `<subject>.<case>.valid.json` 或 `<subject>.<case>.invalid.json`；RPC 範例區分原 envelope 與 `.file` 持久包裝情境。每份正文解釋 invalid 的拒絕原因；正例含最小成功、結構化失敗、同 ID 重送，涉及程序者另含 unknown／截斷，不能只列愉快路徑。第一階段不先建立空 schema 或看似已可用的範例。

驗證要分三層：JSON 解析／schema、owner 與狀態語意、崩潰後持久恢復。schema 通過不代表授權通過、引用存在、程序清空或已提交；各篇須沿原 Given／When／Then 補上實際 wire 例子。後續每人只改自己一份正文、所屬 schema 及 examples 子目錄；共用 README 與既有正本的變更交整合者，不互改別人的檔案。

驗收：Given 兩份文件都引用 BlobRef，When 對照 schema，Then 使用同一 `$ref`；語法合法但跨 owner 或 stale generation 的例子仍由語意驗證拒絕。

## P-010．沿用 proto5 與明確差異〔主編補〕

參照 [proto5 規格入口](../../../proto5/spec/README.md) 的 inst-posix、directives、aos-exec、cpu、aos-llm、kernel：保留已驗證的**請求丟到對應主人資料夾、requests／responses 同名配對、先寫完暫存再原子公布、門鈴只提示、直接 argv 與 stdin JSON、包裝器失敗和子程式結果分開**。proto6 是新寫，這些是可沿用的交接方式，不宣稱 wire 完全相容。

差異來自既有 proto6 條款：C-01／B-501 收緊版本、ID 與未知欄位，不搬入可省 id 的 notification、數字 id、忽略未知欄位或 `_metainfo`；B-101／B-102 不搬 `$ref` 指示詞展開、redirect 或特權代開路徑。proto5 cpu 的公布是暫存檔 → link → unlink；proto6 按 B-402 改為同 filesystem rename 並明定不覆蓋、fsync、DB 與 spool 修復，理由是閉合崩潰後的持久交接，而非聲稱 proto5 原本已採 rename 耐久流程；B-503／C-05 把收件、結果、消費分開，讀走回覆不能等同刪除完成結果。B-601 取消常駐 CPU worker，B-202 以 cgroup 清空判收尾，不能把舊 process group 等待時間直接搬來。S-204 用帳本序號，不按檔名排序。LLM 仍集中代發，但 S-301 改為專用服務 UID 持 key，不能把原本可繼承的憑證 env 帶給 agent；S-302／S-303 的入場與重試由控制層負責。

驗收：Given 以 proto5 格式作範本，When 完成任一協議正文，Then 逐項指出保留的 wire 形狀與上述必要改動，不因「沿用」恢復已取消的權限、ACK 或 worker 行為。

## P-011．待決：不能靠格式代替的決定〔主編補；建議均未拍板〕

以下是後續格式的缺口，不阻止五位作者先寫已確定部分；草稿對受阻部分標「待決」，不得先上線一個猜出的入口。

1. **工具直接投 LLM／後續 job 的入口。** A-402／S-301 已允許工具走指定收件處，但 B-502 methods 只有 tick 的 checkpoint.commit 能提交 JobDraft，未定一般工具如何綁 run、預算、授權與重送。建議由同一 B-501 入口接受受限投件、可信解析 owner／run，與 tick 提案共用准入；是否新增 method、可否建立非 LLM 的後續 job 須先定，不能擅加 `llm.submit`／`job.submit`。由 llm 與 control-rpc 作者共同提案，檔案仍各自持有。
2. **設定發布及管理登記的機器入口。** A-101／A-102 已定 bundle 與下一 tick 生效，B-302 已定 registry/profile，尚未定提出更新者、版本引用解析表與發布請求形狀。建議先採管理者專用本機配置發布 adapter，驗完整引用後原子切指標；不自增公開管理 RPC，也不把普通 agent env 當授權。是否另允許 owner 更新、登記改版採排空或 attempt 邊界切換，需明列部署選擇。
3. **LLM 內容與 provider 的具體映射。** S-301 已定 payload 及 endpoint/scope，A-404 尚未定 messages_ref 的完整 wire 內容、模型原始回覆／usage 的共通 shape、支援哪個 provider API／估算器版本。建議沿 proto5 已有 messages 及一次 client 結果格式為候選，外包 attempt／Outcome 與版本化 usage；由 llm.md 列明差異，不能默認所有 provider 同格式或擅擴充串流。
4. **continuation 與查詢 phase 的對照。** A-502 只定 continuation_ref，A-503 要由語意位置推導 think／act／wait；其內容及控制查詢能讀哪部分還未定。建議由 agent-state.md 定最小、版本化語意續接資料，保存無法從帳本重建的決策及來源，查詢仍為投影；不恢復已刪除的可寫 phase／pending／cursor 副本。若新增語意狀態，須先確認再封 schema。
5. **S-405 `_control` 與完成通知的命名。** C-01 允許 agent_id=`_control`，S-405 同名作控制目錄，存在真碰撞；done 未定是否保留 agent 子目錄及解除欄位名稱。建議為 attention 投影保留控制命名空間並明定一般 agent 的無碰撞映射；done 保留 owner／item 層次，附 `resolved_at_ms` 及結構化處置。不能在本篇偷偷禁用全域合法 ID；storage 作者提出選項，待裁定後補 schema。
6. **helper 讀可信登記的同步方式。** B-102 要從控制帳本查固定描述，B-303 又限制 helper 只查登記、不寫帳本；傳遞何種可信映射、如何核對 registry_revision 尚未定。建議由 daemon 輸出管理者保護的版本化唯讀 launch 材料，helper 只核對白名單欄位與 revision；不能為方便讓它解析 agent 工作或開任意路徑。execution 作者定格式前須明列信任來源與更新責任。
7. **掛勾識別、skip_tick 與服務內部入口。** A-506 stdin 的 attempt_id 可 null，且一次 tick 可有多個掛勾，不能直接拿 tick attempt_id 當各次執行的去重／診斷鍵；pre skip_tick 後工作仍 ready，如何不立即重跑成忙迴圈尚未定。A-506 又把 agent pre／post 計入 tick deadline，B-101 則從放行起計，總 deadline 起點及 post 能用的剩餘時間也須對齊，不能另起 timeout 延長 claim。建議由控制端配獨立 hook 執行識別，保留與原 claim 的關係；skip_tick 留有界退避或等待明確事件的原因，但採哪種喚醒政策須確認。系統掛勾、aos-clean 領候選／回報完成所需可信內部通道也須明列服務 UID 與授權，不擅加公開 RPC。
8. **attention 本身無法落盤的回報與清理範圍。** S-405 要把控制滿碟也寫進 attention_dir，但同卷滿碟／EIO 可能連通知都寫不出。建議沿 B-404 保留容量保存最小證據、恢復後依帳本補檔；是否另允許獨立通知位置及無法持久時的退路須明列，不能承諾當下必有檔。`_control` 的 done 通知不屬任何 agent；建議由管理者呼叫 aos-clean 時的明確控制範圍處理，不能自行加全域定時清理或假稱某個 agent tick 會掃到。

**09-29 整合者暫定（照上列建議採用，均為建議預設、未拍板，使用者可推翻）：**
1. 工具要用 LLM 時，照 proto5 現況把請求丟進 LLM 收件處（每 UID 獨立 spool），owner／run 由可信通道從該工具的 attempt 推出，算進該 run 預算、走同一准入；這是內部交接，不算公開 RPC method。工具不能藉此建立非 LLM 的後續 job。格式由 llm.md 定，control-rpc.md 只列交界。
2. 〔使用者方向 2026-09-29〕改 agent 設定就是**手打指令或直接改設定檔**，沒有另外的「更新設定」機制。誰能改只看檔案權限：管理者能改；要讓 agent 自己改，就開放它對該設定檔的寫權限，之後頂多包成工具。控制端在下一次 tick 開始時讀設定來源、驗證完整引用，通過才固化成新 bundle 換上（A-102）；驗證不過就沿用舊 bundle 並寫一件 attention。
3. LLM 內容以 proto5 的 messages 與一次呼叫結果格式為起點，首版 provider 為 OpenAI 相容 chat completions；差異在 llm.md 列明。
4. continuation 由 agent-state.md 定一份最小、有版本的格式，只存帳本推不回的語意位置與決策；phase 查詢仍是推導。
5. attention 目錄分 `open/agents/<agent_id>/`、`open/control/`，done 同構；解除時附 `resolved_at_ms` 與結構化 `resolution`（動作、操作者、request_id）。不動 C-01 的 ID 規則。
6. helper 讀 daemon 輸出、管理者保護的版本化唯讀 launch 登記快照，只核對白名單欄位與 revision。
7. 每次掛勾執行由控制端配獨立 `hook_run_id` 並記下所屬 claim；總 deadline 從取得 claim 起算，post 只能用剩餘時間；pre `skip_tick` 後以有界退避（例如 60 秒起倍增、上限 15 分鐘）或等到下一個新事件才再排，不成忙迴圈；系統掛勾與 aos-clean 走控制服務 UID 的內部通道，不加公開 RPC。
8. 控制端滿碟時 attention 檔可能寫不出，靠 B-404 保留容量存最小證據、恢復後補檔；`control/` 的 done 由管理者手動跑 aos-clean 清。

**既有延後項目，並非本輪要求再裁定：** 新訊息屬哪個 run、外牆 profile、needs_attention 是否提供可選 resume、各容量及時限仍沿既有條款與裁定。建議 schema 表達已存在的可配置值／支援能力，範例標明採用哪個預設；不因五份文件共用同一個範例便把它變硬規定。設定更新下一 tick 生效、中央持 key、重啟全殺與可選 quota 已有裁定，不重開為待決。

驗收：Given methods 尚無工具投件入口，When 撰寫 llm schema，Then 只完成已准入派送／結果等確定部分，待決入口不出現在「首版可呼叫」清單。

## P-012．五份平行分工表〔主編補〕

下表檔名均相對 `proto6/spec/protocol/`；schema 均在 `schemas/`，範例依 P-009 放作者自己的子目錄。**恰五份正文**；每列是一位作者的唯一寫入範圍，P 編號保留不同區段避免互撞。共用定義由第 1 位持有，其他四位只引用；可先對著下表約定的檔名寫相對 `$ref`，整合時再一次驗證，不需等待另一人改同一檔。

| 文件／條款區段 | 涵蓋的交接點與程式 | 唯一負責產出的 schema 檔 | 依據與交界 |
|---|---|---|---|
| **`control-rpc.md`**／P-100～P-199 | 控制 daemon 的機器啟動、認證入口、每 UID spool 與 socket adapter、持久收據／錯誤、控制意圖及查詢投影；agent.submit/get、run.get/pause/resume/cancel/resolve/outputs、attempt.get/cancel 共 10 個公開 method 的 params／result；run 預算／ready／due／排程游標／計量／取消與處置紀錄；aos-attend 讀 attention → 查權威狀態 → 呼叫既有 RPC／aos-clean 的機器交接、處理表與動作稽核，危險處置授權沿 S-405，不在本輪設計互動介面。明列 result.ack 延後、不可呼叫。 | `control-common.schema.json`（基本型別、Error、BlobRef、Outcome、Run、Job、Attempt）；`control-rpc.schema.json`（通用 request／response）；`control-handoff.schema.json`（持久 RPC 包裝）；`control-methods.schema.json`（上述 10 methods）；`control-config.schema.json`（daemon、准入／容量／停機設定）；`control-state.schema.json`（ready／due、預算、控制意圖、查詢及最小量測紀錄）；`control-attention-policy.schema.json`；`control-attention-action.schema.json`（處理表及動作稽核） | C-01～C-04、C-06；B-401／B-402、B-501～B-504、B-603／B-604；A-201～A-203、A-505；S-101～S-104、S-201～S-204、S-306、S-401～S-405、A-506；methods.json。system hooks 容器放 control-config，掛勾項目引用第 3 份 schema。RPC envelope 不重定 checkpoint.commit 的 payload；run.outputs 引用第 3 份 Output。不要把 SQLite 實體 layout 當 wire 契約。 |
| **`execution.md`**／P-200～P-299 | 控制 daemon → root helper（SO_PEERCRED、可信 launch request／reply、fd）；helper → 固定降權 runner（argv、env、fd、放行／exec 錯誤通道）；runner → 工具 stdin；supervisor → 控制端可信 ExecResult／清理與取消證據；重啟的程序識別／閘門紀錄、停用退役清單；ExecTemplate 轉固定工作描述；A-506 的系統／agent 掛勾實際啟動、UID／資源域、deadline、claim 釋放前收尾與重啟全殺。 | `execution-work.schema.json`；`execution-template.schema.json`；`execution-result.schema.json`；`execution-launch.schema.json`（請求／回覆／閘門／exec 錯誤）；`execution-observation.schema.json`（程序識別、取消、清理、恢復及退役證據）；`execution-profile.schema.json`；`execution-registry.schema.json` | B-101～B-103、B-201～B-204、B-301～B-304、B-602～B-604；C-02／C-03；A-401／A-402／A-506；裁定 5～8、10。掛勾輸出不得當成工具結果或 tick Proposal；識別缺口沿 P-011。profile／registry 為可信部署輸入；實際管理更新入口受 P-011 限制。公開 attempt.cancel/get 歸第 1 份；其底下可信程序回報歸本份。 |
| **`agent-state.md`**／P-300～P-399 | 控制端 → 短命 tick runner 的 claim、固定 bundle、唯讀帳本快照與內容 fd；tick → blob 導入／checkpoint.commit／提案收據；輸入、history、notes／summary 引用、context 材料、語意 checkpoint／continuation、Proposal／append、Output；設定 bundle／工具 manifest、tool call、OutcomeAdapter 的模型可見結果封套；A-506 掛勾登記、pre／post stdin、執行結果紀錄及 tick_outcome，agent bundle 的掛勾引用。 | `agent-config.schema.json`（bundle／context policy／設定換版紀錄）；`agent-tools.schema.json`（manifest／tool call／工具 schema 子集）；`agent-input.schema.json`；`agent-content.schema.json`（history／notes／context 與來源）；`agent-output.schema.json`；`agent-tick.schema.json`（claim／唯讀輸入）；`agent-checkpoint.schema.json`；`agent-proposal.schema.json`（Proposal／JobDraft／append）；`agent-commit.schema.json`（checkpoint.commit params／result）；`agent-tool-outcome.schema.json`；`agent-hook-registration.schema.json`；`agent-hook-input.schema.json`；`agent-hook-result.schema.json` | C-05；B-401／B-403、B-602；A-101～A-103、A-201～A-203、A-301～A-303、A-401～A-404、A-501～A-506；S-101／S-103。只擁有 checkpoint.commit 這 1 個 method 的 payload，外層引用 control-rpc；ExecTemplate／ExecResult 引用第 2 份；LLM provider 內容引用第 4 份；blob fd 交付引用第 5 份。不造第二個派工／消費權威。 |
| **`llm.md`**／P-400～P-499 | 控制端 → 專用服務 UID 的 LLM 代發服務（機器啟動、已准入請求／送出閘門／取消）；服務 → 單次 HTTP client／provider adapter；服務 → 控制端的可信結果、原始回覆／usage、retry-after／cooldown／uncertain 證據；endpoint/model/scope 與憑證引用設定、reservation、run 用量結算。工具投件入口列 P-011，不自行加公開 method。 | `llm-request.schema.json`；`llm-messages.schema.json`；`llm-dispatch.schema.json`（派送／sent 放行／取消與確認）；`llm-result.schema.json`；`llm-usage.schema.json`；`llm-config.schema.json`（endpoint／model／scope、adapter 版本及憑證引用）；`llm-reservation.schema.json`（held／sent／settled／uncertain／released 及退避證據） | A-302、A-402／A-404；S-301～S-306；C-03／C-04；B-402／B-503、B-603；裁定 9、附 429。憑證值不進任何 agent 可讀 schema。只結算一次、sent 前持久證據、429 有限重試與 stream=false 均沿正本；不要由服務自訂另一套排程。 |
| **`storage.md`**／P-500～P-599 | 非特權 blob import／export adapter 的機器 argv、認證、普通檔 fd／二進位資料流、快照與 BlobRef；home 候選 → 受管內容庫 → 唯讀 fd 的跨 UID 交付；檔案與 DB 交接修復索引；S-405 attention open／done 通知、重建、解除資料；aos-clean 的機器啟動、由系統 post 掛勾或管理入口呼叫、向控制 writer 領清理／封存候選、引用檢查及完成收據；重跑去重，不直接成為第二個 SQLite writer。 | `storage-blob-transfer.schema.json`（import／export metadata、成功／錯誤）；`storage-index.schema.json`（發布／修復索引及導出引用，不是 SQLite 全庫）；`storage-attention.schema.json`（open／done，待 P-011 命名裁定）；`storage-retention.schema.json`（留存設定、封存清單與 tombstone）；`storage-clean-request.schema.json`；`storage-clean-candidates.schema.json`；`storage-clean-result.schema.json`（有限批次、候選識別與完成回報） | C-03／C-06；B-304、B-401～B-404、B-505；A-303／A-506；S-404／S-405；裁定第二批及補充的待辦資料夾、掛勾與獨立清理程式。BlobRef 引用第 1 份；只管材料保存，不發 accepted、不替第 3 份提交 checkpoint，也不因刪 attention 檔解除屏障；控制端自身滿碟及 _control 留存缺口依 P-011，不承諾必能當下發布檔案。 |

跨檔引用方向固定：共同型別 → 各篇；execution 的 template／result → agent-state；agent-state 的 Output → control 的 run.outputs；llm 的 provider 內容 → agent context；storage 的資料交付 → 其他各篇。JSON Schema 可相互引用已列檔案，不表示兩個作者可共同寫同一檔。第 1 位只定義通用 RPC envelope；第 3 位自行將 checkpoint.commit payload 與它組合，沒有要求第 1 位同步修改 methods 聚合檔。各篇引用正本 methods.json，不新增或修改該檔；待決裁定另由整合者回寫。

交付驗收：Given 五人各自完成所屬文件，When 整合，Then 10 個控制 RPC 加 checkpoint.commit 共 11 個首版 method 都有唯一 payload owner，result.ack 仍不可呼叫；root helper、tick、supervisor、LLM 代發、blob adapter、設定發布材料、hooks、aos-clean、aos-attend 與 attention 都有指令或交接規格；schema／範例無同檔競寫，所有 P-011 未決選項仍清楚可見。
