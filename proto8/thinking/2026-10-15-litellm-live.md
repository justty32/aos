# 2026-10-15 proto8 新架構用 LiteLLM（GPT 類）實跑

← [thinking](README.md)｜上一次真腦：[報時員實跑](2026-10-15-clerk-live.md)、[判官實跑之二](2026-10-15-judge-live2.md)｜demo：demo/fsm（已刪，見 git 歷史 aa2fec1f）｜機制：agent.md

**原文**：使用者 10-15 開了本機 LiteLLM proxy，要用它（盡量 GPT 類）實跑 proto8 新架構（定義資料夾＋frame）的 agent。

**端點**：`http://localhost:4000/v1`，proxy 沒設 master key（`~/repo/llm_proxy/litellm.yaml` 的 `master_key` 註解掉），所以腦設定**不帶** `--api-key-env`；`aos_brain_openai.py` 本來就支援從環境變數讀金鑰（`api_key_env`），不用改程式。模型挑 ChatGPT 訂閱那組：`chatgpt-gpt-6-luna-nothink`（快）、`chatgpt-gpt-6-sol`（`brain/openai.json` 原本就用它）。單問一句：luna-nothink 1.9 秒、sol-nothink 3.1 秒、astra-low 2.4 秒。每次 prompt_tokens 都約 1640（proxy 的 codex 後端自己塞了一大段系統提示），只問一句也一樣。

**新增**：`demo/fsm/brain/litellm.json`（`aos brain openai --base-url http://localhost:4000/v1 --model chatgpt-gpt-6-luna-nothink`）。

**做法**：demo 定義一個字不改。外層用 `run.py brain/litellm.json`；其餘在 scratchpad 自己開 frame（`env.json` 指回定義、frame 放 `brain.json` 綁定），報時員要也換真腦時，在 frame 放一份 `tools/clerk.json` 蓋過定義的（工具 `lookup_dir` 近的蓋遠的），裡面多一步 `cp ../../brain.json brain.json`。

**結果**（全部 loop 正常結束、`stop_on_end` 停在 end 那行）

| 情境 | 模型 | 結果 | 耗時 |
|---|---|---|---|
| fsm demo（外層真腦、clerk 假腦），兩封信 | luna-nothink／sol | 「你好」直接回；「現在幾點？」→ tool_calls clerk → tool 格 → 回 thinking → 回答；`ret.json` 對 | 9.6／9.9 秒 |
| fsm，兩層都真腦 | luna-nothink | clerk 真的叫了 clock（沒編時間）；外層照抄 | 14.8 秒（tool 那拍 5.1 秒） |
| fsm 同 frame 續跑（done 之後 inbox 再丟一封） | luna-nothink | idle 接新信、開新對話，整圈再走一次；outbox 三行 | 9.3 秒 |
| boss（kernel 的定義資料夾）直接叫，clerk 也真腦 | luna-nothink／sol | 叫 clerk 一次、回一句繁中 | 8.7／9.1 秒 |
| boss 續聊（同 frame 新 `args.json`） | luna-nothink／sol | intake 接在 history 後、沒再叫工具，用英文重述上次時間 | 2.2／2.6 秒 |
| 腦連錯（模型名不存在，proxy 回 400） | — | think 連錯 3 次 → halted → done，`ret.json` 是 `BrainFailed`（帶 proxy 原話） | 0.8 秒 |
| 平行 tool_calls（要求一次問兩個） | luna-nothink | 模型真的一次發兩個；第二個回 `Skipped`，模型回「第二個沒執行成功」，沒重叫 | 9.5 秒 |
| kernel2 agent 判官（第 1 段） | luna-nothink／sol | 判官 3 次都合法（judge_fails 0），human 先、8 封全服務完；每次問 2.6～3.8 秒 | 10.1／11.4 秒 |

- tool_calls 形狀全對（id 是 proxy 生的 `call_…`、arguments 合法 JSON 字串），全程繁體中文。比 LM Studio Qwen3-1.7B（一趟 16～20 秒、會編時間）快且穩。
- 判官：sol 第 1 次挑 L-normal、最後才補 L-low，合規則；luna 第 1 次挑了 L-low（當時快照裡有沒有 L-normal 看不到，不下定論）。

**挖到的問題**（5 題，拍板見下節）

1. **綁定不往下傳**：外層 frame 換了腦，叫出去的子 agent 還是用定義裡的腦（`demo/fsm/tools/clerk.json` 不抄腦；`demo/kernel/boss/tools/clerk.json` 抄的是 boss 定義資料夾的 `brain.json`，不是 frame 綁的）；「工具在子 frame 放什麼」牽涉 C-46 綁定語意。
2. **`kernel2/judge/ask_judge.py` 寫死 `parent` 是 judge/**，換腦只能改定義或抄一份腳本。
3. **平行 tool_calls 第二個被 `Skipped`**，GPT 類很常一次發多個；模型看到 Skipped 只會說「沒成功」，不會自己重叫。
4. **halted 時 loop 退出碼 0、state `done`**，呼叫方只能看 `ret.json` 有沒有 `error`。
5. proxy 每次多塞約 1600 prompt tokens（codex 後端），LLM kernel 的 token 額度會被放大。

## 拍板（10-15）

**原文**：使用者對上面 5 題與畫家 demo 兩個自定點「**都按照推薦**」；其中第 4 題後來被他的新原則推翻（C-52「只管自己這一層」，見 CONCEPTS），他回「**都同意。**」。

1. **換腦只換那一層**：子 agent 沿自己 frame 的 `env.json` 往上找，不看呼叫方；要換子 agent 的腦就在它的 frame 放 `brain.json`。程式本來就是這樣；boss 叫報時員用 boss 定義的腦，是 `boss/tools/clerk.json` 寫死 `cp` 定義的 brain.json，不是漏下去（agent-frame.md（已刪，見 git 歷史 aa2fec1f））。
2. **ask_judge.py 收定義資料夾當引數**（沒給＝`judge/`）；換腦＝另開資料夾放 `brain.json`＋`env.json` 指回 `judge/`。
3. **多個 tool_calls 一拍照順序跑完**，每個回對應 id；`Skipped` 拿掉（agent-lib.md（已刪，見 git 歷史 aa2fec1f））。
4. **halted 時 loop 照舊退 0**（C-52 推翻原推薦），外面看 `ret.json` 的 `error`。
5. **proxy 多塞 token**：不處理。

畫家 demo（demo/paint（已刪，見 git 歷史 aa2fec1f））：畫家想到才把畫筆當工具叫＝維持；`brain.json` 只換那一層＝維持（同 1）。
