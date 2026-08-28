# M1 煙霧測試留存（實跑原文）

← [plan](plan.md)｜[spec](spec.md)｜[SPEC](../../../../docs/SPEC.md)

**用途**：S8 寫 `docs/usage.md` 時直接照抄——feature-dev 鐵律要求「文件裡的每條指令與
輸出都真的跑過」（spec 驗收 7）。**本檔的每一段都是實跑貼上的原文，不要手改**；命令
改了就重跑、重貼。

**跑法**（每一節開頭都標了世界的位置與日期）：

```text
S4／S6 兩節：WSL Ubuntu；世界開在 /tmp（ext4，renameat2 可用，不是 drvfs）
S7／S8／S9 三節：原生 Linux（Manjaro）；世界開在本 session 的 scratchpad（tmpfs）
PATH 前面掛上 <repo>/build/bin，所以下面的 `aos` 就是 default preset 建出來的執行檔
每段的 `[exit N]` 是該命令的退出碼，stderr 與 stdout 一起收
```

---

## S4 `aos deliver`（2026-08-28，世界 `/tmp/aos-smoke-gFH92x`）

投遞、彙整、取件走完整一圈；含各種拒絕路徑與退出碼。

```console
$ aos --help
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
  deliver      投遞一批 instruction 到 aos 資料夾的收件匣
  tooljson     讀取並檢查 tool JSON spec
  llms         呼叫 OpenAI 相容端點並查詢模型能力
[exit 0]

$ aos init .
[exit 0]

$ printf '{"argv":["touch","a"]}' | aos deliver
{"delivery":"694-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ printf '{"argv":["touch","b"]}' | aos deliver
{"delivery":"697-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ ls -1 .aos/inst.tempd/
694-0.json
697-0.json
[exit 0]

$ printf '[{"argv":["touch","c"]},{"argv":["touch","d"]}]' > batch.json; aos deliver . -f batch.json
{"delivery":"699-0.json","count":2,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver . -f /dev/null
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf 'not json' | aos deliver .
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf '{"argv":["touch","a"],"nope":1}' | aos deliver .
aos deliver: invalid input: record 1: UnknownKey
[exit 1]

$ printf '[{"argv":["touch","a"]},{"argv":[]}]' | aos deliver .
aos deliver: invalid input: record 2: EmptyArgv
[exit 1]

$ ls -1 .aos/inst.tempd/
694-0.json
697-0.json
699-0.json
[exit 0]

$ aos deliver /tmp/aos-smoke-no-such-world -f batch.json
aos deliver: cannot enter /tmp/aos-smoke-no-such-world: No such file or directory
[exit 1]

$ aos deliver . . -f batch.json
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ aos exec .
[exit 0]

$ ls -1a . .aos
.:
.
..
.aos
a
b
batch.json
c
d

.aos:
.
..
inst-head.json
inst.tempd
version
[exit 0]

$ cat .aos/inst-head.json
{"version":1,"id":"63558783d7668c4f","origin":"aggregated","result":null}
[exit 0]
```

讀法：

- 三次投遞（`694-0`／`697-0`／`699-0`）＝三個不同 pid 的行程各投一次，序號都從 `0`
  起算（§D-2 的 `<pid>-<seq>`）。同一 process 連投 N 次得 N 份不同名這件事 CLI 演不了
  （一次投遞就一個行程），由 `core/inst/tests/test_run_deliver.cpp` 的第一案蓋住。
- 四種拒收都是**驗證階段**擋下來的：收件匣事後只有三個檔，連 `.temp` 都沒有殘留。
- 一回合 `aos exec .` 把三份投遞（共四筆 instruction）併成一批跑掉，`a b c d` 都在，
  投遞被清空，批旁邊留下 `inst-head.json`（§C-8 四欄位齊，S3 落地的那個）。

## S4 輸入來源的三種寫法與 canonical 位元組（2026-08-28，世界 `/tmp/aos-smoke-4sQSQJ`）

