← [入口](../proto8.md)｜涵蓋：`proto8/lib`（腦可以叫的工具庫，10-24 開、下午遷移）｜周邊其他資料夾見 [06-周邊工具](06-周邊工具.md)

### `proto8/lib`（腦可以叫的工具庫）

agent 的 `tools/<名>` 用捷徑掛進來的標準工具（引用、不複製）。10-24 上午收了 `base/` 七個，下午照 tool-lib 遷移清單把各 demo 自帶的工具搬進來。說明、工具契約與完整索引在 [lib/README](../../../../../proto8/lib/README.md)；設計與遷移紀錄 [thinking 2026-10-24-tool-lib](../../../../../proto8/thinking/2026-10-24-tool-lib.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `README.md` | 分層（base／aos／agent）、工具契約十條（stdin 一份 JSON、stdout 是結果、錯一行同時印 stdout、只碰 `$AOS_WS`、逾時、原子寫檔…）、怎麼用捷徑引用、三層的索引 |
| `<層>/<名>/`（每個一樣三個檔） | `_entry`（第二行是 NAME）、`_tooldef.json`（給模型看，`description`＋`parameters`）、`_metainfo`（給 kernel 與人：`summary`、`time_ms`、`side_effect`…） |
| `base/read`、`write`、`edit`、`bash` | 讀檔（2000 行或 50KB 截）、整份寫、照字面替換（全有或全無）、在工作區跑一行 bash（`timeout_s` 30／300、整群收）；來源 demo/pi-tools |
| `base/ls`、`stat`、`view` | 列資料夾（分頁、回 JSON；資料夾帶 `counter_children`、`aos` 記號，`.json` 帶頂層 key；計數 10-25 起一律 `counter_*`）、單一個的屬性、漸進看檔（JSON 照指標一層、大文字先給大綱）；`ls` 是上午的新寫併 file-tools 的加料，`stat`、`view` 來源 demo/file-tools |
| `base/mkdir`、`move`、`copy`、`trash` | 建資料夾、搬／改名、複製（捷徑照捷徑）、丟進 `.trash/<時間>/`（可救回）；來源 demo/file-tools（`common.py` 攤回各工具） |
| `base/json_read`、`json_edit` | 照指標看 JSON（大的摺起來，Python）；照指標改 JSON（`set`／`del`，先在記憶體全部驗過、再叫 PATH 上的 `aos-json` `batch`／`append`／`del` 寫，只重寫有變的那塊） |
| `base/math`、`clock` | 四則運算（`ExprBad`）、印 UTC 時間；來源 agent-dan 的同名工具（hal、kai、talk 的複本改掛這裡；agent-dan 自己那份留著當範本） |
| `base/run_python` | 跑一段 Python（程式寫進自己的小格 `main.py` 再跑）、回結束碼與輸出，逾時 `timeout_s` 60／300 算 `CommandFailed`；來源 agent-gus |
| `aos/aos_ws.py` | 不是工具（沒有 `_entry`）：「寄信、等答案、讀 stack」的共用模組；10-30 起照 CONVENTION P-42 只碰 stack——`stack_of`、`names`／`where`／`waiting`（queue 的 new／cur／done）、`put`（一則 user message，`aos-post init`＋`send --ordered`）、`history`／`answers`／`exchanges`（回答＝沒有 tool_calls 的 assistant）、`loop_state`（state.json）、`unit_of`／`failed`（trace 一行）、`tail_jsonl`、`last_jsonl`（10-30 前：`put` 進工作區 `new/`、`answer_name`／`answer_text` 讀 `out/`）；proto8/extras/human 的三支與 ai_tools 的 aos-ai 一起 import（10-24 遷移時兩份合一） |
| `aos/memory/`（多一個 `heap.py`） | 長期記憶庫：`op` save／search／read／forget；庫在 `$AOS_HEAP`（沒設＝`$AOS_WS/.heap/`）；`heap.py` 是讀寫本體（掛它的 agent-meg 的 brain 也 import）；錯 `ArgumentsBad`、`OpUnknown`、`MemoryMissing`、`HeapBad` 退 1；來源 agent-meg |
| `aos/send_message`、`check_inbox` | agent 之間寄信：照 `$AOS_ROSTER` 名冊寄進對方信箱 `new/`、自己留 `sent/`、對話串跟 `cur/` 走（信的手數 `counter_hops`）、到 `max_hops`／`max_sends` 擋（`HopsBad`、`SendsBad`…退 1）；看自己信箱還沒處理的；來源 demo/talk |
| `aos/ask_round` | 同步問一隻格組起來的 agent 一題（queue push＋一格一格叫 aos-round＋印答案）；逐檔在 [12-agent-round](12-agent-round.md) |
| `aos/spawn_agent`、`ask_agent`、`agent_status`、`make_json`、`make_tool`、`explain_aos` | 轉叫命令列 `aos-ai`（起 agent、問、看狀態、生成 JSON 與工具骨架、查概念）；aos-ai 的錯照它的代號退 1；`template` 沒給＝agent-nia（10-30 起，原 agent-dan）；ask_agent 的答案＝那次 run 的 `answered` 有這封時最後一則回答；子 agent 放 `$AOS_AI_ROOT`（沒設＝`$AOS_WS`）；來源 ai_tools/dan_tools |
| `aos/try_run` | 在工作區 `target/` 的暫時複本上 `aos-exec` 跑一次、回結束碼與輸出（`timeout_s` 10／60，逾時算 `CommandFailed`；有 `$AOS_IMPROVE_SANDBOX` 就關進 aos-sandbox）；來源 self-improve 的改進者 |
| `agent/agent_tool.py` | 不是工具：「把一隻 agent 包成工具」的轉接，共用一支——`fresh_cell`（`$AOS_STACK/runs/NNN/` mkdir 搶號）、`run_agent`（題目寫進子 agent 的 `ws/new/`、`aos-exec --dotenv-override --ws` 跑、拿 `ws/out/` 的答案；錯 `AgentFailed`、`AnswerMissing`）；10-24 遷移從 pyfix 抽出 |
| `agent/pyfix/`（多一個 `agent/`） | 把改 Python 的事交給子 agent pyfix-agent：`_entry`（dir 檢查、備份 `before/`、叫 `agent_tool`、印答案＋實際 diff；`AOS_PYFIX_DIR`、`PYTHONDONTWRITEBYTECODE` 往下帶）；`agent/` 是 agent-dan 範本（`act.py` 工具一律 `aos-exec --ws $AOS_PYFIX_DIR`、工具退非 0 回給腦；`tools/` 是 `../../../../base/` 的 ls、read、write、edit、bash 五條捷徑；`system.txt` 照新工具名）；來源 agent-eve |
| `agent/cli_session.py` | 不是工具：claude／codex CLI 接成工具的做法（畫面沒開＝非互動續同一段對話；開著＝tmux 貼字、等 hook）；`call_main(工具資料夾)`、`attach_main(argv, agent 資料夾)`、`hook`；`note_cell`（格裡記 `tool.txt`／`ws.txt`；10-27～10-29 叫 `register`、還送一行給 `$AOS_HUB/kernel.sock`，10-30 eca 衝突 6 刪了）、`open_cell`（照格裡的記錄開畫面／叫回）、claude 非互動改 stream-json 並寫 `live.jsonl`（10-28 起只接不重寫，codex 的 `--json` 事件也接）；10-28 加 `close`（關畫面）、`transcripts(kind, id)`（CLI 自己存的對話檔在哪）、畫面 Ctrl-] 也跳出；10-30 加 `link_transcript`（拿到 session id 就建 `transcripts/<kind>-<id>.jsonl` symlink；call_main、hook、開畫面時各叫一次，工具格也建）、`freeze_transcripts`（symlink 換成複製、指不到不報錯；給 aos-eca-hub stop）、`ask`（問 CLI 一句：note_cell → lock → live／非互動 → symlink；call_main 與 eca 的 turn〔10-31 起 `bin/aos-eca-turn`〕共用）；10-31 `live`、`ask`、`call_main` 加參數 `on_busy="yield"`（預設不變＝有人佔著 SessionBad；`"answer"`＝lock 等、有人接著照貼、`busy.txt` 等它消失，共用 `timeout_ms`，給 `aos-eca-turn --on-busy answer`）；工具叫的錯照 lib 契約、attach 的錯 `cli_session:`；來源 agent-fay |
| ~~`eca/turn/`~~ | 外部 coding agent 的一輪（10-30）；10-31 改名＋升 bin 成 `proto8/bin/aos-eca-turn`，`lib/eca/` 整層刪了：逐檔見 [17-eca](17-eca.md) |
| `agent/claude`、`codex` | `_entry`（stdin `{"prompt"}` → 回答；從上一層或掛它的 agent 根找 `cli_session.py`；10-30 起註明這就是 eca 的工具形，跟 `lib/eca/turn --one`〔10-31 起 `aos-eca-turn --one`〕同一支 `call_main`，用 `on_busy` 預設）、`_tooldef.json`、`cli.json`（旗標：claude 只給 Read／Glob／Grep、sonnet、每次 0.5 美元；codex 唯讀沙盒）、`_metainfo`；來源 agent-fay |

測試：`proto8/tests/test_lib.py`（形狀檢查跑過三層每個工具、base 的行為、demo/agent-liv 經捷徑跑一題）、`test_pi_tools.py`、`test_file_tools.py`（原 pi-tools、file-tools 的案例，改指 `lib/base`）；aos、agent 兩層的行為在原本那幾份（`test_meg`、`test_talk`、`test_ai_tools`、`test_self_improve`、`test_eve`、`test_fay`）。
