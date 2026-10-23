# aos-exec

`aos-exec - 在工作區裡執行一個資料夾程式`（NAME，C-54 R1）

**一句話：`aos-exec [--ws WS] [--dotenv-override] XXX [args...]`——在工作區 WS 執行 XXX 這個程式：定好工作區、走進 XXX（cd、讀那裡的 `.env`）、挑出入口、備好環境變數、開跑。**
一個 lib（`lib/libaos-exec.a`，公開標頭 `aos/exec.hpp`）加一支薄薄的命令列（`bin/aos-exec`，只叫 `run_cli`）。連 aos-util、aos-directive（解單子、argv 陣列與 JSON `.env` key 的指示詞）、inst（C 的 libaos，靜態版 `inst-static`）。全家慣例見 [impls/README.md](../README.md)。
inst 是 C lib、沒有命令列，inst 單子由 aos-exec 在行程內跑（ideas § 20）。[aos-loop](../aos-loop/README.md)、[aos-fsm](../aos-fsm/README.md) 的每一次、[aos-daemon](../aos-daemon/README.md) 的子 loop，都是在 fork 出來的子行程裡呼叫這個庫的 `run_cli`（等同起一支 `aos-exec -- 目標 參數...`；10-21 晚）。

像在門口換好鞋再進屋：它只負責帶路和換鞋，進屋之後做什麼是入口的事。`.env` 就是門口那張「進來先把這些設好」的紙條。入口是可執行檔或 argv 陣列時它不留在屋裡（exec，結束碼就是入口的碼）；
入口是 inst 單子時它留在門口當監工：在行程內交給 libaos 起子程式（自成行程群組）、把收到的訊號轉給整群、等它結束，再以子程式的碼結束。

```sh
aos-exec --ws ws agent        # 跑 agent/_entry（或 agent/_entry.json），工作區 ws
aos-exec cfg.json#/tools/stamp a b   # 跑 cfg.json 裡 /tools/stamp 那個值，沿用 $AOS_WS，參數 a b
echo hi | aos-exec tool              # tool/_entry.json 是 {"argv": ["cat"]}：單子沒寫串流＝接呼叫者的，印 hi
```

規則出處：`proto8/thinking/2026-10-19-ideas.md` § 14～§ 20、`2026-10-21-ideas.md` § 1～§ 7（旗標、`.env`、入口順序、一路往下、`AOS_CO`）；行為比照 `proto8/bin/aos-exec`（Python，10-21 晚版），inst 單子比照 `proto8/bin/aos_inst.py`。

## 用法

```
aos-exec [--ws WS] [--dotenv-override] XXX [args...]
```

- **旗標**寫在 XXX 前面；**第一個不是旗標的參數**（不以 `-` 開頭，或就是 `-`）就是 XXX，之後全部**原樣**給入口（XXX 後面的 `--ws`、`--` 也是 args）。
  `--` 結束旗標（XXX 可以 `-` 開頭：`aos-exec -- -p`）。帶值的旗標寫 `--ws V` 或 `--ws=V`；重複給＝最後一個算。
  不認得的旗標＝`FlagUnknown`；旗標缺值、沒給 XXX、不帶值的旗標寫成 `--dotenv-override=V`＝`ArgumentsBad`，stderr 一行 `aos-exec: ArgumentsBad usage: aos-exec [--ws WS] [--dotenv-override] XXX [args...]（原因）`。
  旗標解析在 aos-util 的 `aos/cli.hpp`（`parse_cli`，loop／fsm／daemon 共用）；aos-exec 的旗標表有 `--ws`（10-21 ideas § 3）與不帶值的 `--dotenv-override`（10-22）。
- **`--dotenv-override`**（10-22 ideas § 3，不帶值、重複給＝一樣）：`.env` 蓋掉已有的環境變數。只管這一次起來的 aos-exec：這一跳一路往下讀的每份 `.env`
  （資料夾、`$AOS_ENTRY` 沿路、JSON 物件的 `.env` key）都吃；字串轉向（全新一跳）、argv 陣列插進去的 aos-exec、loop／fsm／daemon 每次叫的 aos-exec 都不吃，要的人自己在 argv 寫。
- **`--ws WS`**：沒給、`-` 或空＝沿用 `$AOS_WS`，沒設用 `.`；給路徑就用那個（相對於呼叫當下的 cwd）；不是資料夾＝`WsMissing`。
  舊寫法 `aos-exec XXX WS args...` 已不認：XXX 後面的 WS 現在是 args。
- **XXX**：資料夾、檔、或 `檔#/指標`；相對路徑從呼叫當下的 cwd 算。
- **args** 原樣接在入口後面；stdin 不讀，原樣給入口。
- **優先順序**（10-22 改）：沒 `--dotenv-override`＝旗標 ＞ 原本的環境 ＞ `.env` ＞ 預設；有＝旗標 ＞ `.env` ＞ 原本的環境 ＞ 預設
  （例：工作區＝`--ws` ＞ 外面的 `$AOS_WS` ＞ `.env` 的 `AOS_WS` ＞ `.`；`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO` 在讀 `.env` 前已設好，不加旗標 `.env` 改不了）。