```console
$ printf '{"argv":["touch","z"]}' | aos deliver .
aos deliver: invalid ./.aos: No such file or directory
[exit 1]

$ mkdir world && aos init world
[exit 0]

$ printf '{"argv":["touch","e"]}' > one.json; aos deliver world -f one.json
{"delivery":"734-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world - < one.json
{"delivery":"736-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world -f - < one.json
{"delivery":"738-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ ls -1 world/.aos/inst.tempd/
734-0.json
736-0.json
738-0.json
[exit 0]

$ cat world/.aos/inst.tempd/*.json
[{"argv":["touch","e"]}]
[{"argv":["touch","e"]}]
[{"argv":["touch","e"]}]
[exit 0]

$ aos exec world && ls -1 world
e
[exit 0]

$ aos exec world; ls -1 world/.aos
inst-head.json
inst.tempd
version
[exit 0]
```

讀法：

- 第一條：沒有 `.aos` 的資料夾**不是世界**，deliver 報錯、不自動建（§D-3）。
  （`aos init world` 也不建資料夾本身，所以前面要 `mkdir world`。）
- `-f FILE`／`-`／`-f -` 三種寫法都通；`-f one.json` 的路徑是相對**呼叫者的** cwd
  解析的（`one.json` 在 `world/` 外面），因為它是命令的輸入、不是世界的一部分。
- 投出去的位元組是 canonical 的（§D-3 裁-7）：投的是單一物件，落地是批陣列
  `[{"argv":["touch","e"]}]`＋一個 LF——`read_all`→`write_all` 往返後的樣子。
- 第二次 `aos exec world` 沒事可做（投遞已清空、沒有新批次），照樣回 0。

---

## S6 `.aos/turn`（2026-08-28，世界 `/tmp/aos-smoke-turn-PgebsG`）

init 建立為 `0`；有工作的回合 release 成功後遞增；空轉不動；缺 turn 的舊世界（模擬：
init 後手動刪掉）視為 `0`，跑一回合後變 `1`（裁-5）。

```console
$ aos init w
[exit 0]

$ cat w/.aos/turn
0
[exit 0]

$ printf '{"argv":["touch","a"]}' | aos deliver w
{"delivery":"699-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos exec w
[exit 0]

$ cat w/.aos/turn
1
[exit 0]

$ aos exec w   # 沒有新投遞，空轉
[exit 0]

$ cat w/.aos/turn   # 不動
1
[exit 0]

$ rm w/.aos/turn   # 模擬 M1 之前的舊世界
[exit 0]

$ printf '{"argv":["touch","b"]}' | aos deliver w
{"delivery":"707-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos exec w
[exit 0]

$ cat w/.aos/turn   # 缺檔視為 0，一回合後為 1（裁-5）
1
[exit 0]

$ ls -1 w
a
b
[exit 0]
```

讀法：

- `aos init w` 建出的 `turn` 初值是 `0`（LF 結尾，spec 驗收 4 前半）。
- 第一次 `aos exec w` 真的跑了投遞（`a` 出現），release 成功後 `turn` 變 `1`
  （spec 驗收 4 後半）。
- 第二次 `aos exec w` 沒有新投遞可跑（沒有工作的回合不是一個回合），`turn` 停在
  `1` 不動。
- 手動刪掉 `turn` 檔模擬「M1 之前的舊世界」：不拒絕、不 bump `version`（仍是
  `1`，此段未貼但另見 `test_run_handoff.cpp` 的斷言），一回合後 `turn` 出現且是
  `1`（讀不到視為 `0`，裁-5／§B-3）。

---

## S8 `docs/usage.md` 用的重跑（2026-08-28，世界 `<scratchpad>/s8-Fwp3wf`、`<scratchpad>/s8r-kJ2tTe`）

S4／S6 兩節是 S3～S6 落地過程中分次跑的，`.aos` 的內容也停在當時（例如 S4 那段的
`ls -1a .aos` 還沒有 `turn`）。這一節是 **S8 在 S0–S7 全落地之後、用同一顆
`build/bin/aos` 重跑一次**的原文，`docs/usage.md` 的 `aos deliver` 節整段照抄自這裡。
兩個世界都開在本 session 的 scratchpad 底下（`/tmp/claude-1000/…/scratchpad/`）。

