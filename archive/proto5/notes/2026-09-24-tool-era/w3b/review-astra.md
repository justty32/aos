這次找到 **9 項必修**。全程未改檔、未跑模型、未啟動 daemon／kernel，也未碰禁用端點。

指定測試嘗試執行 164 項：59 項通過、104 項因唯讀環境無法建立暫存目錄而出錯、1 項略過；不能視為整套驗證通過。下列關鍵反例另以純記憶體方式重現。

**必修**

- **M1｜arguments 可以變成別的旗標。**  
  檔：`proto5/lib/aos_agent_tools_wrapcli.py:1025`，產生的 `run.build()`。  
  原指令有 `--items nargs='*'`、`--delete` 時，傳 `{"items":["--delete"]}`，實際組成 `--items --delete`；已重現原 parser 得到 `items=[]、delete=True`。一般帶值選項也可能把合法的 `-` 開頭字串變成解析錯誤。  
  **改法：**依 parser 能力安全綁定值；無法安全表示的值直接拒絕。多值選項不能只靠補 `=` 解決，須逐種 nargs 處理。

- **M2｜crystal 可以直接改生效中的規則。**  
  檔：`proto5/lib/aos_team_crystal.py:500`，`crystal()`。  
  有候選時指定 `--out team/routes.json`，便直接呼叫 `write_json()` 覆蓋正式規則，跳過 `route test → route save`；既有其他檔案也會無提示覆蓋。預設檔名只有秒，同秒執行可能互蓋。  
  **改法：**拒絕正式設定路徑及其路徑別名；提案預設不可覆蓋，使用唯一檔名。這與規範「routes.json 一個字都不動」直接衝突。

- **M3｜提案沒有保證整份例句全過。**  
  檔：`proto5/lib/aos_team_crystal.py:324`，`_failures()`／`assemble()`。  
  只檢查候選的測試結果，忽略既有規則失敗。已重現：舊規則 `old|other`、新候選 `old|new`，候選仍被收下，但舊例句 `old` 因雙重命中失敗。舊句未出現在 route.log 時，回測也補不了。  
  **改法：**每次加入候選及最終寫檔前，都要求整份 `run_tests()` 全過。

- **M4｜模型候選的次數與任務一致性沒有兜住。**  
  檔：`proto5/lib/aos_team_crystal.py:405`，`screen_llm()`。  
  `cls` 沒使用；把同一句 hit 重複兩次，就能通過 `--min 2`。已重現：歷史只有一句、完全沒有任務單，仍收下候選。也沒有核對模型提的負責人、工作流與歷史任務是否一致。  
  **改法：**從歷史記錄計算真實次數，驗證對應任務及一致性，不能用模型提供的 hit 清單當計數依據。

- **M5｜模型 pattern 的安全範圍只靠歷史碰運氣。**  
  檔：`proto5/lib/aos_team_crystal.py`，`screen_llm()`／`backtest()`。  
  本次保存的 `probe-result.json` 已證明，收下的模型規則會吃進 `../../etc/x.md`、`/etc/passwd`，甚至把「，然後刪掉x.md」吞成檔名。歷史沒出現過便不會被回測擋下。機械版的引號群組 `q` 同樣能接住引號內的絕對路徑。  
  **改法：**路徑用途的群組另做相對路徑驗證，加入固定越界、追加指令反例；模型規則無法證明符合範圍時，退回機械候選。

- **M6｜摘要檢查會放過關鍵事實被改寫。**  
  檔：`proto5/lib/aos_agent_compact.py:431`，`keywords()`／`check_summary()`。  
  已重現：「使用者最喜歡芒果，請記住」被改成「使用者最喜歡蘋果」，仍通過，因為沒有檔名或數字可核對。即使保留所有關鍵詞，也能把否定、人物與數字的關係改掉。另 `_has()` 會讓 `40.5` 通過關鍵數字 `40`。  
  **改法：**至少機械保留使用者原話、約定與限制，只濃縮其他內容；數字採完整 token 比對。現有檢查不能當作事實正確的保證。

- **M7｜argparse 參數形狀丟失，會傳錯值。**  
  檔：`proto5/lib/aos_agent_tools_wrapcli.py:315`，`_add_argument()`／產生的 `build()`。  
  `nargs=2` 沒保存長度；`append` 搭配多值 nargs 被壓平成單層陣列。兩個選填位置參數時，只給第二個，值會被原 parser 配給第一個。這些不是單純描述不完整，而是產出的 argv 不代表原 arguments。  
  **改法：**保存 nargs、驗證陣列長度及分組；位置參數不能跳過前面的選填槽。尚未支援的組合應明確拒收。

