# inst（libaos，C 版 aos_inst）

**一句話：一個很小的純 C 函式庫，只做一件事——起一個程式、等它結束、告訴你結果。**
沒有命令列、不讀 JSON，給其他語言用 C FFI 呼叫（Python ctypes、Rust、Go、Zig…）；[aos-exec](../aos-exec/README.md) 遇到 inst 單子時在行程內呼叫它（單子 JSON 的解析在 aos-exec 的 C++ 庫，不在這裡）。
全家慣例見 [impls/README.md](../README.md)（這個專案是純 C，名字沿用 dcap 的 C 模板：資料夾 `inst`、標頭 `aos.h`、函數 `aos_inst_*`）。

就像你請人幫忙跑腿：你填一張單子（`aos_inst_input_t`）寫清楚「做什麼（argv）、去哪（cwd）、帶什麼（envs、stdin）、
東西放哪（stdout／stderr）、最晚幾點回來（timeout_ms）」，他回來時在回條（`aos_inst_result_t`）上寫「辦完了，結果是幾號；
或是超時了，被叫回來」。盡量少做事：路徑一律絕對路徑、找程式交給 glibc 的 `execvp`、不幫忙建資料夾、不 malloc。

```c
aos_inst_input_t in = {
    .argv = (const char *const[]){"sh", "-c", "echo hi; exit 3", NULL},
    .cwd = "/tmp",
    .paths = {NULL, "/tmp/out.txt", NULL},   // 一律絕對路徑
    .timeout_ms = 5000,
    .grace_ms = 2000,
};
aos_inst_result_t r;
int rc = aos_inst_exec(&in, &r);
if (rc != AOS_INST_OK) printf("lib 出錯：%s\n", aos_inst_strerror(rc));
else printf("%d %d %llu\n", r.code, r.timed_out, r.ms);   // 3 0 11 左右
```

## 用法（介面）

```c
#include "aos.h"

int aos_inst_exec(const aos_inst_input_t *in, aos_inst_result_t *out);   // 一步：起、等、填結果
const char *aos_inst_strerror(int code);   // 錯誤代號 → "CommandNotFound" 這種名字

// 兩步：要在子程式跑的期間做別的事（例如把收到的訊號轉給它）時用
int aos_inst_start(const aos_inst_input_t *in, aos_inst_proc_t *proc);  // 起好就回，pid 在 proc->pid
int aos_inst_wait(aos_inst_proc_t *proc, aos_inst_result_t *out);       // 等到結束（含 timeout／grace），填結果
```

`aos_inst_exec` 就是 `aos_inst_start`＋`aos_inst_wait` 兩行。兩步用法的規矩：

- `aos_inst_proc_t` 由呼叫者配置（放 stack 就好）。**呼叫者只讀 `pid`**，其他欄位是 wait 要用的，別碰。
- `start` 回非 0＝子程式沒起來（代號同下表），這時不呼叫 `wait`，`proc` 也不會被動到。
- `start` 回 0 之後**一定要呼叫一次 `wait`**：不然子程式結束後變殭屍（沒人收屍），pidfd 也漏掉。
- `timeout_ms` 從 `start` 開始算；`wait` 可以在別條執行緒呼叫（例如主執行緒 start、送訊號，工人執行緒 wait）。
- `wait` 回 `WaitFailed`／`KillFailed` 時 `out` 的樣子跟 `aos_inst_exec` 一樣（`pid`、`timed_out`、`ms` 有填，`code`＝-1）。

**單子** `aos_inst_input_t`：全零（`aos_inst_input_t in = {0};`）＝全部用預設，只有 `argv` 一定要填。

