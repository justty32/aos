# proto4-3 — aos-exec 單發、aos-run 連續、aos-daemon 管一堆、aos-kernel 排程（Python）

這是 [proto4 筆記第 11 節](../proto4/notes/2026-09-08-ideas.md)（aos-exec）、
[第 12 節](../proto4/notes/2026-09-08-ideas.md)（aos-run）與
[第 13 節](../proto4/notes/2026-09-08-ideas.md)（aos-daemon）的原型，規格以那三節為準
（跟第 10 節衝突的地方都聽第 11 節的）；第 14 節（拍板的那一輪）與第 15 節（daemon 的
key 改成 inst.json 的路徑）是後來的修正，衝突時聽新的。

kernel 那一段（`aos-kernel`／`aos-kernel-init`／`aos-kernel-tick`）的規格是
[第 16～19 節](../proto4/notes/2026-09-08-ideas.md)：第 16 節對齊名詞（daemon＝硬體、
kernel＝第一個程序）、第 17 節是 kernel 管 `procs/` 的初步想法與問答、第 18 節是原型定案、
第 19 節把它拆成 `aos-kernel-init`（§19.4）／`aos-kernel-tick`（§19.7）一系列獨立指令，
一樣衝突時聽新的。

← [proto4-2](../proto4-2/README.md)（inst.json ＋ cpu ＋ daemon ＋ kernel；那一版的
inst.json 是八欄、相對路徑以資料夾為中心、串流沒寫會被 cpu 抓回 `last.json`）

換的思路是：**inst.json 只是我們規定的第一版指令集**，像 ARM 那樣小而統一——欄位少、
但每個都有定義。最陽春的指令集是「一個檔讀進來就跑」，inst.json 只是在不增加複雜度的
前提下多給了 stdin／stdout／stderr／exit／cwd／envs。

跟 proto4-2 比，這一版改了四件事：

1. **`timeout_ms` 拿掉**。時限不是指令的事，是「反覆執行 inst.json 的傢伙」的事。單發的
   aos-exec 只用命令列旗標 `--timeout-ms` 自己管；寫在 inst.json 裡＝未知 key、拒絕。
2. **沒寫的串流一律 `/dev/null`**，不是繼承、也不是抓回哪個檔。單發執行器不替你收輸出，
   要就自己寫檔名。
3. **相對路徑的中心是 cwd**（解析完的那個工作目錄），不是 `xxx`。只有 `cwd` 自己的相對
   路徑從 `xxx` 起算，不然沒有中心可言。
4. 環境欄位叫 **`envs`**（寫 `env` ＝未知 key），多一個整個物件層級的 `$opt: clear`。

**「一直跑」是 aos-run 的事**（往下看那一節）。它就是 `import aos_exec` 反覆叫
`run_target()`，所以核心就是那一個函式，兩支命令列都只是包它。

## 怎麼跑

```sh
export AOS_DAEMON_HOME=~/.aos-daemon   # daemon、ctl、kernel 三支都靠這個找家；用 --home 不會傳給子孫
cd proto4-3
python3 -m unittest discover -s test        # 190 條測試，真的開進程，暫存在 /tmp、跑完自己收

./aos-exec /path/to/folder                  # 跑 folder/.aos/inst.json
./aos-exec /path/to/folder --dir-target my/inst.json
./aos-exec /path/to/one.json                # 直接指一份 inst.json
./aos-exec /path/to/script.sh               # 普通檔案：直接執行它
./aos-exec /path/to/folder --timeout-ms 3000
echo $?                                     # 子程式的結束狀態；125＝aos-exec 自己失敗
```

```sh
./aos-run /path/to/folder --interval-ms 5000            # 一直跑，每 5 秒一次

./aos-daemon &                                          # 非互動 shell 結束會把它帶走；要常駐用 nohup … &、setsid 或 tmux
./aos-daemon-ctl add /path/to/inst.json --interval-ms 5000    # daemon 只收 .json 的路徑
./aos-daemon-ctl ls

./aos-kernel-init K --ncpu 2                            # 這 2 顆是給行程用的，跑 kernel 自己的那顆不算在內
./aos-daemon-ctl add K/inst.json --interval-ms 1000
./aos-kernel ls K
```

cpu 不用你插，kernel 第一回合會自己把 `cpus/*.json` 掛上 daemon。排進 `K/procs/`
的行程 inst.json 例如：

```json
{"argv":["/abs/程式"],"cwd":"/abs/資料夾","stdout":"out.txt","stderr":"err.txt"}
```

當成函式用（aos-run 就是這樣接的）：

```python
import aos_exec
code, kind = aos_exec.run_target("/path/to/folder", dir_target=".aos/inst.json",
                                 timeout_ms=3000)
# kind："child"＝子程式跑完了、"aos"＝aos-exec 自己失敗、"usage"＝用法錯
```

## 四支工具各自的說明