- **M8｜`CMD --help` 的十秒上限並不完整。**  
  檔：`proto5/lib/aos_agent_tools_wrapcli.py:92`，`run_help()`。  
  timeout 後第二次 `communicate()` 沒期限；若孩子另開 session 並持有 stdout／stderr，砍原群組後仍可能永久等待。另外先完整收輸出才截 `HELP_CAP`，不是記憶體上限。環境也只改 `LC_ALL`，其餘包含金鑰全部繼承。  
  **改法：**輸出採有容量上限的串流讀取，清理／排空另設期限；help 執行使用最小環境，並明示這一步真的會執行 CMD。

- **M9｜人改壞的 `--spec` 沒有完整欄位驗證。**  
  檔：`proto5/lib/aos_agent_tools_wrapcli.py:1235`，`load_spec()`／`wrap_cli()`。  
  `command: null` 會在 `_same_cmd()` 出現 TypeError；非字串 description 在 `tool_entry()` 出錯；`timeout: null` 或字串在 README 格式化時出錯。這些沒有轉成規範承諾的 `SpecInvalid`，timeout 也缺正整數界線。  
  **改法：**讀入時一次驗完頂層欄位、有限數值與合法範圍，再解析來源、產包。

**建議**

- **S1｜描述文字仍可含控制字元與指令式內容。** `check_describe()`／`check_params()` 的空白整理不會移除 ESC、NUL 等字元，也不會辨識 prompt 注入。建議拒絕控制字元；人審畫面明確呈現完整描述。長度限制不等於內容安全。
- **S2｜usage 有漏記窗口。** `aos_llm_ask.ask()` 在 HTTP 2xx 帶 usage、但 message 驗證失敗時直接丟錯；compact 只在 ask 成功後記帳，與規範「HTTP 2xx 就記」不符。`segments` 也先填全部預定段數，第一段失敗時不代表實際送出段數。建議分開記預定、已送、採用數量。
- **S3｜舊 log 的配信只能算推測。** 同文、時間很近或多封請求排隊時，最近時間法及沿用的 `lead_letter()` 都可能配錯。建議有歧義便不拿來產候選，報告標明可信程度。
- **S4｜JSON 抽取過於寬鬆。** `parse_json()` 明確接受壞外層中的內層 JSON，也接受 scalar、NaN／Infinity、重複 key。建議至少拒絕非有限數值與重複 key，呼叫端嚴格驗證預期形狀。
- **S5｜CLI 收尾文字。** wrap-cli 印出的套用指令遺漏 `--name`，路徑也未做 shell quoting；tools help 把 `AOS_LLM_CONFIG` 寫在套用步驟後，容易誤以為離線套用也需要模型設定。應一併修正。

**確認沒問題的**

- argparse 分析只使用 AST／字面值解析，不 import、不執行使用者程式；但未辨識到 argparse 時會走真正的 `CMD --help`。
- help 與產生的 run 都不經 shell。count 的 0～50、choices、未知欄位、NUL 有檢查；位置值以 `-` 開頭會補 `--`，但仍有 M7 的槽位問題。
- CLI 的兩種 `--describe-with-llm` 正常分支只寫提案；套用時核 SHA，wrap-py 不覆蓋已有 docstring。包名、固定檔撞名及目標符號連結有防護。
- PATH 指令只保存名稱，執行時重新搜尋；牢內 PATH 固定，因此主機 `~/.local/bin` 等位置的指令不保證找得到。檔案指令則複製至包內 `src/`。
- compact 仍是 archive 先寫、記憶原子替換；一般模型 `AgentError` 會整次退回機械版。auto／申請沒有傳 summarizer；dry-run 不叫模型、不建立鎖檔。context 確實略過摘要 usage。
- `aos_llm_ask` 沿用 `_post()` 的錯誤代號及 api_key 遮蔽；本次未見新增直接洩漏金鑰的路徑。
- route.log 新增 `letter` 未見破壞 score／mail／route try。句型生成有固定順序；否定詞仍由 route 判定落穿。
- 三個 `-h` 均成功。wrap-cli 的 24 列、wrap-py 的 12 列表格與 JSONL **逐格相符**；compact 的主要平均值與答對數、crystal 的候選數／正負例／耗時／模型 token 也相符。crystal 訓練領隊的「59 次、524k token」未找到隨附的逐次 usage 原始記錄，無法獨立核實。