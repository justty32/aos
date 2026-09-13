# proto4-3 — aos-exec 單發、aos-run 連續、aos-daemon 管一堆、aos-kernel 排程（Python）

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
python3 -m unittest discover -s test        # 220 條測試，真的開進程，暫存在 /tmp、跑完自己收

./aos-exec /path/to/folder                  # 跑 folder/.aos/inst.json
./aos-exec /path/to/folder --stderr -       # 看不到錯誤時先加這個
./aos-exec /path/to/folder --dir-target my/inst.json
./aos-exec /path/to/one.json                # 直接指一份 inst.json
./aos-exec /path/to/script.sh               # 普通檔案：直接執行它
./aos-exec /path/to/script.sh -- a "b c"     # 普通檔案：-- 後原樣當 argv[1:]
./aos-exec /path/to/folder --timeout-ms 3000
echo $?                                     # 子程式的結束狀態；125＝aos-exec 自己失敗
```

```sh
./aos-run /path/to/folder --interval-ms 5000            # 一直跑，每 5 秒一次

setsid -f ./aos-daemon                                  # 上電（腳本／非互動 shell 用這個，不會被帶走）
./aos-daemon &                                          # 互動終端可以這樣
./aos-daemon-ctl add /path/to/inst.json --interval-ms 5000    # daemon 只收 .json 的路徑
./aos-daemon-ctl ls

./aos-kernel-init K --ncpu 2                # 灌一次作業系統
./aos-kernel-init K --ncpu 2 --module /abs/proto4-5/llm_cpu_module.py # LLM 排程當 kernel module
./aos-kernel-boot K                         # 開機：把 kernel 放上 daemon
./aos-kernel add K my-proc.json             # 排行程
./aos-kernel ls K                           # 看狀態
./aos-daemon-ctl stop                       # 關機
```

cpu 不用你插，kernel 第一回合會自己把 `cpus/*.json` 掛上 daemon。排進 `K/procs/`
的行程 inst.json 例如：

```json
{"argv":["/abs/程式"],"cwd":"/abs/資料夾","stdout":"out.txt","stderr":"err.txt"}
```

用 `aos-kernel add` 排時，`cwd` 可以省略，意思就是 inst.json 所在的資料夾；自己手放進
`procs/` 就一定要寫，沒寫會退件。相對 `cwd` 以 inst.json 所在資料夾為準，`argv[0]` 則以
轉完的 cwd 為準。`add` 會照 aos-exec 的規則把整份再驗一遍，多寫的欄位也會被擋。

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
| aos-kernel | [docs/kernel.md](docs/kernel.md) | init 灌一次、boot 開機、add 排行程、rm 拿掉、tick 排程、ls 看狀態 |

## 檔案

逐檔職責搬到 [docs/files.md](docs/files.md)，新手入口只留怎麼用。

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- **只有 `--stderr` 一個覆蓋串流的旗標**（`-`＝印到畫面）；stdin／stdout／exit 不蓋。
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

## 出處

這是 [proto4 筆記第 11～15 節](../proto4/notes/2026-09-08-ideas.md)（aos-exec、aos-run、
aos-daemon）與 [第 16～19 節](../proto4/notes/2026-09-08-ideas.md)（kernel）的原型；後面的
裁決優先於前面的。上一版是 [proto4-2](../proto4-2/README.md)，當時 inst.json 是八欄、
相對路徑以資料夾為中心、沒寫的串流會被 cpu 抓回 `last.json`。
