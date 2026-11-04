# MN2 真 AI 學徒選單續跑報告

依序續跑 luna-1、luna-2、luna-3；每個 node 僅跑 r1。三者都以 rc=1 結束，沒有全過候選，故沒有建立 `pass-luna-K.txt`。無需 r2（僅 rc=3 才重試）。

| node | rc | 選單呼叫 | 重問（bad） | gates 輪數／失敗關 | 選單 token | 審查 token | 總 token | prompt_chars 平均／最大 | r1 秒 |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| luna-1 | 1 | 18 | 2 | 3 輪：第 1 關 ×3 | 50,479 | 0 | 50,479 | 1,867.3／4,708 | 18 |
| luna-2 | 1 | 21 | 0 | 5 輪：第 2 關 ×5 | 64,324 | 0 | 64,324 | 2,559.7／5,908 | 54 |
| luna-3 | 1 | 22 | 1 | 5 輪：第 2 關 ×5 | 68,939 | 0 | 68,939 | 2,639.1／6,773 | 61 |
| **合計** |  | **61** | **3** | **13 輪** | **183,742** | **0** | **183,742** |  | **133** |

prompt_chars 是 `log.jsonl` 中 kind=ask 或 pick 的 prompt_chars 平均與最大值。token 依各 node `budget-status.stdout` 的 `used` 計；選單 token 是 `state.json` calls 的 `used` 加總。這三份數字相等，因此帳本差額（審查 token）為 0。合計低於 400,000 上限；呼叫總數低於 120 上限。每輪 `log.jsonl` 中 gates tool 都是 rc=1，why 均為「aos-tool-gates: 候選沒過。照 issues 修好再交」；失敗關依該輪留下的 gates issues 判定。

## 各 node 狀態與修正選檔

- **luna-1**：`選單 aos-tool：停下——AI 選了出口：缺少必要資訊，請人補充。請換 --run 重走`。3 輪皆卡第 1 關，issues 為「第1關：check candidate.txt：模型那邊確定沒做成」。第 1 輪 fixfile 首次回法格式錯，重問後選主程式 `packs/mailcount/aos7_mailcount.py`；第 2 輪仍選主程式；第 3 輪 fix 選出口，沒有選檔。
- **luna-2**：`選單 aos-tool：停下——層 gates max_rounds 輪數到上限。請換 --run 重走`。5 輪皆卡第 2 關，最後 issues 指向 test import error（`from ao…`，完整訊息留在該 node `state.json`）。五輪 fix 都選測試 `packs/mailcount/tests/test_mailcount.py`；第 5 輪交件後再次進 gates 時達上限。
- **luna-3**：`選單 aos-tool：停下——層 gates max_rounds 輪數到上限。請換 --run 重走`。5 輪皆卡第 2 關，最後 issues 同樣是測試匯入失敗（`from ao…`）。五輪 fix 都選 `packs/mailcount/tests/test_mailcount.py`；第 5 輪交件後再次進 gates 時達上限。另在最初 test 層有一次回法格式錯，重問後收下。

「死在格式」計 **0 次**：共 3 次 `bad` 格式重問（luna-1 兩次、luna-3 一次），皆成功重答；沒有因第 1 關格式問題或連續不合而停下。luna-1 的第 1 關 issues 是模型那邊確定沒做成，不是候選格式錯誤。

## fix 問句與選擇觀察

一次可見的 fix 情境（luna-2）：`state.json` 的 `vars.issues` 是：

> 第2關：test packs/mailcount/tests/test_mailcount.py：ImportError: Failed to import test module: test_mailcount … test_mailcount.py 第 10 行 `from ao…`

fix 層提示「第 2 關是測試或答案錯，看訊息點名主程式還是測試，答案錯通常改主程式」，模型依明確的 test 路徑選了 `tests/test_mailcount.py`。但它在五輪都回到同一個檔案，未能修掉匯入錯誤。這表示目前 fix 問句把「看訊息點名」和「答案錯通常改主程式」放在同一句，仍把選擇責任交給模型；而 fixfile 雖給目前全文及完整規範，沒有要求先對照錯誤中的匯入行與實際模組名稱。luna-1 的 issues 只有「模型那邊確定沒做成」，沒有可供選檔的診斷；模型仍選主程式兩次，然後在第三輪選出口，顯示該摘要不足以引導有效修正。

選檔依隨後 `fixfile` 的 `file` 變數確認；log 不保存模型原始回覆全文。所有 run 都未走到三關通過，也沒有審查階段 token。
