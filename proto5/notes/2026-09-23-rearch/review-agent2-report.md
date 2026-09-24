總評：尚不能定稿；第 1 輪 12 條為 **7 條已解、5 條部分、0 條沒解**。
核心送收、once 清理與單 CPU 排程已接通；仍有吞輸入、遺失 `clear`、環境展開及退出碼相容性缺口。
本輪 C-1～C-10「全部通」的結論須修正：C-6／C-8 尚有同名檔再次投遞的窗口。
以下檔名均指 `proto5/spec/`；下層行號取已提交版本 `e2fd0d7`，不採工作樹實作補記。全程唯讀，未改檔。

## A. 驗收第 1 輪必改 12 條

1. **已解｜持久當批紀錄。** `agent.md:188`、`aos-agent.md:85`：`batch` 與門分離，每個 call 可保存工作名或本地結果；全批本地失敗也能結清。

2. **已解｜讀驗、記憶、ack、state 恢復。** `aos-agent.md:157`、`:208`：先持久 `done` 再 ack；普通 assistant 與工具批次都以固定前綴重寫，補 ack 與結清順序明確。think 的答案仍依賴受保留的 `.out`，此依據成立。

3. **已解｜送件中斷與孤兒回音。** `aos-agent.md:90`、`:112`：先記批、四步對帳後補送；已移除 boot 自動清回音的承諾。正常崩潰恢復不會換名重跑工具。

4. **已解｜取消分類與安全清檔。** `aos-agent.md:202`、`:243`：四種停止結果已分清；清檔另看 `procs`，不把 `Removed` 當完成屏障。正常 once 不會永留帳本，見 B-5。

5. **部分｜consume／input 恢復。** `aos-agent.md:50`、`:230`；`agent.md:167`：能恢復「同一份來源仍在／已消失」，但不能辨識原路徑上新投遞的另一份檔；可能無聲吞掉新輸入，見 B-2。

6. **已解｜連敗計數。** `aos-agent.md:178`、`:218`、`:237`：壞輸出算失敗；計數與結清同次寫 state，重做不重算。暫停訊號的檔案身分仍受 B-2 限制。

7. **已解｜client、名字與發布。** `aos-agent.md:30`、`:164`：三種名字、無 id 的 ack、安全前綴、tmp＋link 與禁止同步 `call()` 都已寫清楚。

8. **部分｜合法 inst 與路徑。** `aos-agent.md:126`；`agent.md:133`：重編碼及 cwd 中心已補正，但 `aos-agent.md:134`「空物件就不寫」會遺失空環境的 `clear`，見 C-1。

9. **部分｜timeout、環境與讀取邊界。** `aos-llm-call.md:83`、`:119`：執行時讀取、內外逾時責任已清楚；但 `agent.md:66` 只警告共用欄位，LLM 端卻整份解 info，仍會被非共用欄位的 `$env` 卡住，見 B-8。

10. **部分｜最小資料契約。** `agent.md:170`、`aos-agent.md:189`、`aos-llm-call.md:69`：waits、文字解碼、固定錯誤文字及 message 驗證大致齊全。`agent.md:50`、`:87` 仍允許將 history 解讀成資料夾，卻沒有可實作的寫回規則，見 C-3；其餘待猜處列 D。

11. **部分｜stop／boot 與登記。** `aos-agent.md:169`、`:250`、`:301`：保留與接續、池前提及合法命令已補；`:280` 仍把可配置的 `done_exit` 當固定 100，合法既有 K 可讓 agent 永久停排，見 B-6。

12. **已解｜拍板邊界與舊版依賴。** `agent.md:228`、`aos-agent.md:306`、`aos-llm-call.md:142`：三件拍板已落入正文，同步工具刪除代價已列，不必回翻舊版才能理解主流程。

## B. 新機制的洞與時序驗證

1. **`state.batch`＋四步判定｜可先放，正常恢復成立。**  
   位置：`aos-agent.md:90`、`:112`、`:157`。  
   時序：先記 `sent:false` → 放 request → kernel 先記 `procs/replies` 再刪原單 → 回音先發布再移除 `replies`。  
   後果：依 requests→帳本→responses 的順序查，不會漏過正常向前移動的工作；`done:null` 尚未 ack，最後一份證據不會自行消失。補 ack 後也不會再次送件。  
   建議：保留此順序；不要簡化成「原單與回音都不在就重送」。

