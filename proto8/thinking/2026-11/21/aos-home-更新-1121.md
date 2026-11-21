家機 `~/aos-home` 更新到 repo `88ea321f4`：install.py、kernel.json 補思考程度、ann 照 start-api 範本換（保留 model=sol）、起樹用 sol 驗四題、關回原狀（線 top-1121-homeup）。

← [2026-11-21](README.md)｜前情：[aos-hook-fire換-1121](aos-hook-fire換-1121.md)、[llm-effort-1121](llm-effort-1121.md)、[tool-desc-瘦身-1121](tool-desc-瘦身-1121/)、[aos-agent-預設目標-1121](aos-agent-預設目標-1121.md)｜給使用者看的過程頁：`~/Desktop/aos-home更新過程-1121.html`

## 授權

使用者 11-21 當場：「可以開始改，改好後去幫我把~/aos-home更新一下，把更新過程寫成html放到桌面」「好，install.py你跑就行」。

## 做了什麼

1. 開工核對：沒有指向 `~/aos-home` 的行程（表上四隻都 `sleeping`，記的 daemon pid 已不在）；repo 工作樹乾淨，HEAD `88ea321f4`。
2. 在 proto8 跑 `python3 install.py`：30 支指令（9 C++、21 Python）、`py/` 587 檔與 12 個 C++ 函式庫進 `lib/`，清掉 22 個舊檔（含 `hook_fire`）。跑完寫 `~/.aos/scratch/top-1121-homeup/install-done`。
3. 逐檔比 `~/aos-home` 與 `templates/start-api/`（JSON 用 `json.load` 比內容）。使用者那份的 JSON 全是 `json.dumps(indent=2)` 的排版；內容上屬於他自己的只有 ann 的 `llm.json`（`model: sol`）和 kernel.json 裡範本沒有的包。其餘差異都是範本這兩天的新東西。
4. 改檔（每個先備份成 `<檔>.bak-1121b`；早上的 `kernel.json.bak-1121` 沒動），JSON 照他的縮排 2 格寫回。

| 檔 | 改了什麼 |
|---|---|
| `llm/kernel.json` | 頂層在 `endpoint` 後加 `reasoning_effort_levels`；luna、terra、sol、astra 在 `summary` 前加 `"api": "responses"`、`reasoning_efforts`；luna 的 summary 換成範本那句。其他包與鍵不動 |
| `agents/ann/loop.json` | 照範本：起停改叫 `aos-hook fire -q --agent`，多 before_run／after_run 與兩個旗標條件 |
| `agents/ann/interfaces.json` | `llm_keys` 多 `reasoning_effort` |
| `agents/ann/hooks.json` | 只差 description |
| `agents/ann/tools.json`、`brain.py`、`llm_settings.py`、`system.txt`、`README.md` | 照範本逐字抄（四支 self 工具關掉、思考程度進信、系統提示指知識庫） |
| `perm/loop.json` | 照範本（loop 層 hook 點）；權限站沒掛 |

沒改：ann `llm.json`；`env.sh`、樹根 `README.md`、`root/`、`llm/` 其餘、`perm/kernel.json`、ann `hook_points.json`（內容同範本，只差排版）。

5. `aos-hook check --agent ~/aos-home/agents/ann` → `ok: 11 points from 2 declarations, 4 hooks from 1 lists`；`grep -rl --include=loop.json -F hook_fire ~/aos-home` 沒有結果。
6. 起樹（清掉繼承的 `AOS_*`，`source env.sh`，背景 `aos-exec root`，輸出寫暫存區）；四隻都 `running`。驗完 `aos-daemon-ctl -d .stack shutdown`，根行程退出、沒有殘留行程，表上四隻回 `sleeping`。

## 驗證數字（sol，共 4 次呼叫）

| # | 問 | 答 | reasoning_effort | prompt_tokens | cached_tokens | reasoning_tokens |
|---|---|---|---|---|---|---|
| 1 | pong | pong | — | 5,962 | 0 | 0 |
| 2 | 2+3 | 5 | — | 5,983 | 5,888 | 0 |
| 3 | 7*6 | 42 | high | 6,004 | 5,888 | 0 |
| 4 | 1～1000 被 3 或 5 整除但不被 15 整除 | 401（對） | high | 6,049 | 5,888 | 28 |

- 對照：昨天同一隻 ann 的 prompt_tokens 是 12,646（工具瘦身前）。
- 第 3、4 筆 llm kernel 帳本那行有 `"reasoning_effort": "high"`；換程度後快取照中（configuration_update 的效果）。
- `llm rm reasoning_effort` 後 aos-agent 自己收掉 stack 的覆蓋檔，`llm` 只剩 `model=sol`。
- 省略：在 `.stack/procs/ann` 不設 `AOS_DAEMON`，`aos-agent ctl where` 印出 ann 的 stack、`aos-agent history ls -3` 列最後三則；在樹根不給 `-d`，`aos-agent -t ann ctl where` 報 `DaemonMissing`（設計如此）。
- 沒設 `LITELLM_KEY`，代理不帶金鑰照收。

## 替使用者做的選擇

1. JSON 照他那份的縮排 2 格寫回，不用範本的單行寫法。
2. ann 保留 `model=sol`，其餘照範本換，含 `tools.json`（ann 也變 36 支，self_llm 等四支關掉）。
3. `perm/loop.json` 沒在用也照範本換。
4. luna summary 換成範本那句。
5. ann 的 `README.md` 抄 HEAD 那份；同時有別的線在工作樹改範本那份（「40 支」改「36 支」），沒抄未交的版本。
6. ann 歷史留下這次的 4 問 4 答（第 9～16 則）。
7. 起樹輸出寫暫存區，不寫樹裡的 `root.log`。

## 沒做、留給使用者

- gpt 包要不要改成「設了程度才走 responses」（現在一律走 `/v1/responses`）。
- ann 要不要打開那四支 self 工具。
- repo 裡 `wf/temp` 兩份暫存隊員定義還指 `hook_fire`（不在 `~/aos-home`）。