> 本節的 `ls` 是 coreutils 的 `ls`。本機 shell 把 `ls` 別名成 `eza`，實跑時用
> `command ls` 繞開別名，貼出來的就是繞開後的輸出（所以 `ls -1a` 才看得到 `.`／`..`）。

### 快樂路徑：四種輸入寫法 → 一回合（世界 `s8-Fwp3wf`）

```console
$ aos --help
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
  deliver      投遞一批 instruction 到 aos 資料夾的收件匣
  tooljson     讀取並檢查 tool JSON spec
  llms         呼叫 OpenAI 相容端點並查詢模型能力
[exit 0]

$ mkdir world && aos init world
[exit 0]

$ cat world/.aos/turn
0
[exit 0]

$ printf '{"argv":["touch","a"]}' > one.json
[exit 0]

$ aos deliver world -f one.json
{"delivery":"87362-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world - < one.json
{"delivery":"87363-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world -f - < one.json
{"delivery":"87364-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ printf '[{"argv":["touch","b"]},{"argv":["touch","c"]}]' | aos deliver world
{"delivery":"87366-0.json","count":2,"target":".aos/inst.tempd"}
[exit 0]

$ ls -1 world/.aos/inst.tempd/
87362-0.json
87363-0.json
87364-0.json
87366-0.json
[exit 0]

$ cat world/.aos/inst.tempd/*.json
[{"argv":["touch","a"]}]
[{"argv":["touch","a"]}]
[{"argv":["touch","a"]}]
[{"argv":["touch","b"]},{"argv":["touch","c"]}]
[exit 0]

$ aos exec world
[exit 0]

$ ls -1 world
a
b
c
[exit 0]

$ cat world/.aos/inst-head.json
{"version":1,"id":"9a2b5422e914c659","origin":"aggregated","result":null}
[exit 0]

$ cat world/.aos/turn
1
[exit 0]

$ aos exec world
[exit 0]

$ cat world/.aos/turn
1
[exit 0]
```

### 拒絕路徑（世界 `s8r-kJ2tTe`，另建一個乾淨的 `world`）

```console
$ printf 'not json' | aos deliver world
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf '{"argv":["touch","a"],"nope":1}' | aos deliver world
aos deliver: invalid input: record 1: UnknownKey
[exit 1]

$ printf '[{"argv":["touch","a"]},{"argv":[]}]' | aos deliver world
aos deliver: invalid input: record 2: EmptyArgv
[exit 1]

$ aos deliver world -f /dev/null
aos deliver: invalid input: JsonSyntax
[exit 1]

$ aos deliver world -f no-such-file.json
aos deliver: cannot read no-such-file.json: No such file or directory
[exit 1]

$ mkdir plain && aos deliver plain -f /dev/null
aos deliver: invalid plain/.aos: No such file or directory
[exit 1]

$ printf '{"argv":["touch","a"]}' | aos deliver plain
aos deliver: invalid plain/.aos: No such file or directory
[exit 1]

$ aos deliver no-such-folder
aos deliver: cannot enter no-such-folder: No such file or directory
[exit 1]

$ aos deliver world world
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ ls -1a world/.aos/inst.tempd/
.
..
[exit 0]
```

讀法（與 S4 兩節一致的部分不重複）：

- **批 id 每次跑都不一樣**：`9a2b5422e914c659` ≠ S4 那節的值，因為摘要吃的是投遞
  **檔名**＋內容，而檔名帶 pid（§D-6／§D-2）。文件裡凡是貼 `id` 或投遞檔名的地方，
  都得說明它會變。
- `-f no-such-file.json` 的錯誤來自 CLI 讀輸入那一步（庫層還沒被呼叫）。
- `aos deliver plain -f /dev/null`：`plain/` 沒有 `.aos`，報的是**世界**的錯而不是
  「invalid input」——CLI 先把輸入讀完，才 chdir 進世界驗版面，內容驗證在最後。

