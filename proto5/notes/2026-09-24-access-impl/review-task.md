← [access-impl](progress.md)

# 任務書：權限牆＋工具管理 CLI 唯讀審查（2026-09-24）

你是唯讀審查者。**不要改任何檔**，只把發現寫成報告（繁體中文）。

## 背景

使用者要在「工具大開發」前先把權限弄好：agent 的工具只能碰指定資料夾，人也要能用指令或文字編輯器管理工具（加、刪、改名）與權限。
設計稿：`proto5/notes/2026-09-24-agent-access/`（README、contract.md）；實作定案：`proto5/notes/2026-09-24-access-impl/progress.md`。
範圍：`git show d4a9797 --stat`。

- 程式：`proto5/lib/aos_agent_access.py`、`aos_agent_access_cli.py`、`aos_jail.py`、`proto5/cli/aos-jail`、`aos_agent_batch.py`（包牢）、`aos_agent_home.py`（tools `$opt`）、`aos_agent_tools.py`、`aos_agent_tools_edit.py`、`aos_agent_cli.py`、`aos_agent_check.py`、`aos_agent_status.py`、`aos_agent_info.py`、`proto5/tools/base/_common.py`
- 規範：`proto5/spec/agent/access.md`、`tools-opt.md`、`info.md`、`state.md`；`proto5/spec/aos-agent/access.md`、`tools.md`、`tools-manage.md`、`send.md`、`cli.md`、`cli-check.md`；`proto5/spec/aos-exec/aos-jail.md`
- 測試：`proto5/lib/test/test_agent_access.py`、`test_jail.py`、`test_agent_tools_manage.py`

## 要看的

1. **逃逸路徑**：牢裡的工具有沒有辦法讀寫表外的資料夾（`..`、絕對路徑、符號連結、`/proc`、串流 fd、`/opt/tool` 的程式資料夾、`/etc` 掛了什麼、`/tmp`、環境變數）？信任資料重疊檢查漏了哪些（可寫 mount 蓋到 tools、info、access 檔、state、門檔、`$ref` 到的檔）？`realpath` 與檢查時點（TOCTOU）有什麼洞？
2. **環境變數洩漏**：`AOS_KERNEL_HOME`、`AOS_LLM_CONFIG`、API key 有沒有任何路徑進得了牢（`--setenv` 過濾、`_meta.envs` 的 `$env`、外層 inst 的 envs、`aos-jail` 自己的參數寫在 inst.json）？
3. **`$opt` 與現行規範矛盾**：tools 元素的 `$opt`（as／only）跟 `spec/directives/`、`spec/agent/info.md`、`aos-llm` 的 `load_llm_view` 共用是否一致；錯誤代號選得對不對；`_source`／`_jail` 會不會漏給模型。
4. **CLI 手感**：`tools ls/add/rm/alias/unalias`、`access ls/set/rm/cwd/net` 的訊息、退出碼、`--target` 慣例、壞檔時拒寫、並行時的 flock、人用文字編輯器改 `access.json`／`info.json` 的方便程度（格式、錯誤訊息指得到哪一格）。
5. **快照與生效時機**：`batch.access` 何時解、崩潰重送是否用同一份、舊 state 相容、沒 bwrap 時的行為、`_jail: false`。
6. **測試漏**：規範裡重要行為沒被測到的；會不穩的測試。

## 報告格式

- 開頭一段總評。
- **必修**（逃逸、洩漏、程式錯、規範與程式不符、會當掉）：每條「在哪（檔:行）、怎麼重現、建議怎麼改」。
- **建議**（可改可不改）：同上，簡短。
- **不用改**（看過判斷沒問題的重點）：一句一條。

測試指令（唯讀沙箱跑不了就跳過）：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_*access*.py'`
