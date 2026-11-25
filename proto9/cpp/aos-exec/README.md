aos-exec（proto9）：從 proto8 的 aos-exec 抄進來、拿掉 `AOS_STACK` 與 inst 單子的「執行一個資料夾程式」小工具（C++20，不連 proto8 任何東西），其餘行為照舊，等下一輪再瘦。

# aos-exec（proto9，11-25）

← [proto9](../../README.md)｜前身：[proto8 aos-exec](../../../proto8/cpp/aos-exec/README.md)（規則全文在它的 `docs/01..05`）

## 它是什麼、跟 proto8 那支差在哪

`aos-exec [--ws WS] [--dotenv-override] XXX [ARGS...]`：XXX 是資料夾、檔、或 `檔#/指標`。它定好工作區（`AOS_WS`）、走進 XXX（cd、讀那裡的 `.env`）、照 `$AOS_ENTRY`（預設 `_entry`）挑出入口、設好 `AOS_CF`／`AOS_CD`／`AOS_CO`，然後 **exec** 入口（不留在中間，結束碼就是入口的、pid 也是同一個）。自己出錯時 stderr 一行 `aos-exec: error: 代號 原因`、退 1。

使用者 11-25 定的（原話）：aos-exec「抄進去瘦身」、「可能要大改」；proto9 不給 `AOS_STACK`；proc 入口先只收可執行檔與 argv 陣列。所以這一版只做了兩件事，其餘一行都沒改行為：

| 拿掉的 | 現在怎樣 |
|---|---|
| `AOS_STACK` | 沒有 `--stack`、`--stack-lazy`（連短名 `-s`）：給了＝`FlagUnknown`，原因多一句 `(proto9 has no AOS_STACK)`。不算預設值、不 export、不建任何資料夾（工作區裡不會冒出 `.stack`）、也不收空的 stack。呼叫者環境裡本來就有 `AOS_STACK` 的，原樣傳下去，aos-exec 不讀它（相對路徑不轉絕對、不在也不建）。`.env` 裡寫 `AOS_STACK=…` 就只是一個普通變數。 |
| inst 單子 | 有 `argv` 的 JSON 物件不再跑：`EntryBad`，原因 `bad entry: <檔[#指標]> is an inst sheet (a JSON object with argv); inst sheets are not supported in proto9`。`src/inst/`、aos-inst（C 庫）、跟著它們的時鐘、`timeout_*`、轉訊號、整群收、`run_inst`、`Result` 全部沒帶進來。 |

還留著的入口種類：有 `+x` 又看內容像程式的檔（`#!`、ELF、或整份不是 JSON）、非空 JSON 陣列（argv）；另外兩種「帶路」照舊：JSON 字串＝轉向（全新的一跳）、沒有 `argv` 的 JSON 物件＝當資料夾往下挑。

公開介面 `include/aos/exec.hpp` 只剩 `run_cli`（等同命令列，會 chdir、setenv，要在 fork 出來的子行程裡叫）與 `argv0`；錯誤代號收進內部的 `src/common/common.hpp`。

## 怎麼編、怎麼跑、怎麼測

```
cd proto9/cpp/aos-exec
make            # build/libaos-exec.a、build/bin/aos-exec；-Wall -Wextra 沒有警告
make test       # 另編測試用的 build/bin/resolve-check，再跑 python3 tests/run.py（全部）
python3 tests/run.py test_proto9_removed      # 只跑某一組
TMPDIR=~/.aos/scratch/xxx make test           # 測試的暫存夾放哪（照 Python tempfile 的 TMPDIR）
build/bin/aos-exec --help
```

argv 陣列的 `argv[0]` 帶 `/` 又 exec 不了時，會在前面插 `aos-exec` 再照 PATH 找；要用這條，`build/bin` 得在 PATH 上（測試自己會放）。

## 從哪裡帶進來什麼

全部是「抄過來再刪」，沒有新寫的邏輯；檔頭第一行都寫了出處。