| 欄位 | 意思 | 零值＝ |
|---|---|---|
| `argv` | NULL 結尾的字串陣列，至少一個（必填）；`argv[0]` 交給 `execvp` | — |
| `cwd` | 在哪個資料夾跑：絕對路徑，要已經存在、進得去（x） | 呼叫者現在的 cwd |
| `envs` | 子程式的完整環境：NULL 結尾的 `"KEY=VALUE"` 陣列，原樣給 | 沿用呼叫者的環境 |
| `paths[3]` | stdin、stdout、stderr 接哪個檔：絕對路徑 | `/dev/null` |
| `appends[3]` | [1][2]：附加在檔尾 | 清空再寫 |
| `merge` | stderr 併進 stdout（這時 `paths[2]` 要是 NULL） | 分開 |
| `timeout_ms` | 最多跑幾毫秒 | 不限時 |
| `grace_ms` | 時間到先 SIGTERM，過這麼久再 SIGKILL | 直接 SIGKILL |
| `inherits[3]` | stdin、stdout、stderr 直接用呼叫者自己的 fd 0／1／2（不開檔；這時 `paths[i]` 要是 NULL） | 照 `paths[i]` |
| `new_session` | 子程式 exec 前 `setsid()` 自成行程群組；timeout 收掉時整群送 | 跟呼叫者同群組、只收直接子程式 |

`inherits`、`new_session` 是後加的（放在結構尾端），全零＝跟加之前一模一樣。

規矩（不合就報錯，lib 不幫忙補）：

- **路徑一律絕對路徑**：`cwd`、`paths[i]` 不是 NULL 就要以 `/` 開頭，否則回 `PathNotAbsolute`（空字串也算）。
- **找程式交給 glibc 的 `execvp`**（lib 自己不搜尋）：`argv[0]` 有 `/`（`"/bin/ls"`、`"./x"`）就直接用，相對的從 `cwd` 算；
  沒有 `/`（`"ls"`）就照**子程式那份環境**的 PATH 找——`envs` 不是 NULL 就看 `envs` 裡的 PATH。
  做法：子行程在 exec 前先 `environ = envs`，再 `execvp`，所以找程式用的 PATH 和子程式看到的環境是同一份
  （改 `environ` 只發生在 fork 出來的子行程，不影響呼叫者）。另外兩點 glibc 行為：
  - 環境裡沒有 PATH 時，glibc 用它自己的預設路徑。
  - PATH 是空字串＝只在 cwd 找（glibc 把空的一段當成目前資料夾；實測如此，`tests/test_lib.c` 有測）。
  - 檔案有執行權限但不是可執行格式（例如沒有 `#!` 的腳本），glibc 會改用 `/bin/sh` 跑它：回 OK、`code` 由 sh 決定
    （內容不是 shell 指令的話通常是 126／127），不是 `LaunchFailed`。
- **不建資料夾**：stdout／stderr 的檔不在會建，但上層資料夾要已經存在，否則 `OpenFailed`。
- **環境原樣給**：`envs` 是 NULL＝子程式沿用呼叫者現在的環境；不是 NULL＝**就是子程式的完整環境**，lib 不接、不去重、不補。
  要在呼叫者的環境上改一點，自己組好一份完整的。Python 例：
  `envs = ["%s=%s" % kv for kv in {**os.environ, "PATH": "/my/bin:" + os.environ["PATH"]}.items()]`

**回條** `aos_inst_result_t`：`code`（退出碼；被訊號停掉＝128＋N）、`signal`（0＝沒有）、`timed_out`、`pid`、`ms`。

- `timed_out=true` 時 `signal` 也可能是 0：子程式在送訊號前剛好結束，或收到 SIGTERM 後自己 `exit`。是不是被收掉，以 `timed_out` 為準。
- 子程式沒起來就出錯：`out` 不會被動到。子程式起來之後才出錯（`WaitFailed`／`KillFailed`）：`pid`、`timed_out`、`ms` 有填，
  `code`＝-1、`signal`＝0。

**回傳值**（`aos_inst_error_t` 的值；函數型別寫 `int`，FFI 比較好接）：`AOS_INST_OK`（0）＝成功跑完，子程式回幾號、
被限時收掉都算成功；其他＝lib 自己出錯：

