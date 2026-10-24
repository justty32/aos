# proto8/human — 給人用的 say／listen／chat

← [proto8](../README.md)｜設計與代定：[thinking 2026-10-24-say-listen](../thinking/2026-10-24-say-listen.md)｜測試 `proto8/tests/test_human.py`

讓人對一隻 fsm agent（[demo/agent-dan](../demo/README.md)、agent-bob 這類 loop＋fsm 範本）下指令、看回覆。對的是**工作區**：題目放 `$AOS_WS/new/<題名>`、答案在 `out/<題名>`（[CONVENTION P-11](../CONVENTION/02-題目stack停錯腦.md)）。Python、純標準庫、只在 Linux（讀 `/proc`）。

| 程式 | NAME |
|---|---|
| `bin/aos-say` | aos-say - 把一句話變成一道題，丟進工作區的 new/ |
| `bin/aos-listen` | aos-listen - 等 out/ 冒出答案、印出來（等一題／跟著看／快照） |
| `bin/aos-chat` | aos-chat - 跟一隻 agent 一問一答（say＋listen 串起來，可以替你跑 agent） |
| `bin/aos_human.py` | 三支共用：工作區、放題、誰在跑、trace 短行、快照 |

```
aos-say    [--ws WS] [--name 題名] [話...]                  stdout 印題名
aos-listen [--ws WS] [--timeout 秒] [--trace] 題名          等這題的答案
aos-listen [--ws WS] [--last N] [--trace] [--follow]        跟著看（像 tail -f）
aos-listen [--ws WS] --status                               誰在跑、停在哪格、各階段幾題
aos-chat   [--ws WS] [--trace] [agent 資料夾]               /status /run /trace /help /quit
```

工作區＝`--ws` ＞ `$AOS_WS` ＞ cwd（同 aos-exec）；stack＝`$AOS_STACK` ＞ `$AOS_WS/.stack/`。每支開頭的說明寫了全部規則。

## 怎麼用

PATH 要有 aos-exec、aos-loop、aos-fsm（同 demo/run.sh）與這裡的 `bin/`：

```sh
R=~/repo/simple_tools/aos/proto8
export PATH=$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-fsm/bin:$R/human/bin:$PATH
mkdir -p ~/code/try/say-listen/ws && cd ~/code/try/say-listen/ws
export AOS_BRAIN_URL=http://localhost:4000/v1          # 不設＝假腦

aos-chat $R/demo/agent-dan                              # 一問一答，chat 每句之後替你跑一次 agent

# 或分開：
N=$(aos-say 現在幾點？)                                 # 放一題
aos-exec --ws . $R/demo/agent-dan                       # 跑（別的終端機也行）
aos-listen "$N"                                         # 拿這題的答案
aos-listen --last 5                                     # 最近五組問答
```

**要 agent 一直在**（不用每次跑）：用 aos-loop 包一層，放在工作區外面，例 `~/code/try/say-listen/serve/loop.json`：

```json
{"_entry": ["aos-loop", {"$env": "AOS_CF"}],
 "exec": {"argv": ["aos-exec", "/絕對路徑/proto8/demo/agent-dan"]},
 "interval_ms": 1000}
```

`aos-exec --ws ~/code/try/say-listen/ws ~/code/try/say-listen/serve/loop.json` 開著，另一個終端機 `aos-chat`（不給 agent）就行。agent 失敗時外層 loop 也會停（P-20），修好再開。