### 庫層與 C ABI 的投遞例子（`core/inst/docs/handoff.md`／`capi.md` 用）

兩支示範程式都在 scratchpad 的臨時目錄裡編、在該目錄裡跑（`inst.json` 是相對路徑，
所以輸出不含機器專屬路徑）；目錄事先 `mkdir -p "$demo/inst.tempd"`。

```console
$ ./deliver-demo
deliver=Ok name=90507-0.json count=1 inbox=inst.tempd
[exit 0]

$ ./deliver-demo
deliver=Ok name=90508-0.json count=1 inbox=inst.tempd
[exit 0]

$ command ls -1 inst.tempd
90507-0.json
90508-0.json

$ cat inst.tempd/*.json
[{"argv":["printf","hello\n"]}]
[{"argv":["printf","hello\n"]}]
```

```console
$ ./deliver
delivered 91715-0.json count=1
[exit 0]

$ ./deliver          # 換到一個沒有 inst.tempd 的目錄再跑
deliver: InboxReadFailed (errno 2)
[exit 1]
```

`handoff.md` 原有的 aggregate／claim／release 例子也重跑過（路徑改到 scratchpad、
其餘一字不動）：輸出仍是 `aggregate=Ok published=1`／`claim=Ok`／`release=Ok`，但
**執行完目錄裡多了一個 `inst-head.json`**（S3 之後才有的 sidecar），文件已補上這句。

---

## S7 fsync 計數實測（2026-08-28，世界 `<scratchpad>/s7/g-n15CIL/w`）

風險 3 的宣稱：「空轉路徑（`--loop` 睡醒沒事做）零 fsync」，原訂實測方式是
`strace -c -e fsync`。**本機沒有 strace**——這台是原生 Linux（Manjaro，kernel
6.18.45-1-MANJARO），不是 WSL；`strace`／`ltrace`／`perf`／`bpftrace` 四個都沒裝，
`pacman -Q` 也查不到（本階段不裝套件、不 sudo）。**改用 `LD_PRELOAD` 攔截器實測**：
自己編一個 `.so` 攔 libc 的 `fsync`／`fdatasync`／`sync`，各自計數、`atexit` 時把
`pid=… fsync=N …` 追加到 `$FSYNC_COUNT_LOG`。攔的是 libc 呼叫層（不是 syscall 層），
`core/inst/src/` 的落盤點全部走 libc `fsync()`（`grep -rn "fsync" core/inst/src/`
確認過，沒有直接 `syscall(SYS_fsync)` 的寫法），所以計數等價。

世界開在 scratchpad（本機 `/tmp` 是 **tmpfs**，不是 ext4；fsync 在 libc 層數，與檔案
系統無關）。`timeout -s INT 5` 送 SIGINT 收尾，`--loop` 的訊號處理讓 `main` 正常返回，
`atexit` 才有機會把計數寫出來。

```console
$ command -v strace ltrace perf bpftrace; echo "(以上皆無輸出＝四種都沒裝)"
(以上皆無輸出＝四種都沒裝)
[exit 0]

$ gcc -shared -fPIC -O2 -o fsyncount.so fsyncount.c -ldl
[exit 0]

$ COUNT=$PWD/fsyncount.so; echo $COUNT
/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/s7/g-n15CIL/fsyncount.so
[exit 0]

$ aos init w
[exit 0]

$ env LD_PRELOAD=$COUNT FSYNC_COUNT_LOG=$PWD/init.log aos init w; cat init.log
aos init: refusing w: .aos already exists
pid=87789 fsync=0 fdatasync=0 sync=0
[exit 0]

$ timeout -s INT 5 env LD_PRELOAD=$COUNT FSYNC_COUNT_LOG=$PWD/idle.log aos exec --loop 100 w
[exit 124]

$ cat idle.log
pid=87793 fsync=0 fdatasync=0 sync=0
[exit 0]

$ printf "{\"argv\":[\"touch\",\"a\"]}" | env LD_PRELOAD=$COUNT FSYNC_COUNT_LOG=$PWD/deliver.log aos deliver w
{"delivery":"88021-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ cat deliver.log
pid=88021 fsync=2 fdatasync=0 sync=0
[exit 0]

$ timeout -s INT 5 env LD_PRELOAD=$COUNT FSYNC_COUNT_LOG=$PWD/work.log aos exec --loop 100 w
[exit 124]

$ cat work.log
pid=88026 fsync=0 fdatasync=0 sync=0
pid=88025 fsync=7 fdatasync=0 sync=0
[exit 0]

$ ls -1 w; cat w/.aos/turn
a
1
[exit 0]

$ timeout -s INT 5 env LD_PRELOAD=$COUNT FSYNC_COUNT_LOG=$PWD/idle2.log aos exec --loop 100 w
[exit 124]

$ cat idle2.log
pid=88128 fsync=0 fdatasync=0 sync=0
[exit 0]
```

