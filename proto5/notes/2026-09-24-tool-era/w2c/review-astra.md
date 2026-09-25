找到 **8 項必修**。其中鎖的時間來源、鎖名落檔，以及申請問句的 shell 引號問題優先處理。

僅審 `12d67d4..HEAD -- proto5`，未改檔、未啟動模型或服務。233 項指定單元測試全部因唯讀沙箱無法建立暫存目錄而停在 setup；下述關鍵案例另以不寫檔的記憶體替身重現。

**必修**

- **M1｜鎖的到期時間由申請者控制。**  
  檔／函式：[aos_team_lock.py:88](../../../lib/aos_team_lock.py)，`on_lock`、`_expired`。  
  **觸發：** worker-2 在自己的 outbox 寫 `at: "2099-01-01T00:00:00+00:00"`，就能把 worker-1 尚未到期的鎖判成過期，搶走或放掉；新鎖還會延續到 2099 年，繞過 86400 秒上限。已重現。正常申請若排隊太久，也可能收到已過期的成功回信。  
  **改法：** 取得、續租與到期判斷都用郵差的可信現在時間；`req.at` 僅作申請紀錄。冪等重跑仍回傳第一次保存的結果。

- **M2｜合法鎖名不一定能落檔，且 `ls` 會漏列。**  
  檔／函式：[aos_team_lock.py:86](../../../lib/aos_team_lock.py)，`_check_lock_name`、`on_lock`、`cmd_lock`；`Layout.lock`。  
  **觸發：** 規範範例 `docs/WORKFLOWS.md` 通過驗證，但只建立 `locks/`，沒有 `locks/docs/`，寫入會失敗。`.hidden` 能建立，卻被 `json_files` 排除；即使補建子目錄，非遞迴的 `ls` 仍漏列。`\w` 也接受中文，200 個中文字會形成超過常見 255-byte 限制的檔名。  
  **改法：** 建議把識別碼映射成固定長度、非隱藏的平面檔名，原名保存在 JSON。若保留目錄形式，須一起處理父目錄、遞迴列舉、隱藏名稱、位元組長度與路徑別名。

- **M3｜提供給人的指令直接嵌入未轉義的模型文字。**  
  檔／函式：[persona_propose:20](../../../tools/task/persona_propose) 與 `access_request.main`。  
  **觸發：** 提案文字含 `$(id)`，問句會生成 `persona append … "...$(id)..."`；人替換家目錄並照抄時，shell 會先執行替換。一般 `$變數`、雙引號也會使寫入內容失真。`access_request` 的 `name` 則完全未引用，也未驗掛載名稱。  
  **改法：** 用 `shlex.quote`／`shlex.join` 組指令，驗證 mount 名稱，必要時用 `--` 結束選項。人同意人格文字，不等於授權執行文字內的 shell 語法。

- **M4｜persona 指令與 runtime 對 `system` 的解析不一致。**  
  檔／函式：[aos_agent_persona.py:17](../../../lib/aos_agent_persona.py)，`_system_path`。  
  **觸發：** 合法設定 `system: {"$env":"PERSONA_PATH"}`，runtime 會解析到自訂人格檔，新指令卻把物件當成沒設定，讀寫預設 `prompts/system.json`，印成功但實際人格不變。已重現。  
  **改法：** 共用 runtime 的 `Document`／`Context`／`resolve_field` 路徑解析；明寫但無效的值應報錯，不應退回預設。

- **M5｜人的 `task show` 漏改審查編號。**  
  檔／函式：[aos_team_task_cli.py:41](../../../lib/aos_team_task_cli.py)，`show`。  
  **觸發：** 子單 `review_of.indices=[1,3]`，`board`、派工信及回報都用 1、3，人的 `task show` 卻仍顯示 0、1；完成後同一畫面中的審查結果又是 1、3。已重現，違反這次新增的對外一致編號契約。  
  **改法：** 子單顯示採用 `review_of.indices`，一般單維持 `enumerate`，並補非連續編號案例。