2. **`intake`／`consuming`｜擋：恢復會吞掉第二份同名檔。**  
   位置：`aos-agent.md:50`、`:61`、`:228`；`agent.md:167`、`:211`。  
   時序：A 已接記憶並 rename 成 `.done` → 清 `intake/consuming` 前崩潰 → 生產者見原路徑消失，投遞 B → 恢復照舊紀錄 rename 原路徑。  
   後果：B 未被讀取就遭封存；恢復接回的仍是 A。生產者沒有覆寫「還沒被收的檔」，完全遵守目前限制。consume 門也會吃掉下一個同名訊號。  
   建議：保存可辨識本次消費的身分，例如每次唯一的封存目的地與完成判定；或明訂輸入／訊號名永不重用。單靠路徑及 ENOENT 不足。若保留固定 `input.json`／`continue.json`，必須支援其重用。

3. **`aw-` 前綴｜可先放，保留名前綴問題已解。**  
   位置：`aos-agent.md:18`、`:31`、`:164`。  
   時序：家名是 `ack-bob` 或 `stop-bob` → 工作名仍以 `aw-` 開頭 → 管理 request 掃描不會誤收。  
   後果：工作與 ack 命名分離；批內序號避免同批撞名。  
   建議：保留；實作仍應對衍生檔名過長回明確錯誤，不把它誤當「已送」。

4. **內外逾時｜可先放，責任已分清。**  
   位置：`aos-llm-call.md:119`；`aos-agent.md:169`。  
   時序：先排隊 → 執行後 HTTP 內圈到期退 1，或外圈到期終止工作 → agent 收回並計一次失敗。  
   後果：不會因排隊久而重送；停機期間也保留批次。兩個設定需人工配合，正文已有說明。  
   建議：保留；外圈的終止寬限依下層執行器，不能把 T 毫秒描述成「必已退出」的硬屏障。

5. **`work/` 清理｜可先放，once 不會永留 `done`。**  
   位置：`aos-agent.md:243`；`kernel.md:193`、`:253`、`:256`。  
   時序：正常 once 收回音 → 同次帳本寫入將回音放進 `replies`、移除行程；running 被 rm → 留 `discard` 與行程，直到 cpu 回音收回才移除。  
   後果：正常 once 不會因 `status=done` 永久擋住清理；`done` 留帳是反覆行程的分支。rm 的工作仍跑時也不會提前刪檔。  
   建議：保留判準；帳本讀不到就保留檔案的退讓正確。

6. **`start`／`stop`＋同池單 CPU｜要修退出碼相容性；沒有自等死鎖。**  
   位置：`aos-agent.md:110`、`:167`、`:278`、`:280`；`kernel.md:106`、`:266`。  
   時序一：tick 送 once 就退出 → kernel 將 tick 排回隊尾 → 同一工作 cpu 可以跑 once；未到回音的 tick 退 101。後果是輪流執行，不是自己等自己。  
   時序二：既有 K 設 `done_exit=101` → agent 第一次等待退 101 → kernel 優先判成完成，不再排。設 1 也會把讀驗錯當完成。  
   建議：`start` 驗證並明訂 K 的退出碼相容前提，不能只寫「done_exit＝100」。stop 的在途保留與等行程消失後才手改 state，已寫清楚。

7. **LLM 執行時讀 agent 家｜可先放，但取消後的不變量須縮限。**  
   位置：`aos-agent.md:53`、`:184`、`:218`、`:299`；`aos-llm-call.md:83`。  
   正常時序：think 排隊 → 後續 tick 只收當批，不 intake、不改記憶 → LLM 讀家；因此正常反覆 tick 不會改掉本問的記憶。  
   例外：A 被 rm 卻仍未讀家 → agent 收 `Removed`、結清並重問 B → B 在另一 cpu 先完成、改記憶 → A 才讀家。A 會看到後續記憶，但其回音已被 discard，不能據此宣稱正式記憶遭污染。  
   建議：將「think 在途不寫記憶」限定於當前未取消的批次；若要連取消殘留工作也保證輸入穩定，須等其 `procs` 消失再重問。

8. **`AOS_LLM_CONFIG`｜要修整份 info 的環境依賴。**  
   位置：`agent.md:60`、`:66`；`aos-llm-call.md:38`、`:85`。  
   config 的絕對路徑、cpu env 來源、首次建家才抄 env 的接法正確。洞在另一邊：`tick.pool={"$env":"AGENT_POOL"}` 僅 agent cpu 有 → agent 正常送件 → LLM cpu 整份解 info 時缺變數 → HTTP 尚未發出便失敗，三次後暫停。  
   建議：LLM loader 只解驗真正使用的欄位；或明訂整份 info 的指示詞依賴都須在兩端成立。只提醒五個共用欄位不要用 `$env` 不足。

## C. 跟下層契約核對

1. **錯｜空 `envs` 的省略規則改變語意。**  
   `aos-agent.md:134` 對合法 `{"$opt":"clear"}` 解得 `clear=true、envs={}`，若照「空物件就不寫」輸出，工具反而繼承 cpu 全環境。`inst-posix.md:108`、`:155`、`:249` 明定這是完全空環境。應只在「未 clear 且空物件」時省略。