用到的攔截器原始碼（`fsyncount.c`，只在 scratchpad，不進 repo）：

```c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static int (*real_fsync)(int);
static int (*real_fdatasync)(int);
static void (*real_sync)(void);
static long n_fsync, n_fdatasync, n_sync;

static void report(void) {
    const char *path = getenv("FSYNC_COUNT_LOG");
    if (!path) return;
    FILE *f = fopen(path, "a");
    if (!f) return;
    fprintf(f, "pid=%d fsync=%ld fdatasync=%ld sync=%ld\n",
            (int)getpid(), n_fsync, n_fdatasync, n_sync);
    fclose(f);
}

__attribute__((constructor)) static void init(void) {
    real_fsync = dlsym(RTLD_NEXT, "fsync");
    real_fdatasync = dlsym(RTLD_NEXT, "fdatasync");
    real_sync = dlsym(RTLD_NEXT, "sync");
    atexit(report);
}

int fsync(int fd) { n_fsync++; return real_fsync(fd); }
int fdatasync(int fd) { n_fdatasync++; return real_fdatasync(fd); }
void sync(void) { n_sync++; real_sync(); }
```

讀法：

- 計數怎麼讀：每行一個行程（`LD_PRELOAD` 會被子行程繼承，所以有工作的那回合多出
  子行程一行）。`work.log` 的 `pid=88026 fsync=0` 是 `touch a` 那個子行程，
  `pid=88025 fsync=7` 才是 `aos` 本身。`fdatasync`／`sync` 全程 0——落盤點只用 `fsync`。
- **空轉組**：空世界跑 `--loop 100` 五秒（約 50 次醒來），`fsync=0`。**風險 3 的宣稱
  對得上**：睡醒後 `claim_instruction` 回 `NoInstruction`、`run_exec_once` 直接
  `return 0`，路徑上沒有任何寫檔。時間縮成 5 秒不是 60 秒——空轉每圈的程式路徑一模
  一樣，跑久只是重複同一圈。
- **對照組（有工作）**：同一個世界投遞一筆後再跑五秒，`fsync=7`。這 7 次落在彙整
  （批 `.temp`、header `.temp`、三次 rename／unlink 之後的目錄 fsync）與 turn
  （`turn.temp`、rename 後的 `.aos` 目錄）。**「有工作才有 fsync」成立**：計數從 0
  跳到 7，而那五秒裡剩下的四十幾圈空轉沒有再加上去。
- **第三段再空轉**：工作做完後的同一個世界，`fsync=0`——確認 7 是「那一回合」的成本，
  不是「跑過工作以後每圈都要付」的成本。
- 旁證兩則：`aos init` 被 `.aos already exists` 擋掉時 `fsync=0`（拒絕路徑不寫檔；
  成功的 init 另測為 3 ＝ `version`、`turn`、`.aos` 目錄）；`aos deliver` 一次投遞
  `fsync=2`（`.temp` 檔、收件匣目錄）。