| 這裡 | 從 proto8 哪裡 | 行數（這裡／原本） | 帶什麼、沒帶什麼 |
|---|---|---|---|
| `src/`（`cli`、`common`、`env`、`find`、`launch`、`main.cpp`）、`include/aos/exec.hpp` | `cpp/aos-exec` | 1,043／約 1,840 | 拿掉 `src/inst/`（675 行）、`setup_stack`／`drop_stack_if_empty`、旗標表的兩個旗標、`Kind::Inst` |
| `src/util/` | `cpp/aos-util`（`error`、`io`、`cli`、`files`、`text`，加 `dirs.cpp` 的 `is_dir`） | 583／1,048 | 只留 `Error` 與 5 個代號、`dumps`、`fail`、`parse_cli`、`usage_error`、`abspath`、`dirname`、`join`、`is_dir`、`read_file`、`split_hash`、`is_utf8`、`space_at`、`lstrip`、`rstrip`；`proc`、`clock`、`signals`、原子寫入、`load_cfg`、`parse_sub_cli`、`read_stdin` 都沒帶 |
| `src/directive/` | `cpp/aos-directive`（`directive.hpp`、`internal.hpp`、`env`、`resolve`、`ref`、`md`） | 1,615／1,635 | 只留 `resolve` 用得到的；`resolve_shallow`、`resolve_keys`、`md_ls`、`md_tree`、命令列沒帶。`ref.cpp` 拆出 `spot.cpp`，926 行的 `md.cpp` 拆成 `md.hpp`＋`md_text`／`md_blocks`／`md_walk` 三份（每檔 ≤ 300 行） |
| `../third_party/nlohmann/` | `cpp/third_party/nlohmann`（json.hpp 3.12.0、LICENSE.MIT、VERSION） | 單檔標頭，原樣 | proto9 第一份 third_party |
| `tests/data/*.json` | `py/tests/md_path_cases.json`（只留 get／missing 兩種案例）、`py/tests/ref_path_cases.json` | 資料 | 給 `test_directive_*` 用 |

## 測試（11-25 最後一次：75 條，75 過、0 敗）

`make test` 跑 `tests/run.py`（unittest，只用這個夾 `build/bin/` 裡的兩支）。

| 檔 | 條數 | 驗什麼 |
|---|---|---|
| `test_proto9_removed.py` | 12 | 這一版新加：拿掉的旗標都是 `FlagUnknown` 而且入口沒跑；沒有 `AOS_STACK` 時入口看不到它；工作區、資料夾裡不會冒出 `.stack`（含出錯時）；外面給的 `AOS_STACK`（相對、絕對、不在、空字串）原樣傳到入口、不建；inst 單子在檔、指標、物件裡、資料夾的 `_entry.json`、轉向之後、經插進去的 aos-exec、帶 `#!` 首行，一律 `EntryBad` |
| `test_cli.py` | 6 | 旗標只認 XXX 前面、XXX 後原樣給入口（抄 proto8 `aos-util/tests/test_parse_cli.py` 的 `test_exec_args_stay_raw`）、`--`、`--help`、`ArgumentsBad`／`FlagUnknown`／`WsMissing` 的整行 |
| `test_classify.py` | 6 | 抄 proto8 同名檔：種類看內容不只看 `+x`；`argv[0]` 是 `+x` 的 JSON 會插 aos-exec；其他 JSON 值 `EntryBad` |
| `test_entry_missing.py` | 3 | 抄 proto8 同名檔（原樣） |
| `test_ref_hash.py` | 6 | 抄 proto8 同名檔：入口裡的 `#/…` 指入口檔自己；原本用 inst 單子的兩條改成 argv 陣列 |
| `test_kept.py` | 16 | 這一版新加，給之後砍東西當警報：`.env`（展開、不蓋／`--dotenv-override`、錯不印值、Unicode 空白、JSON `.env` key）、`AOS_ENTRY` 多段、資料夾贏 `.json`、`.json` 補找、`#/` 與 `AOS_CO`、兩種繞圈、轉向是新的一跳、插 aos-exec、PATH、結束碼、捷徑入口 |
| `test_directive_hash.py`、`test_directive_spot.py`、`test_directive_md.py`、`test_directive_md_cases.py` | 9＋10＋6＋1 | 帶進來的指示詞程式：抄 proto8 `aos-directive/tests` 三份（經測試小工具 `resolve-check`，等於 aos-directive 命令列的瘦身版）、`aos-json/tests/test_md_cases.py` 的 get／missing 部分（共 77 個 md 案例） |

proto8 沒搬過來的測試：

