← [第三波 W3-2 隊報告](README.md)｜[任務書](review-task-2.md)

## 1. 必修

- **M1｜壞外層仍會讓內層「例子」變成答案。**  
  位置：`proto5/lib/aos_llm_ask.py:105`，`parse_json()`；wrap-cli 的 `llm_table()`。  
  重現：`{"example":[{"name":"zero","flags":["--zero"],"kind":"flag","type":"boolean"}],"params":`。外層截斷後，解析器撿到 example 陣列；原 help 有 `--zero` 時，`llm_table()` 完整收下，後續會寫入提案。此外，純量字串 `"[]"` 也被誤收成陣列。  
  建議：辨識字串與容器邊界；外層 JSON 壞掉就拒收，不繼續找其內部片段。完整解析出的純量也應直接拒收。

- **M2｜`_clean()` 會刪掉摘要主體，檢查仍放行。**  
  位置：`proto5/lib/aos_agent_compact.py:512`，`_clean()`／`check_summary()`。  
  重現：圍欄外寫「修改失敗，尚未寫入；以下只是檔名與行數：」，圍欄內只有 `a.md 40`。清理後只剩檔名與數字；以包含該檔名、40 行及足夠長結果的機械摘要驗證，`check_summary()` 回 `None`。  
  建議：只有圍欄外為空、或明確符合客套話白名單才移除；不能把「短於 80 字」視為沒有實質內容。

- **M3｜科學記號溢位可繞過非有限數值檢查。**  
  位置：`proto5/lib/aos_llm_ask.py:74`，`_DECODER`；wrap-cli `check_params()`。  
  重現：`{"a":1e999}` 回傳 `{'a': inf}`。把 `1e999` 放進合法 number 選項的 `choices`，`llm_table()` 也收下；提案序列化會產生非標準 JSON 的 `Infinity`。  
  建議：加上驗證有限值的 `parse_float`，溢位時同樣丟 `_Suspicious`；參數表數值與輸出序列化也應拒絕非有限值。

- **M4｜crystal 的模型正規式仍能噴 Python 例外。**  
  位置：`proto5/lib/aos_team_crystal.py:531`，`screen_llm()`；`aos_team_format.py` 的 `validate_routes()`。  
  重現：候選含 `"do":"handoff","pattern":"a{99999999999999999999}"`，會直接噴 `OverflowError: the repetition number is too large`；現有捕捉只處理 `re.error`／`TeamError`。  
  建議：在正規式驗證層將 `OverflowError`、過深巢狀造成的 `RecursionError` 轉為 `TeamError`，讓模型候選正常列入丟棄原因。

- **M5｜`nargs='*'` 的空陣列仍會傳錯意思。**  
  位置：`proto5/lib/aos_agent_tools_wrapcli.py:1082`，產生的 `build()`。  
  重現：原程式 `add_argument('--items', nargs='*', default=['original'])`，工具輸入 `{"items":[]}` 產生空 argv，原 parser 得到 `['original']`；正確的 `--items` 應得到 `[]`。若該選項必填，則變成缺少選項而失敗。  
  建議：區分「未提供」與「明確提供空陣列」；後者對 `nargs='*'` 仍須輸出旗標，並確認後接位置參數不會被吞入。

## 2. 建議

- **S1｜help 上限測試仍依賴實際排程時間。**  
  位置：`proto5/lib/test/test_agent_tools_wrapcli.py:886`，`test_m8_help_is_bounded()`。  
  測試以實際 fork、sleep 及固定 8／10 秒斷言驗證；主機重載時可能誤紅，另開 session 的孩子也沒有測試端清理。  
  建議：保留整合測試，但補登記孩子 PID 的清理機制；期限邏輯另以可控制時鐘驗證。

## 3. 看過、沒問題的

確認了 wrap-cli 的旗標值防護、固定 nargs 長度檢查、append＋nargs 拒收、多個可變位置參數限制、help 限量讀取與最小環境、spec 頂層型別檢查、控制字元處理及套用指令 quoting；wrap-py 的一般怪形狀回覆會丟棄、套用核 SHA 且不覆蓋既有描述。compact 會機械保留摘要中的使用者行、完整比對小數並記錄失敗回覆的用量。crystal 已補正式規則路徑防護、整份例句驗證、歷史次數與任務一致性檢查、固定反例及配信可信度。未見信箱排序造成的實際測試問題：`sent[0]` 那條測試只有一封信。

四個指定測試檔共 **169 項：69 通過、100 因唯讀環境無法建立暫存目錄而出錯**，不能視為全綠。上述反例以純記憶體呼叫重現，未跑模型、daemon／kernel 或禁用端點。環境唯讀且未提供 `-o` 路徑，因此報告直接回覆，未寫檔。