| 常數 | `aos_inst_strerror` | 什麼時候 |
|---|---|---|
| `AOS_INST_ERR_FIELD_TYPE` | FieldType | `in`／`out` 是 NULL、`argv` 是 NULL 或空 |
| `AOS_INST_ERR_PATH_CONFLICT` | PathConflict | `merge` 又給了 `paths[2]` 或 `inherits[2]`；`inherits[i]` 又給了 `paths[i]` |
| `AOS_INST_ERR_PATH_NOT_ABSOLUTE` | PathNotAbsolute | `cwd` 或 `paths[i]` 不是 `/` 開頭 |
| `AOS_INST_ERR_CWD_MISSING` | CwdMissing | `cwd` 不存在、不是資料夾、或沒有進去的權限（x） |
| `AOS_INST_ERR_OPEN_FAILED` | OpenFailed | 串流的檔開不了（上層資料夾不在、是資料夾…） |
| `AOS_INST_ERR_COMMAND_NOT_FOUND` | CommandNotFound | `argv[0]` 那個檔不存在，或照 PATH 找不到 |
| `AOS_INST_ERR_COMMAND_NOT_EXECUTABLE` | CommandNotExecutable | 沒有執行權限 |
| `AOS_INST_ERR_LAUNCH_FAILED` | LaunchFailed | 其他起不來的原因 |
| `AOS_INST_ERR_WAIT_FAILED` | WaitFailed | 收不到子程式的結果（見下面訊號） |
| `AOS_INST_ERR_KILL_FAILED` | KillFailed | 時間到要收子程式，`kill` 卻失敗（例如子程式 exec 了 setuid 程式＝`EPERM`）。lib 不再等，子程式可能還在跑、還沒收屍，`out->pid` 有填，呼叫者自己處理 |

## 元素（檔案）

- `include/aos.h`：公開介面（給 FFI 看這個就夠）
- `src/inst_exec.c`：`aos_inst_start`（由上往下：檢查參數、組環境、開串流、起子程式）、`aos_inst_wait`（等、收、填結果）、`aos_inst_exec`（兩個接起來）和 `aos_inst_strerror`——**從這裡讀起**
- `src/inst_stream.c`：開三個串流的檔
- `src/inst_proc.c`：fork＋exec、等（pidfd＋poll，退路 1 毫秒輪詢）、時間到收掉
- `src/inst_internal.h`：上面幾個檔之間共用的內部宣告（不安裝、不匯出；名字都是 `inst_` 開頭）
- `tests/test_lib.c`：C 測試；`tests/test_ffi.py`：Python ctypes 測試

## 為什麼這樣做

**訊號**：lib 不碰——不裝 handler、不改你的訊號遮罩、不轉送。Ctrl-C 怎麼處理是呼叫者的事
（子程式跟你同一個行程群組，終端機的 Ctrl-C 會一起送到它；`new_session` 時不會，見下）。子程式在 exec 前把訊號處置恢復預設、遮罩清空。
如果你把 SIGCHLD 設成 SIG_IGN，或別的執行緒用 `waitpid(-1)` 搶收子程式，會拿到 `WaitFailed`。

**執行緒**：沒有全域狀態，多條執行緒可以同時呼叫。極端情況：別的執行緒剛好同時 `fork` 的話，那個子行程會短暫繼承
lib 用來回報 exec 失敗的 pipe（帶 CLOEXEC，它 exec 後就關），這段期間 lib 會多等一下。

**收掉只管直接子程式**（預設）：timeout 到了，SIGTERM／SIGKILL 只送給 lib 起的那個子程式。它自己再起的孫程式
（例如 `sh -c 'sleep 100 & wait'` 裡的 `sleep`）會留著；要整群收掉是外層的事。

**`new_session`＝整群收**：子程式 exec 前先 `setsid()`，自成一個 session／行程群組（群組號＝它的 pid）；
timeout 的 SIGTERM／SIGKILL 改送 `kill(-pid, …)`，孫程式一起收掉（孫程式自己又開新群組的不算）。
順序跟預設一樣：SIGTERM → 直接子程式在 grace 內結束就收工 → 否則整群 SIGKILL（同 Python 版 `_stop` 的 `killpg`）。
代價：子程式不再跟呼叫者同一個前景群組，終端機的 Ctrl-C 不會自動送到它（要轉送是呼叫者的事：
對 `-proc->pid` 送就是整群），它也沒有控制終端、讀不了終端。lib 仍然不碰訊號處理。