| 測試 | 為什麼 |
|---|---|
| `aos-exec/tests/test_stack_lazy.py`（4 條） | 整份在測 `--stack-lazy` 與 stack 的建立；換成 `test_proto9_removed.py` 的反向測試 |
| `aos-exec/tests/test_classify.py` 的 `test_zero_timeout…`、`test_timeout_ms…` 兩條、`test_argv0…` 裡 inst 那一半 | inst 單子拿掉了 |
| `aos-exec/tests/test_classify.py` 的 `test_daemon_ctl_same_rule` | 測的是 proto8 的 Python `daemon_ctl`，proto9 沒有 |
| `aos-json/tests/test_md_cases.py` 的 ls、tree 案例；miss 的原因字面比對 | `md_ls`／`md_tree` 沒帶進來；原因字面原本拿 proto8 的 Python `mdpath` 對，這裡只驗 `DirectiveBad` |
| `aos-util/tests/test_parse_cli.py` 其他條 | 測 aos-json、aos-lock、aos-loop，不是 aos-exec |
| `py/tests/` 裡提到 aos-exec 的二十來份（`apps/agent/test_add_dotenv.py`、`apps/daemon_ctl/test_envs_portable.py`、`apps/tools/test_pointer.py`、`test_hook_*`…）、`aos-daemon`、`aos-loop`、`aos-llm` 的測試 | 都是透過 proto8 的 daemon、loop、tools、hook 去叫 aos-exec，而且多半交給它 inst 單子；那些程式 proto9 沒有 |
| `py/tests/test_tool_entry_exec.py` | 查 proto8 `py/tools`、`templates` 的 `_entry` 有沒有 `+x`，跟這支程式本身無關 |

## 還能砍的

下一輪瘦身的候選，**這一版都沒動**，只量、只寫。行數是大約、只算 `src/`（不含測試）。

| 東西 | 約幾行 | 砍了以後什麼不能用 |
|---|---|---|
| `$ref` 指到 `.md`（`md.hpp`、`md_text`、`md_blocks`、`md_walk`，加 `ref.cpp` 的 `load_md`） | 985 | `{"$ref": "x.md#/標題"}` 讀不到，變 `DirectiveBad`（當 JSON 讀失敗）。全夾最大的一塊，佔現在 src 的三分之一 |
| 指示詞整套（`src/directive/` 全部，加 `launch.cpp` 的 `argv_of`、`dotenv.cpp` 的 `json_env` 裡解指示詞那幾行） | 1,640（含上一列） | argv 陣列只能寫字面字串，`{"$env": …}`、`{"$ref": …}`、`$path`、`$prefix` 都不認；JSON `.env` key 的值只能是字串。只留 `$env`＋`$path`／`$prefix` 的話約 80 行就夠 |
| 　└ `$ref` 陣列合併（`merge`、`Resolved`、`dir_of`） | 70 | `{"$ref": ["a.json", "b.json#/c"]}` 不再合成一份 |
| 　└ `#./`、`#../`（所在物件起算） | 50 | 只剩 `#/` 從根算 |
| `parse_cli` 的通用部分（短名表、`keep`、像負數的字、`--x=V`…） | 130 | 換成 aos-exec 自己 30～40 行的小解析；`-w` 這類短名、`--ws=V` 寫法看要不要留 |
| 沒有 `argv` 的 JSON 物件當資料夾（`classify` 的往下挑、`json_env`、記「最後讀的 `.env`」） | 60 | 一份 JSON 裝很多工具、`cfg.json` 照 `_entry` 一路往下挑不行了；JSON 的 `.env` key 跟著沒了 |
| `#/指標` 尋址（`split_hash`、`locate`、`classify` 的指標、`AOS_CO`） | 45 | `aos-exec cfg.json#/tools/t` 不能用；`AOS_CO` 永遠空（跟上一列一起砍就能整個拿掉 `AOS_CO`） |
| `$AOS_ENTRY` 多段（`sub/run`）與資料夾繞圈偵測 | 45 | `AOS_ENTRY` 只能是一個名字；`.env` 寫 `AOS_ENTRY=sub/run` 會找不到 |
| 字串轉向與繞圈偵測（`Kind::Redirect`、`Chain`、`run_cli` 的迴圈） | 35 | `_entry` 寫 `"../other"` 不再轉過去，變 `EntryBad`；要轉向就用捷徑（symlink）或可執行檔 |
| `AOS_WS`／`--ws` 與工作區（`check_ws`、`Layer` 的蓋回、`WsMissing`） | 35 | 入口拿不到 `AOS_WS`；`.env` 的 `${AOS_WS}` 變「沒設」報錯。proto9 的 proc 有自己的目錄（`AOS_MOUNT`），工作區這個想法可能整個用不到 |
| Python 樣式的 `dumps`（只在錯誤訊息裡印 JSON 用） | 45 | 換 nlohmann 的 `dump()`，錯誤訊息裡的 JSON 少了 `, `、`: ` 的空格 |
| `.env` 認 Unicode 空白（`text.cpp` 的 `space_at`、`lstrip`、`rstrip`） | 70 | 換成只認 ASCII 空白約 10 行；值頭尾的全形空白、不換行空白會留在值裡（跟 python-dotenv 不一樣） |
| 「最後讀的那份 `.env` 自己設了 `AOS_CF`／`AOS_CD`／`AOS_CO` 就不蓋」 | 15 | 這三個一律由 aos-exec 決定，`.env` 改不了 |
| `--dotenv-override` | 25 | `.env` 永遠蓋不過外面已有的變數。proto8 的 `ctl add` 會生 `["aos-exec", "--dotenv-override", "--", …]`，那種 argv 會變 `FlagUnknown` |
| `argv[0]` 帶 `/` 又不能 exec 就插 `aos-exec`（`argv0`） | 25 | `["tools/stamp", "a"]` 這種「argv 第一格是資料夾程式」會 `LaunchFailed`，要自己寫 `["aos-exec", "tools/stamp", "a"]` |
| `.json` 補找（`has_extension`、`locate` 與挑入口時補 `.json`） | 17 | `aos-exec tool` 找不到 `tool.json`、資料夾裡要叫 `_entry` 不能叫 `_entry.json` |
| 入口是捷徑時 cd 到實際的資料夾、不讀那邊 `.env` | 10 | 捷徑入口會在捷徑所在的資料夾跑 |
| `AOS_ENTRY=.env`（`.env` 本身當入口） | 6 | 少一個很少用的寫法 |
| ENOEXEC → `/bin/sh` | 0（glibc 的 `execvp` 白送） | 砍反而要多寫：改用 `execve` 得自己照 PATH 找（約 30 行）。可以順手砍的是 `is_program` 裡「`+x` 又不是 JSON＝程式」那條（約 8 行，還要把整份檔讀進來試 JSON）；砍了 `+x` 沒 `#!` 的腳本會變 `EntryBad` |
| 靜態庫＋公開標頭（給 fork 後叫 `run_cli` 的人） | 30（含 Makefile） | 只剩命令列；之後 daemon 想不 exec 就直接在子行程叫 `run_cli` 的路沒了 |

