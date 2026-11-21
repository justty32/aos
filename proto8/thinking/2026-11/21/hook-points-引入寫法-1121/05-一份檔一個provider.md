他第 1 則問的「一份 hook_points.json 只能有一個 provider，是否不妥」在各候選下怎麼落：引入寫在內容裡之後，一份檔本來就會混著自己的點與引入的點，provider 這個概念可以退成想寫才寫的說明。

← [README](README.md)｜上一份 [04 新格式樣本](04-新格式樣本.md)｜下一份 [06 施工與先後](06-施工與先後.md)

## 今天 provider 擔了三件事

1. **找檔**：`interfaces.json` 的 `{"provider": 名字}` 查表換成路徑（`hook_point.py:91-96`）。
2. **標誰說的**：`said` 記 provider 與路徑，`aos-hook points` 印「aos-loop: when…」（`apps/hook/main.py:280`）、錯誤句寫是哪個 provider 跟誰打架（`hook_point.py:225`）。
3. **一份檔一個 provider**：檔頂層必填 `provider`（`:190-191`），所以一份檔只能代表一支發事件的程式。

## 各候選下

| | 找檔 | 標誰說的 | 一份檔能不能混 |
|---|---|---|---|
| 甲 `$include` 鍵 | 路徑取代名字，不用 provider | 用**檔的路徑**標（`said.path` 今天就有）；檔裡寫了 `provider` 就順便印 | 能：一份檔自己的點＋`$include` 進來的，各點仍記得來自哪份檔 |
| 乙、丙 `$ref` | 同上 | 標不了：合完不知道哪個點來自哪份 | 能，但來源丟了 |
| 丁 新指示詞 | 同上 | 標不了（`aos-directive` 貼完才交給讀者） | 能，來源丟了 |
| 戊 角括號 | 同甲 | 同甲 | 同甲 |

## 建議（是建議）

- **provider 不再是硬性**：他第 2 則定的硬性只有 id 與 input schema，provider 跟其他自由鍵一樣，想寫就寫，用來給人看「這份是誰發的」。檔頂層的 `provider` 必填那條拿掉。
- **「誰說的」改成記檔的路徑**，這樣一份檔混著多支程式的點也沒關係：例如 ann 的一份 `hook_points.json` 引入 loop 那份、再寫自己格程式的點，`aos-hook points` 會印兩種來源（loop_points.json 的與 ann 自己的）。
- **一份檔寫多支程式的點**（例如有人想把 eca 和 mcp 兩份併成一份）就不用特別支援：寫在同一份裡就好，想標清楚可以在點上寫自由鍵 `provider`；甲的讀者照樣把點級的 `provider` 印出來。這只是說明，程式不靠它。
- 同一個點在兩份裡都出現（今天 eca 跟 agent-fsm 都有 before_queue，但一隻 agent 只會引入其中一份），照舊要求說法一致；比的鍵變成 `input`、`output` 與有行為的自由鍵（看 07 第 2 題怎麼定）。
