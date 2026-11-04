← [agent-access 提案](README.md)

# 完整版的契約（astra 審查 M2～M8 之後補）

把「誰在什麼時候讀表、牢裡看得到什麼、什麼一定不能被工具改到」寫死。這是提案，還不是規範。

## 1. 誰解、什麼時候解：**送件時解一次，整批同一份快照**

- **aos-agent 送一批工具時**（[aos-agent §5.2](../../spec/aos-agent/send.md)，建 `work/N.inst.json` 那一步）解映射表：中心＝agent 家，`$env` 用跑 tick 那格的環境——跟現在解 `_meta` 完全同一套。
- **一批只解一次**：這批第一件的 inst 要寫之前解好，存進 `state.json` 的 `batch`（例如 `batch.access`），同批每一件都用它；崩潰重來也用它，不重解。所以一批裡不會混到新舊兩份表。
- 解好的表**展開成字面參數**寫進 inst，`aos-jail` 自己**不讀** `access.json`、不解指示詞（它在牢外、但只照參數做事）：

  ```json
  {"argv": ["aos-jail", "--mount", "ws=/home/u/ws-A", "--mount-ro", "util=/home/u/aos/util-tools",
            "--tool", "/home/u/aos/util-tools/bin/edit-a", "--chdir", "ws", "--net", "off", "--"],
   "cwd": "/home/u/aos/amy", "stdin": "…/work/N.in", "stdout": …}
  ```

  `--tool` 是 `_meta.argv[0]` 解好的**牢外**路徑；aos-jail 把它所在的資料夾唯讀掛到 `/opt/tool`，改寫成牢內路徑再跑，`_meta.argv` 其餘參數接在 `--` 後面原樣傳。外層 inst 的 `cwd` 仍是 agent 家（aos-exec 要在那裡開串流）；牢裡的起點是 `--chdir`，兩者分開。
- **有映射表就一律關牢**：工具檔、`_meta` 都不用寫 `aos-jail`，aos-agent 自動包。沒有 `access.json` 的家照現行行為跑（相容）；想要「有表但某支工具不關」不提供。
- **生效時機**（最小版也一樣，因為最小版在寫 inst 時就把 `$ref` 解成字面）：
  - 改表之後**下一批**生效；已寫出 inst 的那批（排隊中、跑到一半、崩了重送）都用舊的。
  - 正在跑的工具不會因為改表被收回權限。**要馬上撤**：`aos-agent pause`（不再送新批）；還在排隊的那幾件可以 `aos-kernel rm <工作名>` 取消（[kernel §2](../../spec/kernel/syscall.md)：`queued` 直接拿掉）；**已經在跑的，`rm` 只丟掉回音、不殺行程**，現在沒有指令能停它，只能等它跑完（`_timeout_ms` 到了 kernel 會砍）或手動 kill。`aos-agent stop` 也不會停已送出的工具。要不要補一個「撤權＝殺掉這個 agent 在跑的工具」的指令，留給之後。
  - 待確認：手動 `rm` agent 送出的工具後，agent 收回那件時怎麼判（kernel 回 `Removed`）——實作前要對一次 [aos-agent §6](../../spec/aos-agent/collect.md)。

## 2. 牢裡看得到的東西只有三類

| 類 | 內容 | 權限 |
|---|---|---|
| 使用者映射 | `access.json` 的 `mounts`，掛在 `/work/<名字>` | 照表：可寫或 `ro` |
| 固定執行環境 | `/usr`（唯讀）、`/bin`／`/lib` 等連結、新的 `/proc`（`--proc`，配新 pid namespace，看不到別的行程）、最小 `/dev`（`--dev`）、空的 `/tmp`；`/etc` **不整份掛**，只掛跑程式要的幾個檔（`ld.so.cache`、`passwd`／`group`、開網路時的 `resolv.conf`、`ssl/`） | 唯讀 |
| 受控串流 | aos-exec 在牢外開好的 stdin（`work/N.in`）、stdout（`work/N.out`）、stderr（`_meta` 指的檔） | 只有這三個檔的 fd；看不到它們的資料夾 |