### 一跳（hop）：走進去、讀 `.env`、挑入口

一次 aos-exec＝一跳或好幾跳（字串轉向會接下一跳）。每一跳照這個順序（10-21 ideas § 5～§ 7）：

1. **定工作區**（`check_ws`）：照上面 `--ws` 的規則，不是資料夾＝`WsMissing`。
2. **認出 XXX**（`locate`）：先在第一個 `#` 切開（`#` 後面一定要 `/` 開頭，不然＝`EntryBad`；指標照 RFC 6901，`~0`＝`~`、`~1`＝`/`），再看路徑：
   - **資料夾** → 記下來，入口**這時還不挑**（要等讀完 `.env`）。資料夾帶 `#/`＝`EntryBad`。
   - **檔** → 就用它。
   - **不在、basename 沒有 `.`** → 補找 `XXX.json`；都沒有＝`EntryMissing`。
3. **建 stack**（`setup_stack`）：`AOS_STACK` 沒設＝`$AOS_WS/.stack/`（10-23 改名，原 `.aos/`），有設沿用（相對於呼叫當下的 cwd）；mkdir -p、轉絕對、結尾 `/`；export `AOS_WS`、`AOS_STACK`。
   只有這一步算出來的會建、會轉絕對；之後 `.env` 設的 `AOS_*` 照字面用（`.env` 改 `AOS_WS` 時 `AOS_STACK` 不跟著搬，風險自擔，ideas § 6 J8）。
4. **走進去**（`enter`）：資料夾（或檔所在的資料夾）——`AOS_CF`、`AOS_CD` 先設成它（XXX 是檔時 `AOS_CF`＝那個檔）、`AOS_CO` 設空、**cd 進去**、
   **讀那裡的 `.env`**（見下面）、**旗標蓋回**（`--ws` 給的值再寫回 `AOS_WS`）。走進去那一刻 `$AOS_ENTRY` 是 `.env`＝那份 `.env` 不讀成環境（它就是入口）。
5. **資料夾：讀完 `.env` 才照「當下的」`$AOS_ENTRY` 挑入口**（沒設或空＝`_entry`；所以 `.env` 設 `AOS_ENTRY` 有用）：
   - `$AOS_ENTRY` **一段段走**：`sub/run`＝走進 `sub/`（cd、讀它的 `.env`、旗標蓋回）再挑 `run`；沿路的資料夾都走進去（由外到內），中間某段不是資料夾＝`EntryMissing`。
     空的段不算一段（尾巴的 `/`、`//`；`_entry/`＝`_entry`，全是 `/`＝`.`）；`.` 不算走進新資料夾、不重讀 `.env`。
   - 挑到的是**資料夾**＝再走進去，照當下的 `$AOS_ENTRY` 再挑，**一路往下**（所以資料夾贏過旁邊同名的 `.json`）；
     走回走過的資料夾（例 `AOS_ENTRY=.`、`sub/../sub/run`、捷徑繞回上層）＝`EntryBad`（資料夾繞圈）。
   - 挑到的不在就補找 `名字.json`；都沒有＝`EntryMissing`（這個錯在建好 stack、讀完 `.env` 之後才報，所以 `.env` 壞會先報）。
   - 入口檔是指到別處的捷徑：cd 到實際的資料夾，那邊的 `.env` **不讀**。
6. **判種類**（`classify`，見下面「種類」）；沒 `argv` 的 JSON 物件在這一步也當資料夾一路往下。
7. **重設 `AOS_CF`／`AOS_CD`／`AOS_CO`**＝實際的檔、它所在的資料夾、入口在檔裡的指標。**最後讀的那一份** `.env`（檔或 JSON `.env` key）自己設了其中哪個，那個就不蓋；更早讀的設的不算（ideas § 7 K3）。
8. **開跑**（`launch`）；種類是字串轉向就接下一跳（見「種類」的字串那條）。

### 種類（classify）

解開捷徑得到實際的檔之後，依序：

