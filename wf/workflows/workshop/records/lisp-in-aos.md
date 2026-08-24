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

> ⚠ **缺兩個角度**：維運（磁碟上的無窮遞迴長什麼樣、怎麼中止一個跑了三百回合的 `func`、
> `.aos/k/` 會不會愈堆愈多、`ls` 一下看不看得懂）與獨立開發者（手感：「重試三次然後放棄」
> 要寫幾行 JSON、什麼情況下我會乾脆寫 shell script）。**下次續場先補這兩位**——現有三份
> 全是實作／結構／理論視角，使用者體驗與可維運性完全缺席。

---

## R1 想法池（不完整）

### 成形的方向

1. **三層分工，三位講法一致**：**form（原始碼）／續體（做到哪）／effect（真正的 POSIX
   instruction）**。
   - 工程師：「`.aos` Lisp 是 form ＋ 續體 ＋ effect 收據，**instruction 只是 effect**。」
   - 架構師：「**eval 擁有 form 與續體，`inst` 只擁有 POSIX effect**。」
   - 研究人員：「control、environment、continuation、effect **全落盤**的求值機。」

2. **quote 的寫法趨同**：`{"op":"quote","value":<任意 JSON>}`。三位都強調
   **`$ref`／`$env`／`$opt` 仍然只是晚綁定，不是 quote**，兩套機制不要混。
   研究人員多加一條閘門：**只有 `{"op":"exec",...}` 這種 form 能變成 `inst.json` 的內容**。

3. **一回合 ≠ 一次 reduction step。** 這修正了前一場的說法。
   架構師：「**回合是柵欄，不等於一步**」；研究人員給了名字：**批次回合是 superstep**
   （BSP 模型）。也就是說一回合裡可以約簡多步、也可以只約簡一步，回合的意義是**同步柵欄**。

4. **尾呼叫**：三位一致——**只換 control（expr／`c`），不增加 frame**；`func` 每輪重投自己
   「只是排程手段」，不是遞迴加深。

5. **續體檔的欄位開始收斂**（三種寫法其實是同一組東西）：
   - 工程師：`id, expr, frames, bindings, seq, status, origin`
   - 架構師：`{form, kont, handlers}`
   - 研究人員（落盤 CEK）：`{"c": form, "e": bindings, "k": [frames]}`
   → 共同項是**控制、環境、frame 堆疊、handler、狀態**。

6. **`except` 是落盤的 condition，不是跨行程 throw。** 三位講法一致：
   子行程的 `exit` 寫進結果檔 → **下一回合** eval 把它變成一個
   `condition{type, at, cause}` → 沿 frames 找 handler → handler 回一個
   **處理用的 form**（retry／skip／abort）→ 沒人處理就寫 `status: "failed"` 並保留
   JSON Pointer 與來源鏈。**錯誤處理因此也是回合制的。**

7. **macro 是 form→form，發生在執行之前。** 「產生下一批 instruction」**不是** macro
   expansion——那是 effect（研究人員說更像 term rewriting）。三位一致。

8. **eval 先住 `modules/eval/`，`inst` 完全不認得 form**（架構師）。這條跟前一場的
   `core/eval` 提法不同，而且更保守——`inst` 的職責不變。

9. **使用者說「不要變數」能走多遠？研究人員給了最精確的界線：**
   > **可以沒有可變變數，不能沒有 binding。**
   閉包是 `{"code": formHash, "env": envHash}`。架構師同向：沒有 binding 時它只是一個
   **改寫器（rewriter）**；一旦要**可重用的函數**，就需要不可變的參數環境。

10. **同像性（homoiconicity）在 JSON 上不是免費的。** 研究人員直接否定「JSON 陣列＝
    S-expression」；他的說法是：**macro 與 eval 共用同一種 JSON form，才有同像性**——
    同像性來自「兩邊讀的是同一種資料」，不是來自「長得像括號」。

11. **先例定位**（研究人員）：最像**落盤的 CEK machine ＋ BSP**。他也標了一個替代可能：
    如果 form 實際上是依賴圖而非表達式樹，**Petri net 可能比 CEK 更準**。

### 大家問出來的問題

1. **最尖的一問（工程師）**：更新續體 `k` 與投遞 `inst.tempd/` 是**兩次 `rename`**——
   crash 落在兩者之間時，怎麼避免**漏跑**或**重跑**？（這跟前一場「回合中途死掉的洞」
   是同一個洞，只是換成 eval 的版本。）
2. **不要 binding 的話，參數與前一步的結果怎麼命名？**（工程師）
3. **form 要不要進版控？**（架構師）——`.aos/` 整包不進 git，但 form 是原始碼。
4. **多個 eval 可以改同一個 `k` 嗎？**（架構師）
5. **並行的 effect 怎麼 join？**（研究人員）
6. **quote 出來的東西，誰有權把它 exec？**（研究人員）

### 明顯的坑

- **兩次 `rename` 的原子性缺口**（見上面第 1 問）。這是三份發言裡唯一被明確指認為
  「協定層級」的問題。
- **effect 的邊界多寬**、**非零 exit 要不要預設變成 condition**——工程師自己標為不確定。
  預設值選錯會讓每個失敗的指令都變成一次例外處理。
- **`condition` 要不要能 resume**（架構師標為不確定）。可 resume 的 condition system
  （Common Lisp 那種）比單純的例外強大得多，但續體要存的東西也多得多。
- **eval 會不會升進 `core/`**（架構師標為不確定）——現在的答案是 module，但沒人保證它不會
  變成基礎設施。