## 留下來的東西裡，跟 proto9 想法對不上的

- **cd 會被 proc 自己蓋掉**：proto9 的 proc 起來後會 chdir 到自己掛出來的目錄（介面草稿：`/proc/<PID>/cwd` 就是它的目錄）。aos-exec 幫入口 cd 進資料夾這件事，只在 exec 那一刻有用；入口之後還要找自己資料夾裡的檔，要用 `$AOS_CD`（絕對路徑），不要靠目前目錄或相對路徑。
- **`AOS_WS` 預設＝呼叫者的目前目錄**：沒給 `--ws`、外面也沒 `AOS_WS` 時，工作區就是叫它的人站的地方。proto9 的 daemon 站在自己的掛載目錄裡，從那裡叫 aos-exec，工作區會變成 daemon 自己的 FUSE 目錄；相對的 XXX 也從那裡算。接 daemon 時要明給絕對路徑。
- **環境變數的名字是 proto8 那套**：aos-exec 只認、只設 `AOS_WS`、`AOS_ENTRY`、`AOS_CF`／`AOS_CD`／`AOS_CO`；proto9 的 `AOS_ROOT`、`AOS_NAME`、`AOS_MOUNT`、`AOS_NAME_PID` 它不知道，原樣傳。`.env` 不加旗標蓋不掉它們（好），加了 `--dotenv-override` 蓋得掉（daemon 給的名字可能被 `.env` 改掉）。
- **「入口只收可執行檔與 argv 陣列」跟兩種帶路**：字串轉向、沒 `argv` 的 JSON 物件當資料夾，嚴格說不是入口種類，所以這次留著；要不要算進「先只收那兩種」，等使用者說。
- **插 `aos-exec` 要靠 PATH**：proto9 還沒談怎麼裝（`bin/` 放哪），argv 陣列的 `argv[0]` 是資料夾程式時，PATH 上得先有這支 aos-exec。
- **對得上的**：可執行檔與 argv 陣列都是 exec，pid 不變（插進去的 aos-exec 也是 exec），daemon 拿到的 pid 就是入口的 pid；拿掉 inst 單子之後 aos-exec 不再留在中間當監工，也不再有自己的行程群組與轉訊號。
