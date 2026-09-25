← [在 `aos exec` 上做一條會動的 agent loop](../agent-loop.md)（分檔 7/24）｜所在：第 1 輪紀錄 ＞ 5. 題目那四個問題｜[上一份](06-2-真模型跑不跑得起來哪一支以及.md)｜[下一份](08-6-仍然不知道的.md)

#### ③ `aos exec` 這一層讓你手寫了幾次同樣的東西

四位各自列了清單，收斂到五、六個共同項目：

| 該收掉的東西 | 誰報的 | 重寫次數的實測 |
|---|---|---|
| **投遞（temp+rename ＋防碰撞檔名）** | 四位都報 | Carmack 1 支被 3 處用、Armstrong 1 支被 3 支呼叫、Evans 1 支 12 行 4 個呼叫點、Pike 1 支 13 行 |
| **「下一批 instruction 的 JSON 字面」** | 四位都報 | Carmack 3 份（兩種語言）、Pike 2 次（兩種語言）、Armstrong 3 次、Evans 3 次一字不差 |
| **`aos status --json`／loop 的停止條件** | 三位（Carmack、Pike、Evans） | Carmack 4 處各寫一次 `[ -f w1/DONE ]`、Pike 3 個 driver 迴圈各一次、Evans 自己實作了一個 |
| **`stdout`/`stderr`/`exit` 三件套的路徑** | 三位（Pike、Armstrong、Evans） | Pike **39 次**手打、Armstrong **6 次以上**（每筆 instruction 抄一遍） |
| **prompt／context 組裝（`emit-context`）** | 三位（Carmack、Armstrong、Evans） | Armstrong 2 次，而且「兩邊的 header 格式必須手動保持一致，**我已經在這裡打錯過一次**」 |
| **exit 傳播／「前一筆非零就別跑我」** | 兩位（Carmack、Pike） | Carmack 在兩支腳本各寫一次防禦；Pike **想寫但寫不出來**，因為沒地方寫 |
| **每支 CLI 的 adapter（抽最後一則 + 取 session id）** | 兩位（Pike、Evans） | Pike「每換一支 CLI 要新寫兩支程式」；Evans 三支各一次，三個都不一樣 |
| **相位 journal／in-flight 租約** | 一位（Armstrong） | 手寫在 `model.sh` 裡的 `phase.calling` / `phase.called` |
| **整套復原（`aos recover`）** | 一位（Armstrong） | `recover.sh` 從零手寫 |

Carmack persona 的排序：「`deliver` > `status --json`（含 loop 的停止條件）> 回合模板 > exit 傳播 > emit-context。」

Pike persona 的排序不同，他認為 `deliver` 沒那麼急（13 行誰都寫得出來），最該收的是**pipeline stage 檔名的生成**——他要的是能寫 `ctx | mdl | last | note | act | inst | put` 然後 aos 自己去配 `run/*.out`、`run/*.err`、`run/*.exit`，「**這不是語法糖**」。

Evans persona 特別指出 (C)(D) 那兩項（抽最後一則、取 session id）**沒辦法收成一支子命令**，因為它本質上是廠商差異——「但它可以收成**一份 adapter 契約 + 三份設定**」。

Armstrong persona 對第 5 項（相位 journal）的提案：「**`aos exec` 應該在 fork 之前就落盤一個 running marker，附子行程 pid。**」對第 7 項：「`aos recover` **必須內建『孤兒還活著就拒絕』**，因為那正是會付兩次錢的狀態。」

#### ④ tool call 那一段最痛的是什麼

**轉換次數四位各自數：Carmack persona 8 次、Armstrong persona 8 次、Pike persona 10 次、Evans persona 13 次。** 數字不同是因為切法不同（Evans persona 連 CLI 內部線路格式與行程邊界都算進去），但**最痛的那一步四位指的是同一個位置：模型講的參數變成 argv 的那一次轉換**。

Evans persona 把理由講得最清楚：「不是因為它難寫（一段 jq 而已），是因為**它同時是型別轉換和安全邊界，而且它失敗的時候整條 loop 會安靜地死掉**。」他讓模型送 `{"path":123}`（數字，不是字串）：

