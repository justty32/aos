← [notes 索引](../README.md)｜設計稿：[agent-access 提案](../2026-09-24-agent-access/README.md)

# 權限牆＋工具管理 CLI：進度與定案（隊長寫，接手隊先讀這份）

## 段落進度

| 段 | 內容 | 誰 | 狀態 |
|---|---|---|---|
| A1 | tools 元素 `$opt`（as／only）＋`tools ls/add/rm/alias/unalias` | Opus | 完成（d4a9797） |
| A2 | `access.json` 解析＋信任資料重疊＋`aos-jail`＋送件包牢＋check／status＋`access` CLI＋base `AOS_TOOL_ROOT` | Opus | 完成（d4a9797），全測 1343→1419 |
| B | 補測試（任務書第 5 項清單） | Sonnet | 進行中 |
| C | 教程／README／tools README | Sonnet | 進行中 |
| D | 真跑（LiteLLM deepseek-chat）→ `real-run.md` | Opus | 進行中 |
| E | astra 審查（任務書 fb33360）＋必修 | codex＋Opus | 審查中 |

隊長煙霧測試記下的待修（跟 astra 必修一起修）：`tools add base` 在有 access 檔時仍印「改 config.json 的 root」會誤導；`info.json` 被 CLI 改寫成一行，文字編輯器不好改（改成縮排 2）。
| F | 報告 | — | 未開始 |

基準：main 651ea4b。

## 定案（兩隊共同遵守；跟 H 隊 contract 不同的地方標「隊長定」）

### access.json

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "workspace", "ref": {"$opt": "ro", "$val": "~/docs"}},
 "cwd": "ws",
 "net": false}