2. **錯｜把預設排程政策寫成固定契約。**  
   `aos-agent.md:280` 對 `done_exit` 的敘述不符 `kernel.md:106`、`:266`，後果見 B-6。同段 `bad_after` 也應註明 0 表示關閉退件（`kernel.md:107`），不是到零次就退件。

3. **內部契約缺口｜資料夾讀取與記憶寫回衝突。**  
   `agent.md:50` 一概允許路徑指資料夾，`:87` 未限制 history；`aos-agent.md:208`、`:229` 卻要求整份記憶原子重寫。合併多個 JSON 後寫哪個檔沒有答案。最小修法是限定 history 為單一檔案；system 的資料夾語意也須排除或定義。

4. **核對通過｜引用、欄位、錯誤與回音。**  
   `aos-agent.md:32`、`:105`、`:115`、`:165`、`:178`、`:202`，以及 `aos-llm-call.md:38`：cpu §3.1／§3.3／§4.1／§5.3、kernel §1.1／§2／§3、inst-posix §3.1、directives §6 均指對。  
   `target/name/once/pool/timeout_ms`、`procs/replies[].name`、ack notification 與 `N.json`、exec 的 `code/kind/timed_out/stopped` 形狀吻合；`Stopping/Removed/Interrupted/AlreadyExists/NotFound/-32602` 用法吻合。`kind=aos` 是 result、碼為 1，不是 CLI 的 125，也未再假設它帶詳細原因。

## D. 實作者走一遍：仍得猜的地方

1. **記憶目的地。** `agent.md:50`、`:87`；`aos-agent.md:208`：history 指資料夾時，合併與寫回位置怎麼定？須先補 C-3。

2. **工具驗證的完整條件。** `agent.md:130`、`:136`：只列缺欄位，未明寫 `type="function"`、function 必須物件、name 必須非空字串；`_timeout_ms` 型別錯究竟用 `ToolInvalid` 或 `FieldTypeMismatch`？

3. **llm config 身分錯誤分界。** `aos-llm-call.md:71`：`_metainfo` 非物件、缺 `_version`，各回 `ConfigInvalid` 還是 `UnsupportedVersion`？目前只明確涵蓋部分情況。

4. **正規化順序。** `aos-llm-call.md:107`：`content:null, tool_calls:[]` 應先拿掉空陣列，再補空 content；照文字列舉順序做可能最後驗失敗。`agent.md:115` 能推導答案，宜直接寫死。

5. **`HistoryChanged` 的保證範圍。** `aos-agent.md:211`：只驗長度、已接尾巴與 call id；原前綴被等長改寫仍通過。是允許這種編輯，還是需要保存前綴身分？不能把現有檢查說成能偵測所有記憶變更。

6. **既有 `tick.json` 與新 K 不一致。** `aos-agent.md:255`、`:264`：換 K 要重建的操作規則已有，但程式是否檢查不一致、是否拒絕尚未定；照用會登記到新 K，tick 卻繼續向舊 K 送件。

7. **start／stop 逾時後怎麼找回回音。** `aos-agent.md:265`、`:276` 只要求報逾時；`kernel.md:323` 的 CLI 會印回音路徑供後續讀取、ack。wrapper 是否保留這個出口？否則使用者無從確認該次操作與清回音。

8. **日常流程的交付邊界。** `aos-agent.md:303`：手動建家→start→投 input→模型／工具→idle，核心流程可走；使用者想像的 `init`、`say`、pause／continue 指令及回話出口仍未提供。這是明列未做，不能將三份實作完成等同完整日常 CLI 已可用。

## E. 定稿前必改

1. **補消費身分，堵住同名再投遞被吞。** `aos-agent.md:50`、`:230`；`agent.md:167`：覆蓋 intake、consume 與固定 continue 訊號的重用；修改 C-6／C-8「全部通」的驗收結論。

2. **保留空環境的 `clear`。** `aos-agent.md:134`：只有未 clear 的空物件可省略，不能改變工具環境語意。

3. **補整份 info 的跨 cpu 環境契約。** `agent.md:60`、`:66`；`aos-llm-call.md:85`：縮限 LLM loader 的解驗範圍，或完整列出兩端都必須滿足的依賴。

4. **補既有 K 的退出碼相容檢查。** `aos-agent.md:254`、`:280`：阻止合法 `done_exit` 與 tick 退出碼相撞造成永久停排，並寫明 `bad_after=0` 的例外。

5. **限定可寫記憶的路徑形狀。** `agent.md:50`、`:87`；`aos-agent.md:208`：明訂單一 history 檔案，或提供完整且唯一的多檔寫回規則。