- **與 strace 的差異照實記**：`LD_PRELOAD` 看不到繞過 libc 的 raw syscall，也管不到
  靜態連結的行程。本專案兩者都不成立（`aos` 動態連結、寫點全走 libc `fsync()`），
  但這一節的證據強度嚴格說比 `strace -c` 弱一級——本機哪天裝了 strace，值得用同一組
  命令重跑對帳。

---

## S9 退出碼實測（2026-08-28，世界 `<scratchpad>/s9/f-uWPsI3` 底下的多個子世界）

把 `aos`／`aos init`／`aos exec`／`aos deliver` 的各失敗模式各跑一次，記退出碼與
stderr 原文（完整對照表交主線收編進 §D-9）。子世界的佈置：`iw`／`dw` 是正常世界；
`bare` 只有資料夾沒有 `.aos`；`fileaos` 的 `.aos` 是普通檔；`nov` 的 `.aos` 缺
`version`；`v2`／`vg`／`emptyver`／`noverr` 分別是 `version` 為 `2\n`／`garbage`／
空檔／`chmod 000`；`af` 手動放了 `.aos/inst.json.runi`；`ro` 是 `chmod 500` 的資料夾；
`noinbox` 的 `inst.tempd` 被 rmdir；`roinbox` 的 `inst.tempd` 是 `chmod 500`。

### 共通與用法錯誤

```console
$ aos
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
  deliver      投遞一批 instruction 到 aos 資料夾的收件匣
  tooljson     讀取並檢查 tool JSON spec
  llms         呼叫 OpenAI 相容端點並查詢模型能力
[exit 2]

$ aos --help >/dev/null
[exit 0]

$ aos nosuchcmd
aos: unknown command 'nosuchcmd'
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
  deliver      投遞一批 instruction 到 aos 資料夾的收件匣
  tooljson     讀取並檢查 tool JSON spec
  llms         呼叫 OpenAI 相容端點並查詢模型能力
[exit 2]

$ aos init a b
usage: aos init [folder]
[exit 2]

$ aos exec a b
usage: aos exec [--loop <milliseconds>] [folder]
[exit 2]

$ aos exec --loop
usage: aos exec [--loop <milliseconds>] [folder]
[exit 2]

$ aos exec --loop abc iw
usage: aos exec [--loop <milliseconds>] [folder]
[exit 2]

$ aos exec --loop -5 iw
usage: aos exec [--loop <milliseconds>] [folder]
[exit 2]

$ aos exec --loop 1e3 iw
usage: aos exec [--loop <milliseconds>] [folder]
[exit 2]

$ aos deliver dw dw2 -f x.json
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ aos deliver dw -f
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ aos deliver --loop 100 dw
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ timeout -s INT 2 aos exec --loop 0 iw
aos exec: warning: --loop 0 would busy-poll and consume one CPU core; using 1 ms instead
[exit 124]
```

### 世界層拒絕（一律 1；`.runi` 是唯一的 3）

```console
$ aos init iw
aos init: refusing iw: .aos already exists
[exit 1]

$ aos init no-such-dir
aos init: cannot open no-such-dir: No such file or directory
[exit 1]

$ aos init ro
aos init: cannot create ro/.aos: Permission denied
[exit 1]

$ aos exec no-such-world
aos exec: cannot enter no-such-world: No such file or directory
[exit 1]

$ aos exec bare
aos exec: invalid bare/.aos: No such file or directory
[exit 1]

$ aos exec fileaos
aos exec: invalid fileaos/.aos: Not a directory
[exit 1]

$ aos exec nov
aos exec: cannot read nov/.aos/version: No such file or directory
[exit 1]

$ aos exec noverr
aos exec: cannot read noverr/.aos/version: Permission denied
[exit 1]

$ aos exec v2
aos exec: unsupported version in v2/.aos/version
[exit 1]

$ aos exec vg
aos exec: unsupported version in vg/.aos/version
[exit 1]

$ aos exec emptyver
aos exec: unsupported version in emptyver/.aos/version
[exit 1]

$ aos exec af
aos exec: refusing af: .aos/inst.json.runi already exists
[exit 3]

$ printf '{"argv":["true"]}' | aos deliver no-such-world
aos deliver: cannot enter no-such-world: No such file or directory
[exit 1]

$ printf '{"argv":["true"]}' | aos deliver bare
aos deliver: invalid bare/.aos: No such file or directory
[exit 1]

$ printf '{"argv":["true"]}' | aos deliver v2
aos deliver: unsupported version in v2/.aos/version
[exit 1]

$ printf '{"argv":["true"]}' | aos deliver noinbox
aos deliver: cannot deliver noinbox/.aos/inst.tempd: InboxReadFailed: No such file or directory
[exit 1]

$ printf '{"argv":["true"]}' | aos deliver roinbox
aos deliver: cannot deliver roinbox/.aos/inst.tempd/98916-0.json.temp: PublishWriteFailed: Permission denied
[exit 1]

$ aos deliver dw -f no-such-file.json
aos deliver: cannot read no-such-file.json: No such file or directory
[exit 1]

$ aos deliver dw -f .
aos deliver: cannot read .: Is a directory
[exit 1]
```