```

- 位置：`<家>/access.json`；`info.json` 可有 `access` 欄（路徑字串，可用指示詞，相對 agent 家）指到別處。**檔不存在＝不關牢**（照舊行為）。
- `_metainfo` 可省；有寫就要 `_type: agent_access`、`_version: 1`。頂層其他不認得的 key＝`AccessInvalid`（抓 `mount`、`network` 這類手誤）。
- `mounts`：物件，可省（＝空）。key＝牢裡名字 `/work/<名>`，`[a-z0-9_-]+`（不能 `.`、`..`）。值＝路徑字串或指示詞（`$env`／`$ref`／`$fmt`），或選項物件 `{"$opt": "ro", "$val": …}`（唯一選項 `ro`，`$val` 必帶）。
  路徑：先解指示詞（中心＝agent 家、環境＝tick 那格的）、再 `~` 展開（隊長定）、相對的算 agent 家、最後 realpath；**要存在且是資料夾**。
- `cwd`：mounts 裡的名字；可省＝`/work`。`net`：bool，可省＝false；true＝共用主機網路（連得到 localhost）。
- 錯誤代號：格式錯＝`AccessInvalid`（訊息帶 access 檔路徑＋欄位位置，例如 `mounts.ws`；JSON 壞＝`JsonSyntax` 帶行列）；重疊＝`AccessUnsafe`；沒 bwrap＝`NoBwrap`。
- **信任資料與重疊（contract §3）**：信任集合 T＝access 檔本身＋它 `$ref` 到的檔、`info.json`＋它 `$ref` 到的檔、人格檔、記憶檔、`tools` 列到的每個檔與資料夾、每支工具程式（argv[0] 含 `/` 者）realpath 所在資料夾、家裡的 `state.json`、`tick.json`、`.tick.lock`、`paused`、`resumed`、`input`（或 state.input 指的）、`work/`、`log/`、`tools/`、`prompts/`。**家本身不在 T**，所以 `家/workspace` 可寫。
  可寫 mount M（realpath）跟 T 任一項 t（realpath）：`M==t`、M 是 t 祖先、t 是 M 祖先 → `AccessUnsafe: ws 可寫、但包含 <t>`。唯讀 mount 不查。所以「self」（＝家）只能 ro。
  （`$ref` 追不到全部的就盡量；抓不全的寫進規範「限制」。）
- **快照**：act 批在 `make_batch` 解一次，存 `state.batch.access`（沒 access 檔＝null；壞＝`{"error": "代號: 白話"}`；好＝`{"mounts": {名: {"path": 絕對, "ro": bool}}, "cwd": 名|null, "net": bool}`）。同批每件、崩潰重送都用它，不重解。think 批不存（或 null）。舊 state 沒這個鍵＝當 null。
- 快照是 error、或 bwrap 不在：這批每個要關牢的 call 記 `done: {"content": "工具 <名> 跑不起來：<代號>: <白話>"}`、`acked: true`，不送（照 send §5.3 解不過的處理）。
- `_jail: false`（工具元素頂層，跟 `_timeout_ms` 同層；只收 bool）：這支不關牢照舊跑；`check` 給 warn。其他工具照關。

### aos-jail

- 位置：`proto5/lib/aos_jail.py`＋`proto5/cli/aos-jail`（跟其他 cli 一樣薄殼；**不是** `lib/cli/`，隊長定）。純標準庫。**不讀 access.json、不解指示詞**，只照參數做。
- 用法：`aos-jail [--mount NAME=PATH]… [--mount-ro NAME=PATH]… [--chdir NAME] [--net on|off] [--setenv K=V]… -- PROG [ARGS…]`
- PROG 含 `/`（必須是絕對路徑）：realpath 後它的資料夾唯讀掛到 `/opt/tool`，執行 `/opt/tool/<檔名>`；不含 `/`：照牢裡 PATH 找。
- 組 bwrap：`--unshare-all`（net on 再 `--share-net`）、`--die-with-parent`、`--new-session`、`--clearenv`、`/usr` 唯讀、`/bin` `/lib` `/lib64` `/sbin` 照主機（是連結就 `--symlink`、是資料夾就 `--ro-bind-try`）、`--proc /proc`、`--dev /dev`、`--tmpfs /tmp`、`/etc` 只掛少數檔（`ld.so.cache`、`passwd`、`group`、`nsswitch.conf`、`localtime`、`hosts`；net on 再加 `resolv.conf`、`ssl/`、`ca-certificates/`，都用 `-try`）、每個 mount 掛 `/work/<名>`、`--chdir /work/<cwd>` 或 `/work`。
- 環境：只 setenv `PATH=/usr/local/bin:/usr/bin:/bin`、`HOME=/tmp`、`LANG`／`LC_ALL`／`TZ`／`TERM`（主機有才帶）、`AOS_TOOL_ROOT=/work/<cwd>`（沒 cwd＝`/work`）、以及 `--setenv` 給的。`--setenv` 的名字是 `AOS_*` 或含 `KEY`／`TOKEN`／`SECRET`／`PASSWORD`／`CREDENTIAL`（不分大小寫）或 `SSH_AUTH_SOCK` 一律丟掉（stderr 一行 warn）。
- 最後 `os.execvp` bwrap（行程就是 bwrap，kernel 逾時砍得到）。bwrap 找不到＝退 126，stderr：`aos-jail: 找不到 bwrap（bubblewrap）；Arch/Manjaro: sudo pacman -S bubblewrap，Debian/Ubuntu: sudo apt install bubblewrap`。用法錯＝退 2。
- aos-agent 包法（`tool_inst`）：外層 inst `argv = ["aos-jail", …旗標…, "--", PROG, ARGS…]`，PROG 含 `/` 時先照 inst 的 cwd 轉成絕對路徑；外層 `cwd`＝原本解出的（agent 家或 `_meta.cwd`）、stdin／stdout／stderr／exit 照舊；`_meta.envs` 的鍵值改成 `--setenv`（外層 inst 不帶 envs）。**牢裡起點只看 access 的 cwd**，`_meta.cwd` 只影響牢外（規範寫明）。

### tools 元素 `$opt`

- `info.tools` 每個元素：路徑字串、指示詞（解完是路徑字串），或 `{"$opt": {"as": {原名: 新名}, "only": [原名…]}, "$val": 路徑}`；`as`、`only` 各可省但至少一個；`$val` 必帶，可再是指示詞。
- `only` 先挑、`as` 再改名；`as`／`only` 寫了檔（或資料夾）裡沒有的原名＝`ToolInvalid`；改名後撞名＝`ToolInvalid`，訊息講是改名造成的；新名要非空字串。
- 讀工具後每條工具帶內部資訊 `_source`（`{"file": 絕對路徑, "index": i, "name": 原名, "entry": info.tools 第幾個}`），`_` 開頭送模型前拿掉。`function.name` 是改後的名字。
- `aos-llm call` 與 aos-agent 同一份程式（`load_llm_view`），兩邊看到同一個名字。`tool_paths`、`tools_raw`、`tools` 三個鍵保留。
- 規範：`spec/agent/info.md` 那句「沒有欄位吃 `$opt`」改成「只有 `tools` 的元素吃 `$opt`（§3.4）」。

### CLI（全部 `--target DIR`，省略＝`./`；所有改動最後一行印「下一批工具生效，不用重 start」）

```
aos-agent tools ls      [--target DIR] [--json]
aos-agent tools add     NAME|DIR|FILE.json [--target DIR] [--as NEW | --as OLD=NEW[,OLD=NEW…]] [--only a,b] [--root DIR] [--force]
aos-agent tools rm      NAME [--target DIR]
aos-agent tools alias   NAME NEW [--target DIR]
aos-agent tools unalias NEW [--target DIR]
aos-agent access ls     [--target DIR] [--json]
aos-agent access set    NAME PATH [--ro | --rw] [--cwd] [--target DIR]
aos-agent access rm     NAME [--target DIR]
aos-agent access cwd    NAME [--target DIR]
aos-agent access net    on|off [--target DIR]
```

- `tools add`：NAME（內建包）或含 `<資料夾名>.json` 的 DIR＝**裝包**（照舊複製進 `tools/`）；其他 DIR（例如 `../util-tools`）或單一 `.json` 檔＝**原地引用**（不複製，info.tools 加一條路徑；在家裡的寫相對家、家外的寫絕對）。給了 `--as`／`--only` 那條就寫成 `$opt` 物件。`--root` 只給裝包用。
  裝包時家裡**沒有 access 檔**＝順手建一份 `{"mounts": {"ws": <工作根目錄>}, "cwd": "ws", "net": false}`（工作根目錄＝`--root` 或 `workspace`），印出來；已有就不動（隊長定）。
- `tools rm NAME`（模型看到的名字）：只改 info.tools——那條只剩這支＝整條拿掉；還有別的＝那條改成 `only` 其餘的。**不刪任何檔**，印「檔還在 <路徑>」。
- `tools alias NAME NEW`：NAME 可以是現在的名字或原名；在提供它的那條加 `as`。`unalias NEW`：拿掉那條 `as`，`$opt` 空了就收回成純路徑字串。
- `tools ls` 欄：名字、原名（沒改名印 `-`）、來源檔（相對家）、關牢（`jail`／`no`（`_jail:false`）／`-`（沒 access 檔））、池。
- `access set`：PATH 照**殼的目前資料夾**轉成絕對路徑寫進檔（隊長定）；已有的名字沒給 `--ro/--rw` 就保留原模式；新名字預設 rw，但跟信任資料重疊時自動 ro 並印一句；明給 `--rw` 又重疊＝`AccessUnsafe` 退 1 不寫。原值是指示詞會被換成字面，印一句。`--cwd` 同時把起點設成它。
- `access rm` 目前的 cwd＝拒絕（先 `access cwd 別的`）。access 檔壞了＝所有 `access` 寫入指令拒絕並印哪裡壞（不蓋掉手寫的東西）。
- 寫檔一律 `.tmp`＋rename、持 `info.json` 的 flock（跟 `tools add` 同一把），JSON 縮排 2、`ensure_ascii=False`，保留使用者其他鍵。
- `access ls` 印表（名字、路徑、ro/rw、存在否）＋`cwd`、`net`、`bwrap: ok|沒有`＋一句「檔：<路徑>」；沒 access 檔印「沒有 access.json：工具不關牢…」並教一行 `access set`。

### 規範檔

- 新 `spec/agent/access.md`（檔案格式、信任資料、`self` 只能 ro）、`spec/agent/info.md` 加 §3.4 tools `$opt` 與 `access` 欄、`spec/agent/state.md` 的 batch 加 `access`、`spec/agent/errors.md` 加代號。
- 新 `spec/aos-agent/access.md`（送件包牢、快照、`access` CLI）、改 `spec/aos-agent/tools.md`（ls/add/rm/alias）、`cli.md` 用法表、`cli-check.md`、`send.md` §5.3 一句指過去。
- 新 `spec/aos-exec/aos-jail.md`（≤ 8 KB）。各資料夾 `history.md`（有的話）加一行 09-24 access-impl。
