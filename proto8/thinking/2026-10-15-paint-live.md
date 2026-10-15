# 2026-10-15 畫家 demo 用 LiteLLM 真腦實跑

← [thinking](README.md)｜前一次：[LiteLLM 實跑](2026-10-15-litellm-live.md)｜demo：[demo/paint](../demo/paint/README.md)

**原文**：使用者 10-15 要用本機已開的 LiteLLM proxy 把畫家 demo 的真腦路徑實跑一遍，確認行為跟 README 一致；demo 自己的設定問題就修，lib 層的只記錄。

**端點**：`http://localhost:4000/v1`（`/v1/models` 活著），腦設定用現成的 `demo/fsm/brains/litellm.json`（`chatgpt-gpt-6-luna-nothink`，不帶金鑰）。指令：`python3 proto8/demo/paint/run.py brains/litellm.json --keep`（要寫 `brains/litellm.json`，只寫 `litellm.json` 找不到）。

**結果**：全部跟 README 說的一致，沒有要修的 demo 設定。

| 情境 | 結果 | 耗時 |
|---|---|---|
| 叫畫家「幫我畫一隻貓」 | 畫家叫 brush → 畫筆（work/1/）叫 palette（work/1/work/1/，32 毫秒）→ 回「已備好橘色、白色和黑色顏料」→ 畫家畫 ASCII 貓；loop 退 0、state done、7 拍；history＝user→assistant(tool_calls)→tool→assistant | 11.9 秒 |
| 同 frame 續聊「再畫一隻狗」 | history 到 8 則；畫筆在新的 `work/2/`、全新對話；畫家自己改問「備狗狗的顏料」；定義資料夾雜湊不變 | 10.7 秒 |
| 問不用畫畫的問題（「你好，你是誰」） | 畫家照 system.md「先叫 brush」仍叫了一次畫筆才回；回「我是 Codex，AI 編碼助手」（proxy 的 codex 後端自己的身分蓋過畫家設定） | 11.0 秒 |
| 腦連錯（模型名不存在） | think 連錯 → halted → done，loop 退 0，`ret.json` ＝ `{"error": {"code": "BrainFailed", "msg": "HttpError … 回 400 …"}}`（帶 proxy 原話）；history 只有 user 一則 | 0.7 秒 |

- frame 裡留下的東西跟 README 畫的樹一樣：畫家 frame 有 `args.taken.json`、`brain.json`、`frame.json`、`history.json`、`ret.json`、`fsm/state.json`、`loop/state.json`、`tools/brush.json`（綁定時多一步 cp 腦的那份）、`work/<n>/`。畫筆 frame（`work/1/`）有自己的 `brain.json`（工具那步 cp 進去的）、`history.json`、`ret.json`、`stdout.json`；調色盤那層只有 `args.json`、`stdout.json`。
- tool 訊息內容是整份 inst 結果 JSON（含 `id`、`code`、`pid`、`ms`、`result`），不只 result；模型照用沒問題。
- 真腦把 ASCII 畫包在 ```` ```text ```` 圍欄裡，`ret.json` 的 reply 就帶著圍欄；假腦沒有。
- 沒跑 README 的第 3 段（換腦用 fake_alt.json）：`run.py` 設計上給真腦時只跑前兩段，那段只驗假腦綁定。
- LLM 呼叫：每次叫畫家 4 次（畫家 2＋畫筆 2），完整 demo 兩輪約 8 次，加不相干問題 4 次、連錯 1 次，整個任務約 13 次。

**lib 問題（只記錄、未動）**：無新增。觀察到的 halted 退 0、錯寫進 `ret.json` 是已拍板行為（C-52）。

**demo 小觀察（未改）**：問不相干的問題也會叫畫筆，是 `system.md` 的設計（「先用 brush」），不是 bug。
