# 主題：lisp 在 `.aos` 裡長什麼樣？

← [workshop](../README.md)

| | |
|---|---|
| **開場** | 2026-08-24 |
| **已跑輪數** | R1（各自發想）**，只跑了 5 位中的 3 位** |
| **狀態** | 中止於 R1，未收攏 |
| **已發言** | 資深工程師 / 資深架構師 / 資深研究人員 |
| **未發言** | **資深獨立維運人員 / 資深獨立軟體開發者**（使用者中止，這兩份沒有跑） |

**主題**：使用者說「C 語言的普通變數、控制流其實都沒啥必要，我們更該關注的是**做 lisp 的
概念**」。這一場問的是：那個 lisp 在 `.aos` 裡具體長什麼樣。

> ⚠ **缺兩個角度，下次續場先補**：維運（磁碟上的無窮遞迴長什麼樣、怎麼中止一個跑了三百回合的
> `func`、`.aos/k/` 會不會愈堆愈多、`ls` 一下看不看得懂）與獨立開發者（手感：「重試三次然後放棄」
> 要寫幾行 JSON、什麼情況下會乾脆寫 shell script）。現有內容只有實作／結構／理論視角。

---

## R1 想法池（不完整）

### 成形的方向

1. **三層分工：form（原始碼）／續體（做到哪）／effect（真正的 POSIX instruction）。** instruction
   只是 effect；eval 擁有 form 與續體，`inst` 只擁有 POSIX effect；control、environment、continuation、
   effect 全落盤。

2. **quote 寫成 `{"op":"quote","value":<任意 JSON>}`。** `$ref`／`$env`／`$opt` 仍然只是晚綁定，不是
   quote，兩套機制不混。只有 `{"op":"exec",...}` 這種 form 能變成 `inst.json` 的內容。

3. **一回合 ≠ 一次 reduction step。** 回合是柵欄：批次回合是 superstep（BSP 模型），一回合裡可以
   約簡多步、也可以只約簡一步。

4. **尾呼叫只換 control（expr／`c`），不增加 frame**；`func` 每輪重投自己只是排程手段，不是遞迴加深。

5. **續體檔的共同項：控制、環境、frame 堆疊、handler、狀態。** 寫法之一是落盤 CEK：
   `{"c": form, "e": bindings, "k": [frames]}`；或 `{form, kont, handlers}`；或
   `id, expr, frames, bindings, seq, status, origin`。

6. **`except` 是落盤的 condition，不是跨行程 throw。** 子行程的 `exit` 寫進結果檔 → 下一回合 eval
   把它變成 `condition{type, at, cause}` → 沿 frames 找 handler → handler 回一個處理用的 form
   （retry／skip／abort）→ 沒人處理就寫 `status: "failed"` 並保留 JSON Pointer 與來源鏈。錯誤處理也是回合制的。

7. **macro 是 form→form，發生在執行之前。** 「產生下一批 instruction」不是 macro expansion，是 effect
   （更像 term rewriting）。

8. **eval 先住 `modules/eval/`，`inst` 完全不認得 form**；`inst` 的職責不變。

9. **「不要變數」的界線：**
   > **可以沒有可變變數，不能沒有 binding。**
   閉包是 `{"code": formHash, "env": envHash}`。沒有 binding 時它只是改寫器（rewriter）；要可重用的函數
   就需要不可變的參數環境。

10. **同像性在 JSON 上不是免費的。** 「JSON 陣列＝S-expression」不成立；macro 與 eval 共用同一種 JSON
    form 才有同像性——來自兩邊讀的是同一種資料，不是長得像括號。

11. **先例**：最像落盤的 CEK machine ＋ BSP。若 form 實際上是依賴圖而非表達式樹，Petri net 可能比 CEK 更準。

### 大家問出來的問題

1. **更新續體 `k` 與投遞 `inst.tempd/` 是兩次 `rename`**——crash 落在兩者之間時，怎麼避免漏跑或重跑？
   （同「回合中途死掉的洞」，eval 版本）
2. 不要 binding 的話，參數與前一步的結果怎麼命名？
3. form 要不要進版控？（`.aos/` 整包不進 git，但 form 是原始碼）
4. 多個 eval 可以改同一個 `k` 嗎？
5. 並行的 effect 怎麼 join？
6. quote 出來的東西，誰有權把它 exec？

### 明顯的坑

- **兩次 `rename` 的原子性缺口**（上面第 1 問），唯一被指認為協定層級的問題。
- **effect 的邊界多寬、非零 exit 要不要預設變成 condition** 未定。選錯會讓每個失敗的指令都變成一次例外處理。
- **`condition` 要不要能 resume** 未定。可 resume 的 condition system（Common Lisp 那種）強大得多，但續體要存的也多得多。
- **eval 會不會升進 `core/`** 未定，現在是 module。