1. 有 `+x` → **可執行檔**，直接 exec（`#!` 由 kernel 處理；沒有 `#!`、exec 得到 ENOEXEC 時同 glibc `execvp` 改用 `/bin/sh 那個檔 args...` 跑，ideas § 22）。帶 `#/`＝`EntryBad`。
2. 否則當 JSON 讀（第一行 `#!` 跳過、照指標取值；不是 JSON＝`EntryBad`、指標指不到＝`EntryMissing`），看那個值：
   - **沒 `argv` 的物件** → **當資料夾**（10-21 ideas § 6；原「只往下一層」撤回）：進去那一刻 `$AOS_ENTRY` 不是 `.env` 就先套它的 **`.env` key**
     （`{"名字": 值}`，值可放指示詞 `$env`／`$ref`、`$ref` 從那份檔所在的資料夾算；解完不是字串的那一項靜默跳過；`.env` 整個解完不是物件＝整個跳過；
     字串值照 `.env` 檔的 `${名字}` 規則；指示詞解不開、名字不合、`${名字}` 沒設＝`DotenvBad`）、旗標蓋回，再取 `[$AOS_ENTRY]`（沒有這個 key＝`EntryBad`）；
     取出來又是沒 `argv` 的物件就再走進去，一路往下（挑的時候不解 `$ref`，走的是那份檔的樹，不會無限）。`$AOS_ENTRY` 是 `.env`＝`.env` 那格就是入口。
     JSON `.env` key 裡的指示詞只看進入物件之前的環境，同物件裡互相引用用 `${名字}`（ideas § 7 K4）。
   - **陣列**（不空；元素是字串或指示詞 `$env`／`$ref`，10-20 ideas D2、D8）→ 設好環境變數、讀完 `.env`、cd 進去之後解指示詞（`$ref` 從入口檔所在的資料夾算；
     解不開或解完不是全字串＝`EntryBad`），**`argv[0]` 帶 `/` 又 exec 不了**（不是 `+x` 的一般檔：資料夾、沒 `+x` 的檔、不在；或帶 `#/`）＝前面插 `aos-exec`
     （10-20 ideas D3～D4、10-21 ideas § 3 第 9 點：`["tools/stamp", "a"]`＝`aos-exec tools/stamp a`，**a 是 args**；要換工作區自己寫 `["aos-exec", "--ws", WS, "tools/stamp", "a"]`；`aos-exec` 照 PATH 找）；
     再當 argv 交給 glibc 的 `execvp`：`argv[0]` 有 `/` 就直接用（相對的從 cd 進去的地方算），沒有就照 PATH 找
     （空的一段＝目前資料夾；沒設 PATH＝`/bin:/usr/bin`）。`+x` 但沒有 `#!` 的檔改用 `/bin/sh` 跑，跟可執行檔入口一致（ideas § 22，使用者「乙」）。
     PATH 某段的檔沒 `+x`（EACCES）就換下一段，都找不到＝`LaunchFailed`。
   - **有 `argv` 的物件** → **inst 單子**，行程內跑（見下面「inst 單子」）；單子裡就算有 `.env` key 也不套（單子自己有 `envs`）。
   - **字串** → 路徑轉向＝**交給下一層、全新的一跳**（10-21 ideas § 4 E4，C-52）：相對路徑從寫著它的檔所在的資料夾算；旗標**不帶過去**（下一跳的 `--ws` 當沒給，
     但這一跳蓋回環境的 `AOS_WS` 還在）、args 照接、下一跳自己 cd、讀它那裡的 `.env`（疊在這一跳設好的環境上、後讀的贏）。
     轉向到同一個資料夾的檔，同一份 `.env` 會再讀一次（`PATH=${AOS_CD}/bin:${PATH}` 會疊兩次，照規則接受，ideas § 7 K1）。
     繞圈偵測跨跳沿用同一條鏈（`Chain`）：繞回走過的位置（檔＋指標）＝`EntryBad`（訊息列出 `a → b → a`）；不設深度上限。這是「每層只管自己」的唯一例外（K2）。
   - 其他（數字、null、空陣列…）→ `EntryBad`。

### `.env`

格式照 `src/env/dotenv.cpp`（10-21 ideas § 4.3，N-59 第 4 件；10-22 ideas § 3 改成 dotenv 基礎子集，照 bin 版逐案比過、跟 python-dotenv 一樣）：

- 一行 `[export ]名字=值`；去前導空白（只認 ASCII 空白）、去行尾 `\r` 後，空的或 `#` 開頭＝跳過；行首 `export `（export 後接空格／tab、再接不是 `=` 的字）忽略；
  `=` 只切第一個、兩邊空白忽略（名字後面只認空格／tab）。