### 內容層：壞投遞（0）vs 壞批次／解析失敗（1）

```console
$ printf "not json" > bad/.aos/inst.tempd/999-0.json; aos exec bad
aos exec: warning: .aos/inst.tempd/999-0.json: JsonSyntax
[exit 0]

$ ls -1 bad/.aos/inst.tempd
999-0.json.bad
[exit 0]

$ printf "not json" > badbase/.aos/inst.json; aos exec badbase
aos exec: .aos/inst.json.runi: JsonSyntax
[exit 1]

$ printf '{"argv":[{"$ref":"no-such.json#/x"}]}' | aos deliver xref >/dev/null; aos exec xref
aos exec: .aos/inst.json.runi: record 1: argv[0]: ReferenceReadFailed: /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/s9/f-uWPsI3/xref/no-such.json#/x: No such file or directory: chain /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/s9/f-uWPsI3/xref/no-such.json#/x
[exit 1]

$ printf '{"argv":[{"$env":"NO_SUCH_VAR_XYZ"}]}' | aos deliver xenv >/dev/null; aos exec xenv
aos exec: .aos/inst.json.runi: record 1: argv[0]: environment variable NO_SUCH_VAR_XYZ does not exist
[exit 1]

$ printf '{"argv":["true"],"exit":"nodir/e"}' | aos deliver xwrite >/dev/null; aos exec xwrite
aos exec: record 1: ExitWriteFailed
[exit 1]
```

### 子行程的成敗一律不反映（全部 0）

```console
$ printf '{"argv":["false"],"exit":"e"}' | aos deliver xfalse >/dev/null; aos exec xfalse; cat xfalse/e
1
[exit 0]

$ printf '{"argv":["no-such-executable-xyz"],"exit":"e"}' | aos deliver xmissing >/dev/null; aos exec xmissing; cat xmissing/e
127
[exit 0]

$ printf '{"argv":["/tmp"],"exit":"e"}' | aos deliver xdir >/dev/null; aos exec xdir; cat xdir/e
127
[exit 0]

$ touch xnoperm/prog; chmod 644 xnoperm/prog
[exit 0]

$ printf '{"argv":["./prog"],"exit":"e"}' | aos deliver xnoperm >/dev/null; aos exec xnoperm; cat xnoperm/e
127
[exit 0]

$ printf '{"argv":["echo","hi"],"stdout":"nodir/o","exit":"e"}' | aos deliver xout2 >/dev/null; aos exec xout2; cat xout2/e
126
[exit 0]

$ printf '{"argv":["sleep","5"],"timeout_ms":200,"exit":"e"}' | aos deliver xto >/dev/null; aos exec xto; cat xto/e
143
[exit 0]
```

### 收尾失敗：回合跑完了、PC 沒推進（1）

