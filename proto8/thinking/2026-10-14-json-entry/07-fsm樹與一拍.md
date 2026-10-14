# 2026-10-14 aos-fsm：資料夾樹、一拍、巢狀接法

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[06-fsm](06-fsm.md)｜下一份：[08-fsm拍板與改寫](08-fsm拍板與改寫.md)

## 12. 樹、一拍、巢狀

### 12.1 資料夾樹（此例畫的是非同步 think：thinking 格是一個子 fsm 資料夾；基礎實作先做阻塞版，見 [12](12-七題回覆.md)）

```
/…/lib/agents/std/          ← 預設表資料夾：可被引用的範本，不是父類
├── agent.json              範本（整張表寫好，複製後改）
├── inst-idle.json  inst-ask.json  inst-wait.json  inst-tool.json  inst-failed.json  inst-think-sync.json（甲版，換一格就用）
└── agent_idle.py  agent_ask.py  agent_wait.py  agent_tool.py  agent_failed.py  agent_think_sync.py   ← 方法程式（N-12）
painter/                    ← 一個 agent＝一個物件
├── agent.json              {"start":"idle",
│                            "states":{"idle":"/…/std/inst-idle.json", "thinking":"think/",            ← 一格＝一個資料夾
│                                      "tool":"/…/std/inst-tool.json", "failed":"/…/std/inst-failed.json",
│                                      "error":"on-error.json"},
│                            "llm":"llm.json","system":"system.md","history":"history.json","tools":["tools/sh"],
│                            "in":"in","work":"work",
│                            "state":"state.json","ctl":"agent-ctl.json","lock":"agent.lock/","max_steps":20}
├── think/                  ← 子物件：巢狀 fsm
│   ├── inst.json           {"argv":["python3","/…/aos_fsm.py","fsm.json"],"cwd":"think"}   ← aos-inst 的資料夾找法找到它
│   ├── fsm.json            {"start":"ask","end":["tool","idle"],
│   │                        "states":{"ask":"/…/std/inst-ask.json","waiting":"/…/std/inst-wait.json"},
│   │                        "requests":"/…/brain/in/", "state":"state.json"}                     ← 子表、請求資料夾、子 state 窗
│   └── state.json          子狀態（ask／waiting）
├── loop.json               inst.argv＝aos_fsm.py、stdin＝agent.json、stdout＝steps.jsonl（append）
└── state.json  agent-ctl.json  agent.lock/  history.json  in/  tools/  work/
```

阻塞版（基礎實作先做的）：把 `"thinking": "think/"` 改成 `"thinking": "/…/std/inst-think-sync.json"`，其他不動。

### 12.2 一拍（外層 phase＝thinking，內層 phase＝ask）

loop 按 aos_inst 起外層 `aos_fsm.py`（stdin＝agent.json）→ mkdir `agent.lock/`、讀 `agent-ctl.json`、從 `state.json` 讀回 `phase`、`data` → 查 `states.thinking`＝`think/` → aos-inst 找法拿到 `think/inst.json` → 寫 `work/2-args.json`、`run(dict)`（蓋上 stdin／stdout／stderr／exit）→ 內層 fsm 起來：從 `think/state.json` 讀回 `ask` → 跑 `inst-ask.json`：組 `work/2-req.json` 與 aos-llm 的單子 `work/2-llm.json`（stdin＝req、stdout＝`2-resp.json`、exit＝`2-llm.exit`），把單子丟進請求資料夾（Maildir：先寫 tmp 再 rename 進 new/），stdout `{"next":"waiting"}` → 內層：phase＝waiting，自己這拍的 stdout 是一行 steps（沒有 `next`）→ 外層讀到沒有 `next`：留在 thinking，steps.jsonl 吐 `{"step":2,"from":"thinking","to":"thinking","code":0,"ms":200}` → 放鎖、退出 0。
之後每拍：內層 `waiting` 看 `work/2-llm.exit` 出現沒（N-12：exit 檔出現＝跑完），沒有就不吐、兩層都留著；出現就讀 `2-resp.json`、history ＋assistant，回 `{"next":"tool","data":{"calls":[…]}}`（或 `{"next":"idle"}` 並寫 `.done`）。`tool` 在內層的 `end` 名單裡 → 內層把這份 ret 原樣當自己的 stdout 最後一份、把子 phase 歸位到 `ask`、退出 0 → 外層讀到 `next: tool` → phase＝tool。

### 12.3 巢狀 fsm 的接法（三題已定，見 12.4）

- 內層每拍只跑一步就結束（它被外層當一張 inst 按，壽命就是一拍）。
- 內層沒到終點：stdout 最後一份沒有 `next`（就是它平常的 steps 那行）→ 外層留在原格。
- 內層到終點：設定裡明寫 **`end` 出口名單**；方法回的 `next` 不在自己表裡、但在 `end` 裡＝交給上層——fsm 把那份 ret 原樣當自己這拍 stdout 的最後一份（帶 `next`、`data`），子 phase 歸位到 `start`。不在表裡也不在 `end` 裡＝錯（第 2、5 題）。沒上層的 fsm 不給 `end` 就好。
- 內層有自己的 state 窗（記子狀態）；**鎖不另開**，沿用外層那把（外層已拿鎖、拍內序列化）；要單獨手動跑內層時再給它 lock。ctl 也不另開。
- 內層不吃外層的 args：它用 TARGET（`fsm.json`）拿設定，照 D-3 不讀 stdin；要外層的東西就 `$ref` 外層檔（`../agent.json#/llm`）或直接讀共用檔（`../history.json`）。
- 請求檔的內容（乙版）：建議就是那張 aos-llm 的 inst 單子本身（絕對路徑），處理者只要會 `aos-inst 它` 就行，結果落在單子說的地方（painter/work/），所以處理者是誰都無所謂。

### 12.4 巢狀三題（10-14 使用者拍板，三題全照推薦，已定）

1. **子 fsm 出口**：明寫 `end` 名單。格回傳的 `next` 不在自己表裡、但在 `end` 裡＝交給外層，子 phase 歸位 `start`。
2. **子 fsm 鎖**：不開，沿用外層那把。
3. **子 fsm 不讀外層給的 stdin**：照 D-3 從自己的 TARGET 拿設定；要外層的東西就 `$ref`。

另（[09](09-daemon套fsm.md)、[10](10-lisp組合子.md) 拍板）：沒吐 `next` 時改為「看表上靜態 next、表也沒有才留原狀態」；巢狀出口的兩次 rename 之間當掉會重發請求，**接受重跑**；各格冪等性不保證、不在規範範圍內（N-20），要顧的格自己先看 `work/N` 有沒有舊結果。