**`inherits`＝接呼叫者的串流**：`inherits[i]`＝true 時那個串流不開檔，子程式直接拿呼叫者的 fd 0／1／2
（呼叫者的 fd 是什麼就是什麼：檔、管道、socket、終端都行；關著就是關著）。跟下面「寫 `/dev/stdout`」那招不同：
不重開檔，所以不會清空呼叫者的輸出檔，socket 也接得上。`merge`＋`inherits[1]`＝stderr 併進呼叫者的 fd 1。

**溢位**：`timeout_ms`、`grace_ms` 大到「現在＋它」溢位（例如 FFI 傳 -1）時：timeout＝實質不限時，grace＝一直等 SIGTERM 生效。

**ABI 尚未凍結**：三個結構體沒有版本欄位，日後加欄位時，用 FFI 的呼叫端（例如 ctypes 的 `Structure`）要跟著改。

**怎麼等子程式**：Linux 5.3+ 用 `pidfd_open`＋`poll`——子程式一結束 `poll` 就醒，再 `waitpid` 收屍；
期限（timeout、grace）就是 `poll` 的逾時。拿不到 pidfd（核心太舊 `ENOSYS`、被 seccomp 擋 `EPERM`…）就退回
每 1 毫秒 `waitpid(WNOHANG)` 看一次。`ms` 以毫秒為單位：pidfd 路跑 `/bin/true` 大約 0 毫秒，退路最多多約 1 毫秒。
編譯時加 `-DAOS_INST_NO_PIDFD` 可以強制走退路（`ctest` 兩條路都會測）。

**串流的幾個坑**：

- **接呼叫者自己的輸出**：最簡單是 `inherits[1]`（見上）。另一條舊路：`paths[1]` 寫 `"/dev/stdout"`（stderr 同理）時，`appends[1]` 要設 `true`。否則呼叫者的 stdout 若是檔案（`./prog > log.txt`），開的時候會先把 `log.txt` 清空。呼叫者的 stdout 是 socket 時，`/dev/stdout` 開不了，回 `OpenFailed`。
- **FIFO（具名管道）**：路徑不要給另一端沒人接的 FIFO。`open` 會一直卡住，這時子程式還沒起來，`timeout_ms` 管不到。
- **路徑是捷徑（symlink）會照著走**：跟 shell 的 `>` 一樣（`/dev/stdout` 本身就是捷徑，所以不能加 `O_NOFOLLOW`）。
  斷掉的捷徑會建出它指向的檔再寫進去。在多人可寫的資料夾（如 `/tmp`）要小心別人事先放好的捷徑，可能讓你寫到別處。
- **stdout、stderr 給同一個路徑**：沒設 `merge` 的話兩邊各開一次、各自從頭寫，會互相蓋掉。要合在一起請用 `merge`。

## Python ctypes 範例

```python
import ctypes

class Input(ctypes.Structure):     # 欄位順序、型別要跟 aos.h 一模一樣
    _fields_ = [("argv", ctypes.POINTER(ctypes.c_char_p)), ("cwd", ctypes.c_char_p),
                ("envs", ctypes.POINTER(ctypes.c_char_p)),
                ("paths", ctypes.c_char_p * 3), ("appends", ctypes.c_bool * 3), ("merge", ctypes.c_bool),
                ("timeout_ms", ctypes.c_ulonglong), ("grace_ms", ctypes.c_ulonglong),
                ("inherits", ctypes.c_bool * 3), ("new_session", ctypes.c_bool)]

class Result(ctypes.Structure):
    _fields_ = [("code", ctypes.c_int), ("signal", ctypes.c_int), ("timed_out", ctypes.c_bool),
                ("pid", ctypes.c_long), ("ms", ctypes.c_ulonglong)]

lib = ctypes.CDLL("./lib/libinst.so")
lib.aos_inst_exec.argtypes = [ctypes.POINTER(Input), ctypes.POINTER(Result)]
lib.aos_inst_strerror.restype = ctypes.c_char_p

argv = (ctypes.c_char_p * 4)(b"sh", b"-c", b"echo hi; exit 3", None)
inp = Input(argv=argv, cwd=b"/tmp", timeout_ms=5000, grace_ms=2000)   # 沒寫的欄位＝零＝預設
inp.paths[1] = b"/tmp/out.txt"                                        # 一律絕對路徑
r = Result()
rc = lib.aos_inst_exec(ctypes.byref(inp), ctypes.byref(r))
if rc != 0:
    print("lib 出錯：", lib.aos_inst_strerror(rc).decode())
else:
    print(r.code, r.timed_out, r.ms)   # 3 False 11 左右
```