```console
$ printf 'x\n' > badturn/.aos/turn
[exit 0]

$ printf '{"argv":["touch","t"]}' | aos deliver badturn >/dev/null; aos exec badturn
aos exec: cannot advance badturn/.aos/turn: Invalid argument
[exit 1]

$ ls -1a badturn badturn/.aos
badturn:
.
..
.aos
t

badturn/.aos:
.
..
inst-head.json
inst.tempd
turn
version
[exit 0]
```

### `aos deliver` 的輸入驗證（成功 0、拒收 1）

```console
$ printf '{"argv":["true"]}' | aos deliver dw
{"delivery":"99012-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ printf 'not json' | aos deliver dw
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf '{"argv":["true"],"nope":1}' | aos deliver dw
aos deliver: invalid input: record 1: UnknownKey
[exit 1]

$ printf '{"argv":[]}' | aos deliver dw
aos deliver: invalid input: record 1: EmptyArgv
[exit 1]

$ printf '[]' | aos deliver dw
{"delivery":"99020-0.json","count":0,"target":".aos/inst.tempd"}
[exit 0]

$ aos exec dw
[exit 0]
```

讀法：

- **2 ＝ 命令列自己不合法**，只看 argv 就判得出來、還沒碰檔案系統：頂層無子命令／
  未知子命令、各子命令參數過多、`--loop` 缺值或值不是十進位無號整數（`abc`／`-5`／
  `1e3` 都走 `std::from_chars` 全長解析，一律 2）。`aos --help`／`-h` 是 0。
  `aos deliver --loop 100 dw` 之所以是 2：deliver 沒有 `--loop`，多出來的參數落進
  「參數過多」。
- **1 ＝ 到得了檔案系統、但這一回合起不來或沒收乾淨**：世界不存在、`.aos` 缺或不是
  目錄、`version` 讀不到／不認得（`2`、垃圾、空檔全歸同一句 `unsupported version`）、
  `init` 目標已有 `.aos` 或不可寫、`deliver` 的輸入無效或收件匣不可用。
- **3 只有一個來源**：`claim_instruction` 撞到既有的 `.aos/inst.json.runi`。它也是
  唯一會讓 `--loop` 整個中止的碼（`run_loop.cpp` 只對 `3` 提早 `return`；回 1 的錯誤
  會被無限重試）。
- **「不反映子行程成敗」實測成立**：子行程回 1、執行檔不存在（`exit` 檔 127）、
  argv[0] 是目錄（127）、沒有執行權（127）、重導向開檔失敗（126）、`timeout_ms`
  逾時被殺（143 ＝ 128+SIGTERM）——`aos exec` 六種全回 **0**，成敗只落在 `exit` 欄位
  指到的檔（§D-9 前半驗證通過）。
- **但「逐筆執行失敗」會回 1**：`ExitWriteFailed`（`exit` 欄位指到的路徑寫不進去）是
  `aos` 自己的落地動作、不是子行程回什麼，所以歸 1。這條界線值得在 §D-9 明說：
  **子行程「跑完之後回什麼」不反映；`aos` 自己「跑不動／收不了尾」反映。**
- **壞投遞 vs 壞批次是兩件事**：收件匣裡的無效投遞被隔離成 `.bad` 後**續行**，
  `aos exec` 回 0（只印 warning）；已發布的 `.aos/inst.json` 本身壞掉則是 1。`$ref`／
  `$env` 解析失敗同樣是 1（批次根本沒開始跑）。
- **1 也可能代表「回合其實跑完了」**：`badturn` 那組——`t` 已經建出來（子行程真的跑
  過）、`.runi` 也正常刪掉了，只有 `turn` 停在壞值 `x`，退出碼 1。§B-3 只保證「讀不到」
  視為 0，不保證「讀到壞內容」也視為 0，所以這是設計內的行為——但當時 §D-9 的「1 ＝
  函式庫層失敗」那句話蓋不住它。**本節就是 S9 改寫 §D-9 的依據**：新條款把界線寫成
  「aos 自己跑不動或收不了尾」，並明說 1 不等於「這一回合沒有發生」。
- 空批次 `[]` 是合法投遞（`count:0`，§C-2），退出碼 0。

## 待補（後續步驟寫進來）

- 無。
