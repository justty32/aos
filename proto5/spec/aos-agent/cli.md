← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 1. 用法

（09-24 fix-r4 改：家一律 `--target DIR`，不再是位置參數；`last` 併進 `listen`；加 `pause`）

```
aos-agent tick     [--target DIR]
aos-agent start    [--target DIR]
aos-agent stop     [--target DIR]
aos-agent init     [--target DIR] [--force]
aos-agent say      TEXT [--target DIR] [--wait [秒]]
aos-agent listen   [--target DIR] (--last [N] | --wait [秒] | --follow) [--show-calls | --show-calls-full] [--json]
aos-agent status   [--target DIR] [--json] [-v]
aos-agent pause    [--target DIR]
aos-agent continue [--target DIR | --all]
aos-agent check    [--target DIR] [--probe]    # （09-24 advice-r1）start 之前先查一遍，§1.7
aos-agent tools ls      [--target DIR] [--json]                                    # §1.8 續（09-24 access-impl）
aos-agent tools add     NAME|DIR|FILE.json [--target DIR] [--as NEW | --as OLD=NEW[,…]] [--only a,b] [--root DIR] [--force]   # §1.8（09-24 tools-base 補，access-impl 補 --as／--only）
aos-agent tools rm      NAME [--target DIR]                                         # §1.8 續：只改 info.json，不刪檔
aos-agent tools alias   NAME NEW [--target DIR]                                     # §1.8 續
aos-agent tools unalias NEW [--target DIR]                                          # §1.8 續
aos-agent talk     [--target DIR] [--wait 秒] [--show-calls]   # （09-24 talk）來回對話，§1.9
aos-agent access ls  [--target DIR] [--json]                                        # 權限牆（09-24 access-impl，access.md §3）
aos-agent access set NAME PATH [--ro | --rw] [--cwd] [--target DIR]                 # 同上
aos-agent access rm  NAME [--target DIR]                                            # 同上
aos-agent access cwd NAME [--target DIR]                                            # 同上
aos-agent access net on|off [--target DIR]                                          # 同上
aos-agent context [--target DIR] [--by-round] [--json]                             # （09-24 第 4 隊）cli-memory.md
aos-agent compact [--target DIR] [--keep-rounds N] [--max-tokens X] [--dry-run] [--json] ｜ --prune-archive 天數   # 同上
aos-agent events  [--target DIR] [--last N] [--usage] [--json]                    # 同上
aos-agent history [--target DIR] --archive [SHA] [--grep 字] [--json]              # 同上
aos-agent notes   [--target DIR] ls [--json] | show KEY                            # 同上
aos-agent -h ／ aos-agent <子命令> -h        # 每個子命令一句話
```

`--target` 省略＝目前資料夾（agent 沒有對應的環境變數），必須是 agent 家（`NotAnAgent`；`init` 例外）；`NotAnAgent` 的訊息講清楚這次用的家是 `--target` 給的還是目前資料夾。
（09-24 fix-r5 補）`info.json` 的 `_metainfo._type` 是別的字串（例如指到 kernel 家）時，`NotAnAgent` 直接說「`<dir>` 是 kernel 家，不是 agent 家」（`kernel` 換成那個 `_type`）。
`continue --all`（§1.4）跟 `--target` 互斥（兩個都給＝用法錯 2），要 `AOS_KERNEL_HOME`（沒設＝用法錯 2）。
`tick`／`start` 都要 `AOS_KERNEL_HOME`：沒設或不是絕對路徑＝用法錯 2；
（09-24 試玩 r2 補）`stop` 沒設 `AOS_KERNEL_HOME` 就用 `tick.json` 記的（§11，字面絕對路徑才算），兩個都沒有＝用法錯 2。其他子命令不要 `AOS_KERNEL_HOME`（`say`／`status`／`listen` 有設就拿來看登記狀態；（advice-r1）`check` 有設就查那個 K，沒設看 `tick.json`，都沒有是一行 `bad`、不是用法錯，§1.7）。
`--json` 只給 `listen`、`status`、`tools ls`、`access ls`（09-24 access-impl），給別的＝用法錯 2；`--probe` 只給 `check`。（09-24 listen 微調）`listen` 三種看法一定要給一種，`--last [N]`、`--show-calls*` 見 §1.5。`talk` 也有 `--show-calls`（簡化版，見 §1.9），`talk --wait` 一定要帶秒數、省略整個旗標＝120 秒（§1.9）。`--wait` 的秒數：省略＝**300 秒**；給了要是 0～604800（7 天）的數字（可帶小數），不是＝用法錯 2。

## 1.1 `init`：生一個最小可跑的家（09-24 試玩 r2 補）

家（`--target`，省略＝目前資料夾）不在就建。`<家>/info.json` 已在＝`AlreadyExists`、退 1、什麼都不寫（`--force` 也一樣）。
（09-24 fix-r5 補）家已在、不是空資料夾、又沒有 `info.json`（不是 agent 家）＝`NotEmpty`、退 1、什麼都不寫，訊息列出前幾個已有的檔名、說「確定要生在這裡就加 `--force`」；`--force` 才照樣生（已有的檔不動，同名的 `prompts/system.json` 等會被蓋掉）。
否則寫出**內建的一份預設**（寫死在程式裡；之後會有 `--template`，這版沒有）：

| 檔 | 內容 |
|---|---|
| `info.json` | `llm.model` 是代號 `"default"`、`llm.pool` `llm`、`llm.timeout_ms` 125000、`tools: ["tools"]`（整個資料夾）、`tool_pool` `default`、`tick` `{"pool": "default", "interval_ms": 1000}`；`system`／`history` 照預設路徑 |
| `prompts/system.json` | 一句人格（繁體中文助理，要時間就叫 `date`） |
| `tools/date.json` | 一個 `date` 工具當範例（`_meta: {"argv": ["date", "+%Y-%m-%d %H:%M:%S"]}`） |
| `state.json` | `{"input": "input"}`：輸入從 `input/` 資料夾收，`say` 每則取唯一檔名 |
| `access.json` | （09-24 access round2）有工具的家一定要有表，`init` 順手生一份預設：`{"mounts": {"ws": "workspace"}, "cwd": "ws", "net": false}`——連範例的 `date` 工具也關牢，只看得到 `workspace/` |
| `input/`、`log/`、`workspace/` | 空資料夾 |

每個檔 `.tmp` 再 rename，**`info.json` 最後寫**（中途崩了不會半套被當成 agent 家；（09-24 access-impl）`info.json` 縮排 2、不跳脫中文，方便手改）。成功印三行：`initialized <dir 絕對路徑>`、
一行 access.json 的提醒（`access.json：工具關在牢裡，只看得到 /work/ws（＝workspace，可寫）、不能上網；改：aos-agent access ls／set`），
和一行提醒：llm.json 不歸 agent 家，它在 kernel 的 llm cpu 用 `AOS_LLM_CONFIG` 指的位置，裡面要有 `default` 這個代號。退 0。