- **不保證「模型永遠看不到真路徑」**，只保證「工具的路徑是穩定的別名」：檔案內容、`/proc/self/fd` 的連結、程式自己印的東西都可能帶出牢外路徑。
- **通訊入口**：映射目錄裡如果有 Unix socket（例如某個服務的 `.sock`），唯讀也擋不住連它、請牢外服務代做事。規則：`check` 對映射目錄頂層與已知位置掃 socket／FIFO 給 warn；使用者別把含服務 socket 的資料夾映射進去。`net: true` 是共用主機網路（連得到本機 LiteLLM、區網），不只是「能下載套件」。
- **待確認**（要實機測，還沒做）：在真的 base bash 行程樹裡看 `/proc/*/fd`，能不能從受控串流的 fd 反推或重開 `work/` 其他檔。先照「看得到檔名、開不了別的檔」寫，測完再改。

## 3. 信任資料：工具永遠不能寫到

會決定「權限」或「跑什麼」的東西叫**信任資料**：`access.json` 與它 `$ref` 到的每一份檔（遞迴）、`info.json` 與它 `$ref` 到的檔、`tools` 列到的工具檔與資料夾、每支工具 `_meta` 引用的檔、工具程式本身與它所在的資料夾，以及 agent 家（`state.json`、`.tick.lock`、`paused`、`resumed`、`input`、`waits` 的門檔、`work/`、`log/`）。

- **規則**：任何**可寫**的映射，解開符號連結後，不能是信任資料的同一個位置、祖先或子孫。違反＝aos-agent 送件時這批每一件都「跑不起來：AccessUnsafe：ws 可寫、但包含 tools/…」，`check` 標 bad。只讀映射可以重疊。
- 共用工具夾因此**只能唯讀掛**；想讓 amy 改共用工具＝不支援（她改了會下毒給所有 agent）。
- 限制（明講、不處理）：有人事先在 workspace 裡建好指向信任資料的**硬連結**；檢查之後、下一批之前才被人換掉的符號連結（下一批會再檢查一次）。

## 4. 開放 amy 自己（`self`）

- **預設整個家唯讀**（`self` 一律 `ro`）；要讓她寫東西，映射一個**家外面**的資料夾（例如 `notes` → `~/aos/amy-notes`），或家裡明確的子資料夾（例如 `self-notes` → `./notes`），後者一樣要過 §3 的規則（`./notes` 不能含信任資料）。
- 不採「整個家可寫、黑名單蓋唯讀」：控制檔名單會長（`.tick.lock`、`paused`、`resumed`、門檔、自訂的人格／記憶路徑），不存在的檔蓋不上、之後就建得出來（例如自己建 `paused` 讓自己停擺），而且牢外程式會 rename 替換這些檔。實驗 3 只證明「蓋得上去」，不證明這些情況安全。

## 5. `aos-agent check` 多驗的

- 映射表：解得開、名字合法（`[a-z0-9_-]+`，不能是 `.`、`..`）、路徑存在、`cwd` 指的名字在 `mounts` 裡、§3 的重疊規則。
- bwrap：跑一次固定、沒副作用的 `bwrap … true` 看能不能開；不跑任何工具、不建資料夾（check 唯讀的約定）。
- 每支工具：牢外的程式在、有執行位；**牢內**跑不跑得起來（直譯器、動態函式庫）靜態查不完，查不到的印 warn 而不是 ok。

## 6. 隔離不包括的

- **同一批平行跑的工具**仍共用同一個 workspace：兩支同時寫同一個檔照樣互蓋。有先後的仍要分兩批（叫模型一次一支）。
- **資源上限**（磁碟、輸出大小、行程數、記憶體）bwrap 不給；要的話另一層（cgroup／`systemd-run --user --scope`），這條線不做。