- 值（`env_value`）：沒引號＝去頭尾空白，第一個「空白＋`#`」起是行尾註解（`a#b`、`#fff` 照字面，同 python-dotenv）；`=` 後空白再接 `#`（`X= # c`）＝`DotenvBad`。
  單、雙引號只剝一對、不跳脫、不跨行，引號後只能接空白或 `#` 註解；雙引號裡展開 `${名字}`、單引號照字面；引號沒收尾、引號裡有 `\`、單引號裡有 `${`、引號後有雜字＝`DotenvBad`。
  值頭尾與 `#` 前面的空白照 python-dotenv 認 Unicode 空白（Python `str.isspace` 那一套，含全形空白、不換行空白；aos-util 的 `aos/text.hpp`）。不支援 unset、多行、跳脫、`${X:-y}`。
- **預設不蓋**：開始讀一份 `.env` 那一刻環境裡已有的名字，那一行跳過（格式、`${名字}` 照驗，壞了照報錯）；同一份檔裡同名照樣後者贏。加 `--dotenv-override`＝蓋。
  JSON 物件的 `.env` key 格式不變（引號、註解那些 JSON 自己有，不套），只套蓋不蓋。
- 名字要是 `[A-Za-z_][A-Za-z0-9_]*`，不合＝`DotenvBad`。
- 值只展開 `${名字}`，逐行（後面看得到前面設的、也看得到 aos-exec 剛算好的 `AOS_*`）；`${名字}` 沒設＝`DotenvBad`、`${` 後面不是 `名字}`＝`DotenvBad`；孤零零的 `$`（含 `$名字`）原樣留；值裡有 NUL＝`DotenvBad`。不自動轉相對路徑。
- 什麼都能設，包括 `AOS_*`（風險自擔；讀 `.env` 前已設的要加 `--dotenv-override`）；cd 已經做了，改 `AOS_CD` 不會再 cd。旗標等整份讀完才蓋回，所以 `.env` 自己設了 `AOS_WS`、後面又寫 `${AOS_WS}` 拿到的是 `.env` 的值——建議 `.env` 不要設有旗標的變數（K5）。
- 沒有 `.env`＝什麼都不做；有但讀不到（權限、它是資料夾、壞掉的捷徑）也＝`DotenvBad`（原因開頭 `.env 讀不到`）；不是 UTF-8（含帶 BOM：BOM 不去掉，第一行名字不合）＝`DotenvBad`（原因開頭 `.env 壞`）。
  錯只印檔名和行號（JSON `.env` key：只印「檔#指標 的 .env」），**絕不印值**、也不印名字。權限不檢查。

### 環境變數（照 P-39 分三類；六個 `AOS_*` 加 PATH）

| 變數 | aos-exec 做什麼 | 類別 |
|---|---|---|
| `AOS_ENTRY` | aos-exec 自己只讀、不設；沒設（或空）＝`_entry`。資料夾裡與 JSON 裡用同一個名字；每次挑入口都重讀（`.env` 可能剛改過它） | 繼承 |
| `AOS_WS` | 每跳設：WS 的絕對路徑（`--ws` 給的，每讀完一份 `.env` 都蓋回去） | 叫別人時明給 |
| `AOS_STACK` | 沒設＝`$AOS_WS/.stack/`（10-23 改名，原 `.aos/`）；有設沿用（相對於呼叫當下的 cwd）；都 mkdir -p、轉絕對、結尾 `/` | 叫別人時明給 |
| `AOS_CF` | 每跳覆寫：實際被執行的檔（解開捷徑的絕對路徑，不帶 `#/…`；往下走進 JSON 物件時不變；字串轉向後＝最後那個檔）。走進資料夾時先＝那個資料夾 | 每層覆寫 |
| `AOS_CD` | 每跳覆寫：`AOS_CF` 所在的資料夾＝cd 進去的地方 | 每層覆寫 |
| `AOS_CO` | 每跳覆寫（10-21 晚新增，aos current obj）：入口在那份 JSON 檔裡的位置，JSON 指標、不帶 `#`（例 `/a/_entry`；`檔#/指標` 也算在內，之後每挑一格接 `/` 加照 `~0`／`~1` 跳脫的 key）；整份檔就是入口、或可執行檔＝空。走進資料夾時先設空 | 每層覆寫 |
| `PATH` | aos-exec **不動**，原樣傳下去（ideas § 24「也套用，都不動path吧」）；要改由 `.env` 自己寫（`PATH=${AOS_CD}/bin:${PATH}`）。入口裡要寫 `aos-exec 別的`、`aos-loop`…，由呼叫者事先把那幾支的 `bin/` 放進 PATH | 繼承 |

最後讀的那一份 `.env` 自己設了 `AOS_CF`／`AOS_CD`／`AOS_CO` 的，挑完入口不蓋（見上面一跳的第 7 步）。

### inst 單子

格式照 `proto8/bin/aos_inst.py`（10-19 版）：**只認 10 個 key，其他一律忽略**。

| key | 型別 | 沒寫 |
|---|---|---|
| `argv` | 非空字串陣列（必填）；args 接在後面 | — |
| `cwd` | 字串路徑，從入口所在的資料夾算 | 入口所在的資料夾 |
| `envs` | `{名: 字串}`，疊在現有環境上 | 沿用現有環境 |
| `stdin`／`stdout`／`stderr` | 字串路徑（`null`＝沒寫），從解出來的 `cwd` 算；stdout／stderr 覆寫 | **接呼叫者的**（aos-exec 自己的 fd 0／1／2） |
| `stdout_append`／`stderr_append` | true／false：改附加 | false |
| `timeout_ms` | 正整數或 `null`：到了先 SIGTERM **整群** | 不限 |
| `grace_ms` | 非負整數：SIGTERM 後等多久再 SIGKILL 整群（0＝直接 SIGKILL） | 2000 |

- **先解指示詞再驗**：單子裡任何位置的 `{"$env": 名}`、`{"$ref": "檔#/指標"}`（位置只認 `#/`，10-23 刪 `$at`），可帶 `$path`（`join(值, $path)`）、`$prefix`（接在前面）
  先換掉（aos-directive，規則見它的 README；N-45，10-20 改版；`$path` 10-21 傍晚起是字串拼接）。在 aos-exec 設好六個環境變數、讀完 `.env` 之後才解，所以讀得到 `AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO` 與 `.env` 設的值
  （例 `"stdout": {"$env": "AOS_STACK", "$path": "out"}`）。`$ref` 的相對檔名從入口檔所在的資料夾算（命令列不給 `run_inst` 的 `ref_base`，沿用 `base_dir`＝入口檔所在的資料夾）。
- **`argv[0]` 帶 `/` 又 exec 不了＝前面插 `aos-exec`**（10-20 ideas D3；從解出來的 `cwd` 看），`aos-exec` 照子程式的 PATH 找，找不到＝`LaunchFailed`（`CommandMissing`）。
- **型別不對**＝`EntryBad`（單子就是入口）；指示詞解不開（`$env` 沒設、`$ref` 讀不到或指到資料夾、指不到、繞圈）＝`DirectiveBad`；libaos 起不來＝`LaunchFailed`，原因是 libaos 的名字開頭
  （`CommandMissing`、`CommandBad`、`CwdMissing`、`OpenFailed`…）；收不到結果＝`Internal`。這幾種錯的原因前面都再加「單子跑不起來：」（同 bin 版），代號照舊分種類。
- **不認的 key**：除了打錯的，impls/aos-inst 那代認得的 `id`、`envs_clear`、`cwd_mkdir`、`stdout_mkdir`、`stderr_mkdir`、`stderr_merge` 在這裡也**被忽略、不報錯**——
  寫 `stderr_merge: true` 不會合併；寫 `cwd_mkdir: true` 不會建資料夾，cwd 不在就 `LaunchFailed`（測試把這個現象釘住）。
- **監工**：子程式自成行程群組（libaos `new_session`）；跑的期間 aos-exec 收到 SIGINT／SIGTERM／SIGHUP 自己不死，轉給**整個群組**，
  第一次轉過之後過 `grace_ms` 還沒結束就 SIGKILL 整群；逾時由 libaos 管（也是整群）。子程式結束後 aos-exec **以子程式的碼結束**（被訊號停掉＝128＋N，
  例 SIGTERM＝143，透明轉交 N-43）。子程式沒有控制終端，讀不了終端（P-36 已接受）。
- **`argv[0]` 由 libaos 跑**（glibc 的 `execvp`）：所以單子裡 `+x` 但沒 `#!` 的檔會被 glibc 改用 sh 跑——跟上面可執行檔、argv 陣列入口一樣（ideas § 22）。
- **JSON 入口不要寫 `+x`**：拿掉 `+x` 的 `_entry`（第一行 `#!` 會被跳過）就能當單子跑。也**不要**寫成 `#!/usr/bin/env aos-exec` 再加 `+x`：
  `+x` 的檔 aos-exec 會 exec 它、kernel 又叫 aos-exec……原地無限 exec。aos-exec 不讀 `+x` 檔的內容去擋。（舊理由「`./_exec foo` 的 foo 會被當工作區」10-21 起沒了：XXX 後面都是 args。）

## 元素

```
 main ──▶ run_cli（解旗標）──▶ hop（check_ws → locate → setup_stack → enter：cd、load_env → 挑入口 → classify → 重設 CF／CD／CO）──▶ launch（exec／run_inst）
                                  ▲                                                                                       │
                                  └──────────────────── 字串轉向＝全新的一跳（旗標不帶、args 照接、同一條 Chain）◀────────────┘
```

| 檔 | 做什麼 |
|---|---|
| `include/aos/exec.hpp` | 公開介面：`run_cli(args)`（等同命令列；自己印錯、回 1；可執行檔／argv 陣列 exec 掉、成功不回來；單子回子程式的碼）、`run_inst`、`argv0`、`Result`；代號 `aos::exec::code::*`（含 `WsMissing`、`DotenvBad`）。`Result::received`＝跑的期間轉給子程式的第一個訊號 |
| `src/cli/cli.hpp`、`cli.cpp` | `run_cli`：aos-util 的 `parse_cli`（旗標表目前只有 `--ws`）→ 一跳跳走（`hop`；字串轉向接下一跳）→ `launch`；自己的錯印一行「aos-exec: 代號 原因」、回 1 |
| `src/common/common.hpp` | `using`、`entry_name()`（`$AOS_ENTRY`，每次重讀）、找到的入口 `Kind`、`Found` |
| `src/env/env.hpp`、`env.cpp` | `check_ws`（WS 規則、不是資料夾 `WsMissing`）、`setup_stack`（`AOS_STACK`、export `AOS_WS`／`AOS_STACK`） |
| `src/env/dotenv.cpp` | `load_env`（讀 `資料夾/.env` 逐行套進環境）、`json_env`（沒 argv 的 JSON 物件的 `.env` key）、`set_env`（一個 `名字=值`，只展開 `${名字}`）；UTF-8 檢查；錯只印位置 |
| `src/find/find.hpp`、`find.cpp` | `hop`（一跳：定工作區 → `locate` → 建 stack → `enter` → 資料夾一段段挑入口、一路往下、資料夾繞圈 → `classify` → 重設 `AOS_CF`／`AOS_CD`／`AOS_CO`）、`locate`（資料夾、檔、`檔#/指標`、補 `.json`）、`enter`（設 CF／CD／CO、cd、讀 `.env`、旗標蓋回）、`entry_name`、`Layer`（旗標蓋回）、`Chain` |
| `src/find/classify.cpp` | `classify`：`+x` 判斷、讀 JSON（跳 `#!`、照指標取值）、沒 argv 的物件當資料夾（`.env` key、取 `[$AOS_ENTRY]`、一路往下、組 `AOS_CO`）、種類、字串轉向繞圈偵測 |
| `src/inst/inst.hpp` | inst 元素的內部介面：`Inst`、`parse_inst`、`LibInput`、`build_lib_input`、訊號函數 |
| `src/inst/fields.cpp` | 單子 → `Inst`：10 個 key 驗型別（順序照 `aos_inst.py` 的 parse） |
| `src/inst/lib_input.cpp` | `Inst` → libaos 的 `aos_inst_input_t`：絕對路徑、環境、串流沒寫＝`inherits`、`new_session` |
| `src/inst/signals.cpp` | signalfd 收三個訊號、`killpg` 轉給整群、grace 到了 SIGKILL 整群 |
| `src/inst/run.cpp` | `run_inst`：解指示詞 → 驗 → 擋訊號 → `aos_inst_start` → 工人執行緒 `aos_inst_wait`、主執行緒轉訊號 → `Result` |
| `src/launch/launch.hpp`、`launch.cpp` | `launch(Found, args)`（cd 已在 hop 做完；可執行檔、argv 陣列都 `execvp`，沒 `#!` 由它改用 `/bin/sh`；argv 陣列先解指示詞、`argv0`；inst 單子 `run_inst`，錯的原因開頭加「單子跑不起來：」）、`argv0` |
| `src/main.cpp` | 命令列：只叫 `run_cli` |

## 為什麼這樣做

- **`run_cli` 會動行程全域狀態（chdir、setenv）**：`.env` 要在挑入口之前讀、挑入口又要看讀完之後的 `$AOS_ENTRY`、每走進一層都要 cd 和 setenv，
  拆不成「先純計算、最後才動全域」的幾步（10-21 晚以前公開的 `find_entry`／`resolve_ws`／`prepare_env`／`apply_env`／`launch`／`Entry`／`Env` 因此收進內部，改成 `check_ws`／`setup_stack`／`hop`／`launch` 這幾個內部函數）。
  所以長命的呼叫者不在自己的行程裡叫它：aos-loop、aos-fsm 的每一次、aos-daemon 的子 loop 都是 **fork 出來的子行程**裡呼叫 `run_cli`，
  效果等同起一支 `aos-exec -- 目標 參數...`，父行程的 cwd 與環境不受影響。
- **AOS_STACK 在 chdir 之前算**：有設的相對路徑要從呼叫當下的 cwd 算。WS 的檢查在認出 XXX 之前、建 stack 在認出 XXX 之後（錯誤先後同 bin 版），所以拆成 `check_ws`、`setup_stack` 兩個。
- **字串轉向是全新的一跳**：C-52「每層只管自己」——下一層自己定工作區、cd、讀 `.env`；這一層的旗標不帶過去。唯一的例外是繞圈偵測沿用同一條鏈，當安全網（ideas § 7 K2）。
- **`.env` 的錯不印值**：`.env` 常放 API key，錯誤訊息只說哪個檔第幾行、什麼原因。
- **可執行檔、argv 陣列都用 glibc 的 `execvp`**：`+x` 沒 `#!`（ENOEXEC）由它改用 `/bin/sh` 跑，三種入口（含 inst 單子的 `argv[0]`）一致（ideas § 22）。
  aos-exec 自己沒有 fork，不必守「fork 後只能呼叫 async-signal-safe」那條（loop／fsm／daemon 在 fork 後呼叫 `run_cli`，是 exec 的替身：子行程是單執行緒的，且本來就要做完 `.env`、cd 再 exec）。
- **inst 單子留在行程裡**：單子的逾時、整群收掉、轉訊號總得有人做，而 inst 只是 C lib、沒有自己的命令列（§ 20），所以 aos-exec 當監工；
  可執行檔與 argv 陣列沒有這些欄位，直接 exec、少一層行程。
- **單子 JSON 的解析放這裡、不進 C 庫**（使用者 10-19 拍板）：libaos 維持純 C、不讀 JSON、零 malloc、給 FFI。
- **`$env` 在 setenv、讀完 `.env` 之後解**：單子要讀得到 aos-exec 剛設的 `AOS_STACK`／`AOS_CD` 與 `.env` 設的值（10-21 ideas § 4 E1：`.env` 一直有效到真正開跑）。
- **`run_inst` 進出擋／還原訊號遮罩**：單執行緒的 CLI 不用另外做事；多執行緒的呼叫者要在開執行緒前自己把三個訊號擋好。
  轉送用 `killpg`（沒有 pidfd 可以代表一整群）；工人收完屍就停止轉送，避免群組號被別人重用時送錯。

## 錯誤代號

自己出錯：stderr 一行 **`aos-exec: 代號 原因`**、退 1（例 `aos-exec: EntryMissing 入口不存在：nope`）。照 N-60／P-21「程式名: 原因」，代號放開頭給測試認；
代號後面的原因開頭跟 bin 版一樣（`工作區不存在`、`入口不存在`、`入口壞`、`起不來：X（原因）`、`單子跑不起來：`、`.env 讀不到`、`.env 壞`、`建不了 AOS_STACK`、`usage: …`）。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`（共用） | 沒給 XXX、旗標缺值、不帶值的旗標帶了值（原因 `usage: aos-exec [--ws WS] [--dotenv-override] XXX [args...]（原因）`） |
| `FlagUnknown`（共用） | 不認得的旗標 |
| `WsMissing` | WS 不是資料夾 |
| `EntryMissing` | 資料夾／檔／`.json` 補找都沒有；多段 `$AOS_ENTRY` 中間某段不是資料夾；`#/` 指標指不到 |
| `EntryBad` | 既不可執行也不是 JSON；JSON 種類不對（沒 argv 的物件裡沒有 `[$AOS_ENTRY]`、數字、空陣列…）；`#` 後面不是 `/`；資料夾或可執行檔帶 `#/`；字串轉向繞圈；資料夾繞圈；argv 陣列的指示詞解不開或解完不是全字串；inst 單子欄位型別不對 |
| `DotenvBad` | `.env` 在但讀不到（權限、是資料夾、壞掉的捷徑）；`.env` 壞：沒有 `=`、名字不合、`${` 寫法不對、`${名字}` 沒設、值有 NUL、不是 UTF-8（含 BOM）；JSON `.env` key 的指示詞解不開、名字不合、`${名字}` 沒設。只印位置、不印值 |
| `DirectiveBad`（aos-directive 透傳） | 單子裡的指示詞解不開：`$env` 沒設、`$ref` 讀不到／不是 JSON、指不到、繞圈（寫法不合不算錯，物件原封不動，之後照欄位規則判） |
| `MkdirFailed`（共用） | AOS_STACK 建不了 |
| `LaunchFailed`（共用） | exec 失敗（ENOENT、EACCES…；原因 `起不來：X（原因）`）；inst 單子 libaos 起不來（原因 `單子跑不起來：` 接 libaos 的名字） |
| `Internal`（共用） | 照理不會發生的例外；inst 單子收不到結果（libaos 的 `WaitFailed`／`KillFailed`）、準備轉訊號失敗 |

代號照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)；統合前 `ArgumentsBad`／`FlagUnknown` 都叫 Usage、`WsMissing` 叫 WorkspaceMissing、`DotenvBad` 分成 EnvReadFailed（讀不到）與 EnvBad（壞）；libaos 的 `CommandMissing`／`CommandBad` 叫 CommandNotFound／CommandNotExecutable；指示詞的 `$at` 叫 at（`$at` 同日再刪，位置只認 `#/`）。

