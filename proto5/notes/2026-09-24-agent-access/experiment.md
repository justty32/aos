← [agent-access 提案](README.md)

# 小實驗（2026-09-24，Manjaro，約 5 分鐘）

腳本在 [`exp/`](exp/)，原本跑在 scratchpad（路徑寫死，要重跑改開頭的路徑）。**沒起 daemon／kernel、沒問模型**，所以沒驗完整的 tick、排隊與崩潰恢復流程：
直接呼叫 aos-agent 送件時用的 `aos_inst.load_obj`／`tool_inst()`，再用真的 `aos-exec` 跑工具。
base 工具包用的是另一隊 worktree 當下的快照（還在變）。擺設：`amy/`（有 `secret.txt`、`info.json`）、`ws-A/`、`ws-B/`、`ws-A/sneaky -> ../amy`（符號連結）。

## 1. 現有指示詞能不能把 workspace 寫在一個檔、工具去取（[exp1.py](exp/exp1.py)、[exp1b.py](exp/exp1b.py)）

| # | 寫法（工具的 `_meta`） | 結果 |
|---|---|---|
| 1 | `"cwd": {"$ref": "access.json#/ws"}`，`envs` 也 `$ref` 同一檔 | cwd 解成 ws-A ✔；**envs 那個 `$ref` 失敗**：cwd 換掉後，其他欄位的 `$ref` 改相對「新的 cwd」找檔（inst-posix §3.1 的規矩），去 ws-A 找 `access.json` 找不到 |
| 2 | 改 `access.json` 一行（ws-A→ws-B）再解 | 立刻變 ws-B ✔（`_meta` 每次送件都重解） |
| 3 | `_meta` 整份 `{"$ref": "../util-tools/x.meta.json"}`，共用檔裡寫 `"cwd": {"$ref": "access.json#/ws"}` | ✔ 而且 `access.json` 是相對**各自的 agent 家**找——共用檔自動吃每個 agent 自己的表 |
| 4、5 | `argv[0]` 想用「agent 家的絕對路徑」拼 | 現在沒有任何來源給得出家路徑（`$env` 找不到）；如果 aos-agent 解 `_meta` 時多給一個 `AOS_AGENT_HOME` 就行 |
| 6、7 | 把陣列（例如允許清單）`$ref` 進 `envs` 或 `argv` 一格 | `FieldTypeMismatch`：一格只能放一個字串，陣列攤不開 |
| 8 | `envs` 用 `{"$ref": "", "$at": "/cwd"}` 抄 cwd | 失敗，同 #1（抄到的是指示詞，又相對新 cwd 解） |
| 9、10 | 寫 `../amy/access.json`，或乾脆**不寫 cwd** | ✔；不寫 cwd 時所有 `$ref` 都相對 agent 家，最穩 |

**結論**：「amy 看到的名字 → 實際路徑」用 `$ref` 指一份小表就做得到，改一行下一次叫工具就生效。
坑（精確講，astra 建議 1）：`cwd` 裡的相對 `$ref` 以 agent 家為中心（#3 的結論只適用這一格）；`cwd` 解完之後，argv／envs 等其他欄位的相對 `$ref` 以**新的 cwd**為中心——還能用，只是中心變了（#9）；`$ref: ""` 指的是目前文件本身，不是路徑。陣列攤不開。

## 2. 路徑逃不逃得出去（[exp2.sh](exp/exp2.sh)）

base 工具根目錄設 ws-A，cwd＝amy 家（aos-agent 現在的做法）：

| 試 | read 工具 | bash 工具（沒隔離） | bash 關進 bwrap（只掛 ws-A 到 `/ws`） |
|---|---|---|---|
| `../amy/secret.txt` | `OutsideRoot` 擋下 | **讀到** `secret-of-amy` | `No such file or directory` |
| `sneaky/secret.txt`（符號連結） | `OutsideRoot` | **讀到** | `No such file`（連結指向牢外，懸空） |
| amy 的絕對路徑 | `OutsideRoot` | **讀到** | `No such file` |
| `echo $AOS_KERNEL_HOME $OPENAI_API_KEY` | — | **印出**（cpu 的環境整包繼承） | 空的（`--clearenv`） |
| `pwd` | — | 印真路徑 `…/ws-A` | `/ws` |
| 寫檔 `new.txt` | — | — | 寫進真的 ws-A ✔ |
| `curl localhost:4000` | — | — | 連不上（`--unshare-all` 連網路一起關；要網路加 `--share-net`） |

- read 的錯誤訊息裡帶**真路徑**（`outside the project directory /tmp/…/ws-A`）——別名會從這裡漏；關進牢裡就變成 `/ws`、`/work/ws`。
- bwrap 0.12.0 已裝（`/usr/bin/bwrap`），一般使用者就能用（user namespace 開著），開一次平均 **1.3 ms**。
- 同一串 bwrap 參數只把來源換成 ws-B：裡面看到的還是 `/ws`，`ls` 變成 `b.txt`。
- aos-exec 在外面先開好的 stdin／stdout 穿得過 bwrap：工具的 `work/N.in`、`work/N.out` 不用掛進牢裡。

## 3. 開放 amy 自己、但設定檔唯讀；工具改名（[exp3.sh](exp/exp3.sh)）

- 注意這只測了「當下」寫、刪、搬；牢外程式之後用 rename 換掉被蓋住的檔會怎樣沒測（astra 必修 3 待確認）。提案因此改成 `self` 整個唯讀。
- bwrap 先 `--bind amy /work/self`、再 `--ro-bind amy/access.json …`、`amy/info.json …` 蓋上去：
  寫 `self/note.txt` ✔；覆寫 access.json＝`Read-only file system`；`rm`／`mv` info.json＝`Device or resource busy`。
- `tools` 元素寫 `{"$ref": "../where.json#/util_tools"}`、那格的值是**路徑字串**：可以（第二輪補測，照常讀到資料夾裡的工具）。
- `info.json` 的 `tools` 放共用檔路徑 `"../util-tools/bash-edit-a.json"` 現在就行（模型看到 `bash-edit-a`）；
  放 `{"$ref": …}`＝`FieldTypeMismatch`（`$ref` 取到的是內容、不是路徑）；放 `{"$opt": {"as": "edit-a"}, …}`＝`UnknownOption: 這個位置沒有任何 $opt 選項`——**改名要規範新增這個選項**，程式在這一格本來就走 `$opt` 的解析，只是選項表是空的。

## 4. 只靠現有指示詞＋bwrap，走真的送件路徑（[exp4.py](exp/exp4.py)）

base 的 `bash`、`read` 的 `_meta.argv` 寫成 `["bwrap", …, "--bind", {"$ref": "access.json#/ws"}, "/work/ws", "--chdir", "/work/ws", …, "python3", "/opt/base/bash"]`，
`envs` 用 `clear`，base 的 `config.json` 寫 `{"root": "/work/ws"}`；用 aos-agent 的 `tool_inst()` 產生 inst、真的 `aos-exec` 跑：

| access.json | bash `ls` | bash 讀 amy（相對與絕對） | bash 看 `AOS_KERNEL_HOME` | read `../self/info.json` |
|---|---|---|---|---|
| `ws`＝ws-A | `a.txt sneaky` | 都失敗 | 空 | `OutsideRoot … /work/ws` |
| 改一行 → ws-B | `b.txt` | 都失敗 | 空 | 同上 |

**不改任何 aos 程式就做得到「一個 workspace、別名固定、bash 也關住、改一行就換」**。缺的是：多個資料夾要一個一個寫進每支工具的 argv（七支工具各寫一次），這就是完整版要補 `aos-jail` 的原因。
