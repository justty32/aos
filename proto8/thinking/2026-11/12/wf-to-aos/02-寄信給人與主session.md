# 02 寄信給人、明天主 session 卡在哪、邊緣狀況、之後自然會長的（11-12 晚，對標調查結論之二）

← [回入口](../wf-to-aos.md)｜所在段落：[現有東西夠不夠對標 wf/ 規矩](../wf-to-aos.md#現有東西夠不夠對標-wf-規矩11-12-晚家機)｜上一份：[01-對標調查結論](01-對標調查結論.md)

## 等使用者＝寄信給人：照抄指令與兩個洞

在 scratchpad 實跑過；不給 `-s` 就是人自己的 `~/.aos/stack`（家機這個信箱已經存在）。

```sh
# agent 寄給人（agent 的腦叫 mailbox_send 帶 box 參數是同一件事）
aos-mailbox -s <agent 的 stack> send --box ~/.aos/stack/mailbox --from eca_main \
  --status NEEDS-USER --title "index L7-L10: 4 defaults wait for your ruling" \
  --decide "reply L7:ok L8:ok ..." "see proto8/thinking/2026-11/12/index-link.md"
# 人：看有哪些在等（＝WAIT_USER 的 open 清單）
aos-mailbox peek            # 01794…  eca_main  NEEDS-USER  index L7-L10: 4 defaults wait for your ruling
# 人：讀、回
aos-mailbox read --keep     # 印 from/status/title/what/…/reply_to；--keep 留 archive/
aos-mailbox send --box <上面印的 reply_to> --in-reply-to <信名> --status DONE --title "L7-L10 all ok" "all ok"
```

實跑：寄後人的 peek 一行、read 後空了、agent 的 peek 出現 `lorkhan DONE L7-L10 all ok`。

兩個洞：

1. **讀了≠回了**：`read` 一讀就從 open 消失，不管回沒回；`--keep` 的 archive 混著已辦與未辦。補法二選一：約定平常只 `peek`、回信時才 `read`；或補一個「回了才消」的動作。
2. **人不會被通知**：`mail_notify` 是 agent 的 hook，人那邊沒有；可掛一支 on_clock 或桌面通知。

（另兩點較小：只有 STATUS＋標題、沒有 wait-user 的四類；信箱在本機不跨機。）

## 明天主 session 開始：現在卡在三點

1. **MCP 起得來但 0 支工具**（11-12 晚已修，見下）：`~/.cache/aos-mcp-aos/tools.json` 原本只有 `aos_kb`、`wf_kb` 兩格，都指 11-12 已刪的 `lib/agent/memory_read`；實跑每次 warning `tool aos_kb skipped: PathMissing`，本 session 報 `aos: CONNECTION_CLOSED`。

   **已修（11-12 晚，家機）**。使用者原話：「好，這些都不是問題。只是主session接mcp這個要處理。邊緣狀況這邊就先這樣，之後踩坑再說。」
   - 做了什麼：只動 `~/.cache/aos-mcp-aos/tools.json`（舊檔備份成同夾 `tools.json.bak-1112`）；`~/.claude.json` 沒動（它那行 `aos-mcp --ws ~/.cache/aos-mcp-aos/ws ~/.cache/aos-mcp-aos/tools.json` 照用）。新登記檔照範本 `templates/eca-claude/tools.json` 用 `$override` 疊 `lib/packs/json.json`、`lib/packs/index.json` 兩包，每支只補一格 `env` 把 `AOS_WS` 設成 repo 根。
   - 掛了 10 支：`index_view`、`json_get`／`json_ls`／`json_search`／`json_len`／`json_set`／`json_add`／`json_del`／`json_multi_get`／`json_multi_set`。路徑參數的相對路徑一律從 repo 根 `/home/lorkhan/repo/simple_tools/aos` 算，跟主 session 的 cwd 無關（從 `/tmp` 起也一樣）。
   - 實跑（照 `~/.claude.json` 那行手動起 stdio）：`initialize`＋`tools/list` 得 10 支；`index_view proto8/knowledge/aos` 印 `[index] proto8/knowledge/aos/_index.json, 20 entries`；`json_get`、`json_ls`、`json_len` 都正常；stderr 只有故意叫錯檔那次的 `FileMissing`；關 stdin 退 0。`aos-tools --file … ls` 列 10 支、退 0、沒有 warning。
   - 沒掛：mailbox 三支（主 session 不在 daemon 表上＝`DaemonMissing`）；aos 的基礎檔案工具（主 session 自己有讀寫檔與 shell）；`todo`（見代定）。
   - 代定：(1) 不掛 `todo`——主 session 經 aos-mcp 用，清單會存在 `~/.cache/aos-mcp-aos/ws/.stack/tools/todo/todo.json`，是這台機器上這個 repo **所有同時開著的主 session 共用一張**、不進 git，幾個 session 會互蓋；Claude Code 自己也有待辦工具。要掛時再決定清單歸誰。(2) 包的路徑照範本寫 `{"$env": "AOS_HOME", …}`、`AOS_WS` 寫絕對路徑：包裡每支工具本來就用 `$env AOS_HOME`，外層改寫絕對路徑也躲不掉這個依賴（實跑：拿掉 `AOS_HOME` 照樣 `DirectiveBad`），所以只留 `AOS_HOME` 一個要顧的點；`~/.claude.json` 那台的 `env` 是空的，靠 Claude Code 從 `.zshrc` 繼承 `AOS_HOME`（家機現在跑的主 session 有）。不從有 `AOS_HOME` 的 shell 起 Claude Code，aos MCP 會起不來（`ToolsBad`）；要更穩可在 `~/.claude.json` 那台的 `env` 加 `AOS_HOME`，沒動、留給使用者。(3) `json_set` 等寫入工具照「json 整包」一起掛。
   - 使用者要做的：重開 Claude Code 或 `/mcp` 重連 aos，看到 10 支就對（記在 [wait-user/04](../../../../../wf/wait-user/04-雜事.md)）。
   - 明天接著的事（使用者說明天開始／之後踩坑再說，這次沒做）：Skill 放哪（`.claude/skills/`）；主 session 的身分（算不算一隻 agent、別的 agent 回信 `reply_to` 指哪個信箱，連帶 mailbox 三支能不能掛）；always-on 規矩怎麼進主 session；`todo` 歸誰。
2. **信箱與 self 類工具不通**：`mailbox_peek／read／send`、`self_*`、`goal`、`subagent`、`fork` 先 `aos-agent ctl who` 認人，主 session 不在任何 daemon 表上→`DaemonMissing`。主 session 收信只能走 Bash `aos-mailbox`；把主 session 登記成表上的一隻，現在沒有這種做法；它給別的 agent 的 `reply_to` 指哪個信箱也沒定。
3. **Skill 與規矩兩套**：repo 沒有 `.claude/skills/`（只有 `.claude/commands/wf-lint.md`）；同一份 skill 主 session 與 eca 共用的前提是 eca 的工作區就是 repo，那時 eca 推測也會讀 CLAUDE.md 與 `.claude/settings.json` 的 compact hook（未實跑驗證），兩套規矩同時進 eca。

## 邊緣狀況

1. **兩套並存誰是準**：鐵律、user.md 偏好若同時抄一份進 system.txt／json，改一邊另一邊不跟。
2. **agent 改壞規矩**：`self_system set` 整份換掉 system、`self_hook rm` 拿掉 mail_notify、`json_set`／`json_del` 改共用規矩 json，都不擋；救法只有人 `aos-agent system reset` 或 git（規矩放 repo 至少有 diff）。
3. **人看不懂 json**：散文的跳脫字元；`index_view` 最像目錄頁但只到一句說明。
4. **讀了當掉**：`read` 後當掉或忘了回，那封就從 peek 消失。
5. **index 說謊**：`_index.json` 加一格不存在的 `ghost.md`，`index_view` 照印、不警告（工具本來就說「是視角不是事實」）；新增節點沒補 index 也看不出來。
6. **主 session 不在表上**：見上節〈明天主 session 開始〉第 2 點。
7. **index 樹裡的相對路徑**：容器規則（index-link L7～L10）還在代定；搬檔後的路徑換算只有 `agent_def new` 會做，內容樹沒有。
8. **agent-fsm 沒有自動 compact**：長對話靠腦自己 `self_history summarize`、`do_task start/end` 收。

## 之後自然會長的（只記現有材料）

- **always-on 怎麼掛**（使用者：「玩一玩自然會想到，反正有hook」）：`system.txt`（agent-fsm 取代、eca 每輪附加）；hook 事件 before_queue／after_queue／before_tool／after_tool／brain_failed／tool_added／after_start／after_stop／on_clock（`lib/agent/hooks.py`），**沒有 compact／history 變了的事件**；換台開新對話有 reseed 開場白（`aos_eca/reseed.py`）。
- **檢查工具**（使用者：「先放着」）：現有只到定義／工具層——`agent_def check`、`tools_def check`、`aos/defs` 的 problems、`metainfo_check`、`aos-tools` 載入時對壞路徑 warning、`aos-daemon-ctl prune`；要跑可掛 on_clock 或 before_tool，現在沒人掛。
- **人讀 json**（使用者：「有需要的話再做一些輔助工具」）：`index_view`（KEY TAB 說明）、`json_ls --depth`、`json_get`、`view`（一次一層）、`aos-json get/ls/search`。
- **多 agent 工作流**：`subagent`、`agents_ctl`、`fork`、`do_task`、eca 的 `Agent`，交接書＝一封 REQUEST 信；機制夠，wf dispatch 的領地表、交接書六條、可觀察驗收還沒有 aos 版。