| 工具 | 說明在哪 | 講什麼 |
|---|---|---|
| aos-exec | [docs/exec.md](docs/exec.md) | 三種目標、inst.json 七欄、指示詞、退出碼 |
| aos-run | [docs/run.md](docs/run.md) | 間隔怎麼算、`--status-fd`、什麼時候停、印什麼 |
| aos-daemon | [docs/daemon.md](docs/daemon.md) | key、五個狀態、七個動作、請求格式、家目錄、CLI |
| aos-kernel | [docs/kernel.md](docs/kernel.md) | 家長什麼樣、四支指令、每回合五步、開機順序、這一版沒做什麼 |

## 檔案

- `aos-exec`：命令列入口，可執行，薄薄一層。
- `aos_exec.py`：認目標是哪一種、組出要跑的東西、跑一次、砍逾時、寫 exit 檔。核心是
  `run_target(xxx, dir_target=…, timeout_ms=…) -> (code, kind)`，`kind` 是
  `child`／`aos`／`usage`。
- `aos_inst.py`：inst.json 的讀、驗、解指示詞（格式那一層），從 proto4-2 抄來改的。
- `aos-run`：aos-run 的命令列入口，可執行，一樣薄薄一層。
- `aos_run.py`：迴圈本體——什麼時候跑下一次、什麼時候停、跑完印一行（給人）＋寫一個事件
  （給程式）。核心是 `run_loop(xxx, *, dir_target=…, timeout_ms=…, interval_ms=…,
  from_start=…, max_runs=…, time_limit_ms=…, stop_exits=…, log=…, status_fd=…,
  stop_on_error=…) -> (退出碼, 停止原因)`。
- `aos-daemon`：daemon 本人的命令列入口——普通前台程式，解 `--home`、檢查已經在跑、
  `Daemon(home).serve()`。不背景化，自己 `&` 或交給 systemd。
- `aos_daemon.py`：daemon 本體——那個 dict、七個動作（都是 `Daemon` 的方法、都回
  `(ok, result)`、都立刻回，測試可以不開 daemon 進程直接叫）、主迴圈一圈 `tick()`
  （收請求、推狀態機、收屍）、落地與收工。
- `aos_daemon_entry.py`：表上的**一筆**長什麼樣（`Entry`）＋五個狀態的**狀態機**
  （`advance()`／`begin_stop()`）＋兩條讀取執行緒（讀 status 更新近況、讀 stderr 進 log）
  ＋ key 那兩條規則：`key_of()`（那份 `.json` 的 realpath）與 `json_only()`（只收 `.json`）。
- `aos_daemon_req.py`：**請求檔**那一層——`dispatch()`（一個請求 →`(ok, result)`）與
  `handle_requests()`（掃 `requests/`、處理、搬到 `done/`）。
- `aos-daemon-ctl`：命令列入口，可執行，薄薄一層，真東西在 `aos_daemon_ctl.py`。
- `aos_daemon_ctl.py`：對 daemon 下指令——丟請求等回音、讀 `state.json` 印表；daemon 沒在
  跑時 `ls`／`get` 讀最後狀態、其他指令直接說「daemon 沒在跑」。
- `aos-kernel`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel.py`。
- `aos_kernel.py`：家的版面（`KHome`：哪個檔在哪、讀寫 config／state／log，`here_or_die()`
  共用）＋剩下的唯一子命令 `ls`。`init`／`tick` 都拿掉了，被人叫到只回退出碼 2、提示改用
  `aos-kernel-init`／`aos-kernel-tick`。
- `aos-kernel-init`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel_init.py`。
- `aos_kernel_init.py`：`init` 本體——建家與四個檔（`inst.json`／`config.json`／
  `state.json`／`kernel.log`／`procs/`／`cpus/`），從 `aos_kernel.py` 拆出來的獨立指令
  （§19.4：重灌作業系統跟每回合跑的心跳／給人看的 ls 不是同一種壽命），共用
  `aos_kernel.KHome`。