入口跑起來之後的結束碼不是 aos-exec 的錯：可執行檔與 argv 陣列是 exec（碼就是入口的）；inst 單子是子程式的碼（被訊號停掉 128＋N）。
所以入口自己退 1 跟 aos-exec 出錯分不出來時，看 stderr 那行有沒有 `aos-exec: ` 開頭。

## 跟 bin 版 `proto8/bin/aos-exec`（Python）的差異

規則照 bin 的 10-21 晚版，行為一樣；刻意不同的只有：

- （10-23 起不是差異）錯誤一行兩版都是 `aos-exec: 代號 原因`，代號與原因開頭一樣（bin 10-23 照這裡的代號補上）。
- inst 單子：bin 版在行程內 `aos_inst.run()`，這裡在行程內交給 libaos（C）、aos-exec 留著當監工——兩版都是 aos-exec 這一層留在行程裡。
- impls 沒有 `aos-inst` 命令列：P-28 的 (A)「`_entry` 第一行 `#!/usr/bin/env aos-inst`」與 (1)「小殼 `exec aos-inst _entry.json`」在這裡跑不起來；
  同一個檔拿掉 `+x` 就能用（第一行 `#!` 跳過、當單子跑）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

`ctest` 跑 `test_cli`（`tests/test_cli.py`，56 組，約 1 秒）。A～D 段用 `run(XXX, WS, args...)` 小工具，轉成新命令列 `aos-exec --ws WS XXX args...`；E 段直接用 `raw(...)` 給命令列。
A 段從 `proto8/tests/test_exec.py` 移植跟 aos-exec 本身有關的案例（靠 demo、aos-loop、aos-fsm 的不移植），
B 段是 § 14～§ 19 的新規則（含「exec 不留行程」：入口的 `$$`＝aos-exec 的 pid；`+x` 沒 `#!` 交給 sh；`$AOS_ENTRY` 指到資料夾＝走進去、沒 `argv` 的物件一路往下），
C 段是 inst 單子：結束碼轉交（3、10、SIGTERM＝143）、監工留在行程裡、shebang 開頭的非 `+x` 單子、args／`#/`／`_entry`／字串轉向、
串流接呼叫者的（`{"argv": ["cat"]}` 透傳 stdin）與寫檔／附加、`$env`＋`path`、逾時整群殺（`sh -c 'sleep 100 & …; wait'`）、
訊號轉給整群與 grace 後 SIGKILL（137）、單子壞的各種代號、不認的 key 被忽略；
D 段是 10-20 的指示詞與 argv（對照 `proto8/tests/test_directive_argv.py`、`test_directive_lenient.py`）：`$ref` 的 `#/`、`$at` 不作用、繞圈；argv 陣列放 `$env`／`$ref`、`$path`／`$prefix`、解不開＝入口壞；
argv[0] 帶 `/` 又 exec 不了＝交給 aos-exec（資料夾、JSON 檔、補 `.json`、`#/`、`+x` 檔照舊、第二個元素是 args、換工作區寫 `--ws`、沒 `/` 照 PATH、PATH 上沒 aos-exec）；
E 段是 10-21 的新規則（對照 `proto8/tests/test_exec_rules.py`、`test_exec_env.py`）：旗標（`--ws V`／`--ws=V`、重複給、蓋過 `$AOS_WS`、`-`／空＝沿用、XXX 之後不解析、舊的位置 WS 變 args、`--`、不認得、缺值、沒 XXX、usage 一行）、
`.env`（逐行、`${名字}`、`=` 只切第一個、沒有 `.env`；旗標 ＞ `.env` ＞ 外面；`${}` 沒設與各種壞法都不印值、不是 UTF-8、是資料夾）、
入口順序（`.env` 設的 `AOS_ENTRY` 有作用、多段 `$AOS_ENTRY` 沿路讀 `.env`、挑到資料夾一路往下、走回走過的資料夾）、
JSON 物件（`.env` key、一路往下、`AOS_CO`、`檔#/指標` 算進 `AOS_CO`、整份檔＝空、`.env` key 設 `AOS_ENTRY`、指示詞解不開）、轉向（下一層讀自己的 `.env`、旗標不帶過去）；
10-22 起靠「`.env` 蓋原有」的案例改成不加／加 `--dotenv-override` 各一份，另加 `e_dotenv_subset`（基礎子集的收下與壞的寫法、Unicode 空白、預設不蓋與同檔後者贏、
旗標重複給與 `=V` 錯、跳過的行照驗、轉向不吃旗標、JSON `.env` key 格式不變；對照 `proto8/tests/test_exec_dotenv.py`）。
測試的 `raw()` 把 aos-exec 的 `bin/` 放 PATH 最前面——aos-exec 不動 PATH（§ 24），入口裡要叫 `aos-exec` 由呼叫者放；`path_passed_as_is` 驗 PATH 原樣傳下去。

