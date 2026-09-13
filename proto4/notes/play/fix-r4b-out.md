## 完成內容

- 四支執行器等待檔未到時改回 101，增加 `checks`、不跑下一格，並在 stderr 顯示等待路徑與次數；檔案抵達後仍於同次呼叫繼續執行。
- Lua／Python 的 `aos.b64` 統一回 `{"$b64": ...}`；`unb64` 同時接受物件與純 base64 字串。
- Lua `ms` 改讀 `/proc/uptime` 的牆鐘時間；Python／JSON 原本已使用牆鐘性質的 `time.monotonic()`。
- `aos-step-lua --help`／`-h` 正常退出 0，格式與另外兩支一致。
- Lua 會警告未列進 return 表的命名函式，略過 `_` 開頭 helper。
- JSON／Python／Lua 錯誤全文改放各自的 `<PROG>.error`，不同程式不互蓋，該格成功後刪除。
- README 已補齊等待時間線、101、reset 警告、call 選項、`<OUT>.req.json`、LLM 兩種家與 binary 規則。

Lua 載入與函式掃描拆至 [step_program.lua](/home/lorkhan/repo/simple_tools/aos/proto4-6/lua/step_program.lua)，所有程式碼與 README 均未超過 300 行。

## 修改檔案

- `proto4-4/`：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-4/README.md)、[state.janet](/home/lorkhan/repo/simple_tools/aos/proto4-4/src/state.janet)、[step.janet](/home/lorkhan/repo/simple_tools/aos/proto4-4/src/step.janet)、[test/step.janet](/home/lorkhan/repo/simple_tools/aos/proto4-4/test/step.janet)
- `proto4-6/`：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-6/README.md)、三支執行器與共用 Python/Lua library，以及五份相關測試檔。

## 測試數字

| 測試 | Baseline | 最終 |
|---|---:|---:|
| `proto4-3` unittest | 226 | 236 |
| `proto4-4` aos／step／cpu | 42／45／12 | 42／46／12 |
| `proto4-6` unittest | 71 | 77 |
| 根目錄 CTest | — | 8/8 通過 |

`proto4-3` 最終增加的 10 條來自同時進行的另一份任務；本次沒有修改 `proto4-3/`。根目錄 `cmake --build --preset default && ctest --preset default` 全綠。

沒有真打外部 LLM、沒有 commit、沒有 push、沒有開 agent；任務項目均已完成。