`argv` 這類陣列要自己留著參照（像上面的變數 `argv`），呼叫途中被回收就會讀到垃圾。完整一點的寫法看 `tests/test_ffi.py`。

## 跟 Python 版（aos_inst.py）的差異

| | aos_inst.py | libaos |
|---|---|---|
| 輸入 | JSON／命令列旗標／TARGET 檔、指示詞 | 一個 C 結構體 |
| envs | `{名字: 值}`，同名的由 envs 蓋過 | `"KEY=VALUE"` 陣列＝完整環境（NULL＝沿用呼叫者的），不接不去重 |
| 路徑 | 相對路徑從 cwd 算 | 一律絕對路徑，否則 `PathNotAbsolute` |
| 找程式 | 照子程式那份環境的 PATH 找 | `execvp`：一樣照子程式那份環境的 PATH 找 |
| 建資料夾 | `cwd_mkdir`、`stdout_mkdir`… | 都不建 |
| timeout | `timeout_ms` null＝不限 | `timeout_ms` 0＝不限 |
| grace_ms | 沒寫＝2000 | 沒寫（0）＝直接 SIGKILL |
| 訊號 | 收到 INT／TERM／HUP 轉給子程式，過 grace 再 SIGKILL | 完全不管 |
| 串流沒寫 | 接呼叫者的 | `/dev/null`；要接呼叫者的設 `inherits[i]` |
| 行程群組 | 子程式自成群組（`start_new_session`），逾時 `killpg` 整群 | 預設同群組、只收直接子程式；`new_session` 時同 Python 版 |
| 結果 | `{"id", "code", "signal", ...}`，signal 沒有＝null | 結構體，沒有 `id`；signal 沒有＝0 |
| 錯誤 | 丟 `InstError(code, msg)` | 回 int 代號，只有名字沒有訊息；多 `PathNotAbsolute`、`WaitFailed` |
| 記憶體 | — | 不 malloc |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- 產物：`lib/libinst.so`（給 FFI：Python ctypes、Rust、Go…）和 `lib/libinst.a`（給 [aos-exec](../aos-exec/README.md) 靜態連進去，啟動時少載入一個 .so；10-16～17 那代的 aos-inst 也連它）。
  同一份原始碼只編一次（CMake 的 OBJECT library），再包成兩種。沒有執行檔。
- 一定會加 `-std=c11 -Wall -Wextra -Werror`、`-fPIC`、預設 hidden。`.so` 只匯出 `aos_inst_exec`、`aos_inst_start`、`aos_inst_wait`、
  `aos_inst_strerror` 四個符號（`nm -D lib/libinst.so` 看得到）。
- `ctest` 跑三個：`test_lib`（C 測試，走 pidfd 路）、`test_lib_nopidfd`（同一支測試、lib 加 `-DAOS_INST_NO_PIDFD` 強制走輪詢退路）、
  `test_ffi`（Python ctypes 載 `lib/libinst.so`）。
- 換編譯器：`CC=clang cmake -B build ...`。純 C、不用 vcpkg，所以不 include 全家的 `cmake/settings.cmake`。
- 別的 dcap 專案要用它：`add_subdirectory(../inst inst-build)` 再連 `inst`（.so）或 `inst-static`（.a）。

## 寫法

一行一件事：不在 if 條件裡賦值、不串長的 `&&`／`||`（先算成有名字的 bool，或拆成巢狀 if）、每個 if 都加 `{}`。
排版用 `clang-format --style=LLVM`（2 格縮排、80 欄），編輯器存檔自動排版也不會改動。