**拿 `proto8/tests` 對照**（10-23 起不用再對照：Python 版刪了，`proto8/tests` 直接跑這支與 aos-loop、aos-fsm、aos-daemon 的 `bin/`〔`proto8/tests/aos_bins.py`〕，那兩個字面差別的測試改成照這裡的字面，全過；以下是 10-23 前的做法與結果）（手動，不進 ctest）：把 `proto8/tests` 複製到暫存資料夾，旁邊的 `bin/` 換成指到 impls 四支（aos-exec、aos-loop、aos-fsm、aos-daemon）的捷徑（impls 沒有的 `aos-tick` 與 `aos_*.py` 指到 `proto8/bin` 的；`proto8/demo` 也放一份捷徑在旁邊），
直接跑（10-23 起 bin 也帶代號，不用再抹；`tests/own_error.py` 會逐行對代號，impls 的代號也全對得上）：
10-23 全套只剩 2 個不過（10-23 命名統合後再跑一次，245 個，還是這 2 個；設定檔讀不到那行的原因照 Python OSError 寫成 `[Errno 2] …`，`own_error.py` 靠它分 CfgMissing），都是 inst 單子錯誤訊息的字面（`test_inst` 要原因開頭是 key 名、這裡是「單子的 key…」；`test_directive_argv` 的 D1 要訊息裡有檔名、
這裡 libaos 的 `OpenFailed` 不帶檔名），行為一樣；照現狀不改（10-23 使用者）。裝了 python-dotenv（`pip install --target` 到暫存資料夾、`PYTHONPATH` 指過去）時 `test_exec_dotenv` 的逐案對照也過。