```
=== 模型送了 path:123（數字，不是字串） ===
model round exit=0
--- 投遞出去的東西長什麼樣 ---
[{"argv":["/usr/bin/wc","-w",123],"stdout":"state/tool.out",...}]

=== 下一回合：aos 要吃這份 ===
aos exec: warning: .aos/inst.tempd/217053-2.json: FieldTypeMismatch
tool round exit=0
--- .aos 現況 ---
.aos/inst.tempd/217053-2.json.bad

=== 再推一次，看 loop 是不是就這樣死了 ===
exit=0
.aos/inst.tempd/217053-2.json.bad
```

他的那段話值得原樣留著：

> 那個 `FieldTypeMismatch` **是給模型看的**，但它去了 stderr。
>
> 模型永遠不會知道自己的參數被拒絕，所以它永遠沒機會改。

對比他自己的 `nuke_everything` 那次——那次拒絕發生在**投遞之前**（在他的腳本裡），錯誤被寫成一則 `[tool]` 餵回模型，模型下一回合就修正了。「**同樣是『模型講錯話』，在投遞前被擋 = loop 自我修復；在投遞後被擋 = loop 靜默死亡。這條線就是 `aos agent` 該站的位置。**」

Pike persona 指的是同一步，痛點不同——那一步是他的安全邊界，而他手上只有字串（見坑的總表裡的 `/usr/bin/id`）。他的第二痛是模型輸出的線上格式：`act` 用 `split(" ")` 拆參數，「**兩個參數就沒救了**，我得自己發明引號規則。JSON 進、JSON 出，中間我硬塞了一個沒有語法的文字協定，只因為那是模型最容易講對的東西」。

Carmack persona 指的也是同一步，他的痛是**符號撞名**：instruction 沒有 shell，所以 `write_file(path, text)` 這種最普通的工具必須寫成：

```json
"write_file": {"argv":["/bin/sh","-c","printf '%s\\n' \"$2\" > \"$1\"","sh","$1","$2"]}
```

「這一行裡的 `"$1"`／`"$2"` 出現了**兩種完全不同的意思**：模板裡的是**我的**佔位符（要被模型參數取代），`-c` 字串裡的是 **sh 的**位置參數（絕對不能被取代）。這兩者長得一模一樣，靠的是我的取代函式只認 `re.fullmatch(r"\$(\d+)", slot)` 才沒有炸掉。**這是個等著咬人的陷阱，而它的根源是「模型的參數」與「shell 的參數」被迫共用同一種記法。任何一個工具需要 redirect、pipe、glob，都會掉進這個坑。**」

Armstrong persona 是唯一指向**回程**的：他的最痛是第 7 步，工具結果變成塞進 prompt 的純文字。「去程有 schema，回程只有字串拼接。」他的第二痛是第 2 步：「codex 沒有原生的 tool-call 事件給我用（它的 tool 是它自己的 shell，不是我的），所以我只能借『最後一則訊息 + output-schema』來假裝那是一個 tool call。**能動，但語意是我硬套上去的。**」

**第二痛的位置有兩位重合：工具結果被拆成三個自己命名的檔案。** Carmack persona 與 Evans persona 都指向這裡，理由都是沒有 correlation id、沒有交易邊界、`parallel: true` 一開就壞。Evans persona 補了 exit 檔的形狀：「exit code 是『十進位字串加一個 LF』——我得 `tr -d '\n'` 才能用。」

**一個意外不痛的地方，兩位都提：模型的自由文字轉 JSON 這一步沒有想像中痛。** Carmack persona 寫了剝 markdown 圍欄 + 平衡括號掃描的 fallback，準備接 codex 亂加解釋文字，結果「實測 3 次真呼叫全部乾淨輸出一行 JSON，**fallback 一次都沒觸發**」。Armstrong persona 靠 `--output-schema` 讓這一步整個消失。**但 Evans persona 的 claude 那條是反例**——claude 照樣包 ```json 圍籬，他得寫 sed 硬剝。

---