- `aos-kernel-tick`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel_tick.py`。
- `aos_kernel_tick.py`：心跳本體——一回合那五步：點 cpu（`poll_cpus`／`ctl_add`）、檢查佇列
  （`check_queue`／`bad_reason`）、排程（`schedule`／`_take`／`_swap`，硬連結＋rename 那招），
  也是從 `aos_kernel.py` 拆出來的獨立指令（§19.7），共用 `aos_kernel.here_or_die()`。
- `aos_home.py`：家目錄的版面（哪個檔在哪）＋家的優先序（`--home` → `AOS_DAEMON_HOME` →
  `~/.aos-daemon`）＋原子寫檔＋pid 活不活，從 proto4-2 改的。
- `test/`：`python3 -m unittest discover -s test`（185 條）。kernel 的在
  `test_kernel.py`（真的開一支 daemon ＋ 真的跑 aos-kernel）。daemon 的測試分三支：
  `_daemon.py`（共用基底，底線開頭＝discover 不撿）、`test_daemon.py`（key 與查）、
  `test_daemon_ops.py`（暫停／刪／restart／請求），另外 `test_daemon_cli.py` 真的開一支
  daemon 進程走完一輩子。

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- **沒有覆蓋串流的旗標**。「用 aos-exec 自己的 stdin／stdout／stderr／exit 蓋掉 inst.json
  裡寫的」是後續要做的方便功能，這次不做。
- **不注入 `AOS_*` 環境變數**（`AOS_DIR`／`AOS_TICK` 都沒有），aos-exec 與 aos-run 都一樣
  （§8：proc 不需要知道自己被誰、以什麼節奏跑）。要不要有之後撞到再說。
- **不寫任何紀錄檔**。不抓子行程的輸出、不寫 `last.json`／`runs.jsonl`，`exit` 欄位是唯一
  會被寫出去的東西。想看輸出就自己寫 `stdout`。aos-run 的每次一行只印在**它自己的 stderr**，
  `--status-fd` 也只是**寫給誰**的事，不落檔。
- **整合進 aos-daemon 是之後的事**。aos-run 只是概念驗證：proto4-2 的 `aos_cpu.py`「跑一次」
  那段要換成這裡的東西、`last.json`／`runs.jsonl`／`cpu.json` 歸誰寫，都還沒動。
- aos-run **沒有對齊格子**：`--from-start` 是「上次起點＋interval」，不是「起跑＋n×interval」，
  長跑會慢慢往後漂。
- aos-run **不重讀自己的旗標**、不吃設定檔、沒有健康檢查、沒有退避（壞掉就是照原速一直試）。
- `exit` 檔的父目錄不存在就直接失敗（退出碼 125），**不幫忙 mkdir**，那個指令也不會被跑。
- `$ref` 沒有範圍限制（能不能指到 cwd 外＝行程權限說了算），也**沒有深度上限**——只有循環
  會被擋（同一條鏈撞到同一個 realpath＋pointer），一條夠長的鏈可以一直解下去。
- **`$ref` 的相對路徑一律以 cwd 為中心**，不是以「被 `$ref` 的那個檔所在的資料夾」為中心。
  所以從別的資料夾 `$ref` 進來的一份 inst.json，它裡面的相對路徑還是照 cwd 算。
- `$fmt` 只有 `env:` 一個 namespace，沒有路徑變數、沒有預設值語法、沒有跳脫。
- 沒有並行（凍結版的 `parallel`）、沒有批次、沒有重試、沒有退避。

aos-daemon 這一版另外沒做的：

- **不自動重開**。aos-run 自己退了（跑滿、時限到、`--stop-exit`、被別人殺）就只是從表上
  消失、`daemon.log` 記一行，不會替你再開一個。
- **只看副檔名，不看內容**：`add` 只確認「不是資料夾、以 `.json` 結尾」，裡面是不是一份
  合法的 inst.json 完全不驗——驗那個是 aos-exec 每次跑的事（壞了就每次 `exit=125 kind=aos`）。
- **不監看檔案出現**：收下一個還不存在的 `.json` 之後，就是照 `--interval-ms` 一直試，
  沒有 inotify、沒有退避，`runs` 會一直往上加。
- **暫停中 `--timeout-ms` 不生效**：砍逾時的是 aos-run，它被 SIGSTOP 了就沒人砍，正在跑
  的那個子行程會一直跑下去。要不要讓 daemon 代砍，之後再說。
- **`pause` 不保證從此零次**：等它睡著才 SIGSTOP，`interval` 極短時那一刀可能剛好落在下一次
  開跑之後，那次會跑完才真的停。要「馬上凍住、正在跑的也不管」得另外做。
- **`restart` 的空窗期表上還在**（狀態 `restarting`，別人趁隙 `add` 會被擋掉），但那段時間
  它就是沒在跑，`pause`／`resume` 也會被拒絕。
- **等不到就放棄的是 CLI，不是 daemon**：`aos-daemon-ctl` 的 rm／restart／pause 等 10 秒
  就印一句退出碼 1，daemon 那邊該做的還是照做。要對帳自己再 `ls` 一次。
- **daemon 這一層不知道有 kernel**：請求是 daemon 自己讀的，`aos-kernel` 對它來說就是
  另一個下 `ctl` 指令的人。
- **沒有 `.aos/` 紀錄檔**（proto4-2 的 `last.json`／`runs.jsonl`／`cpu.json` 都沒有），
  只剩 `daemon.log` 一條線；aos-run 子進程的 stdout 直接進 `/dev/null`。
- **daemon 的生死歸使用者**（§9）：它就是硬體，一支普通程式，你自己開著、自己管它的生死
  （背景放 `&`、tmux、systemd 都行），掛了 aos 不管、也不會有人替你重開。
- 沒有權限、沒有認證：**誰能寫 `H/requests/` 就能叫 daemon 用你的身分跑任何東西**。
- 不檢查 inst.json 的權限。一份 inst.json 就是可執行的權柄：它可以指名任意程式、引數、
  輸入輸出檔、工作目錄與環境變數值，全都用你的憑證跑。能改它的人就等於能用你的身分執行
  任意程式碼。