- **M6｜G 的文件宣稱涵蓋心跳，實際沒有。**  
  檔／函式：[tools/task/README.md:25](../../../tools/task/README.md)、`handoff` 註解；相關路徑是 `aos_team_beat.write_request`。  
  **觸發：** 例行工作要求「把 README.md 改寫成白話」，心跳直接產生 handoff 申請，完全不經工具的 `_wants_auto_lint`，因此不會補 lint。  
  **改法：** 最小修正是把文件與註解限縮成「經 handoff 工具送出的申請」。若確實要求心跳也涵蓋，才抽共用規則接入該路徑。

- **M7｜`access_request` 對模型宣告能申請網路，實際無此介面。**  
  檔／函式：[task.json:118](../../../tools/task/task.json)、`access_request.main`。  
  **觸發：** 模型照 description 要求開網路，但 schema 強制填掛載欄位，工具也只生成 `access set` 問句。  
  **改法：** 本輪若只做資料夾申請，移除 description／docstring 的網路承諾，指引網路需求走 `ask_human`；否則補明確的網路申請分支。

- **M8｜教程把四種申請的批准效果寫成同一種。**  
  檔／段落：[08-team.md:166](../../../tutorials/08-team.md)，〈申請〉開頭，無函式。  
  **觸發：** 讀者會以為四種都出現在 `wait ls`，且回答後還須手動套用；實際 lock 不開問題，routine 則在批准被處理後自動取得排程授權。  
  **改法：** 明列「access／persona：回答後另行套用；routine：批准後心跳生效；lock：郵差直接處理」。下方四條指令與「人批准了」輸出本身基本合理。

**建議**

- **S1｜G 應收窄觸發條件。** 已重現兩種假陽性：「不要把 README.md 改成更白話」、`goal=改寫 app.py` 搭配 `facts=參考 README.md`；英文 `Rewrite README.md for clarity` 則漏判。建議以明確的 workflows 文件工作流白名單或結構化標記觸發，goal 關鍵字只作輔助。只改成掃 `workflow` 的任意文字，仍不夠可靠。

- **S2｜模型端 `lock ls` 不必非同步。** 人的 `aos-team lock ls` 已經同步。模型可仿 `board` 讀唯讀快照，但不能把「看到空閒」當成 acquire 成功。若新增 `/work/locks`，須同步保留名稱、模板初始化、工具 config、舊家補掛載及衝突處理；沿用 B 隊既有唯讀 mount 格式即可，不需要另創 access.json 契約。

- **S3｜問句加固定前綴與明確執行者。** 建議 `[access_request][需人手動套用]`、`[persona_propose][需人手動套用]`，並寫「以下指令僅供人類在牢外執行；模型收到同意後仍須等待套用」。目前 `on_answer` 會把完整問句回送模型，正好解釋 H 中再次嘗試執行指令的現象。

- **S4｜鎖名驗證不是防留言板機制。** 200 字只限制單一名稱；任意新名稱加上 500 字 `why`，仍可承載訊息，而且到期不會刪除紀錄。若需要限制資源濫用，應另設每成員數量／速率上限與過期紀錄保留期限。修掉 M1 後，24 小時作為單次租期上限可接受；同持有者自動續租是目前明文特性，不是漏洞，也不提供公平輪替保證。

**確認沒問題的**

- **F 的兩次 `want` 檢查合理且一致**：工具先擋手誤，伺服器再把關。合法子單的 indices 本來按父單順序遞增；實測 `[1,3]` 可通過兩端，父單收到的仍是 `[1,3]`，沒有二次轉換。父單結果、history 中的 effects 與 `_results_text` 未發現舊編號假設；漏點是 M5。
- **T-pool 主要接線正確**：`_pool` 覆寫、未填回退 `tool_pool`、空值型別檢查、未知池與 kernel 保留池診斷都對得上。保留池錯誤明確指出工具的 `_pool`。相同池可能因不同設定欄位各報一次，屬診斷重複，未見因此漏查。
- **借用 `kind: ask` 可行**：access／persona 的回答確實不會自動改設定；routine 仍走既有批准路徑。
- **acquire／release 經郵差序列化合理**；鎖是合作式租約，沒有強制阻止持有者以外的人寫專案檔案。