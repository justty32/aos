# C API

這份文件回答「C99 或其他 FFI 呼叫端如何用穩定的 C ABI 建立、解析與執行一筆
instruction，以及如何投遞一批 instruction」。它不提供容器式的批次型別，交接協定也只
開放**投遞**那一步（`aos_deliver_*`，見下面的〈投遞〉）；需要批次容器、彙整、取件與
釋放時用 [C++ API](cxxapi.md)，只想操作命令列則看[使用說明](../../../docs/usage.md)。

公開的 C ABI 由 `<aos/inst.h>` 宣告。這個標頭相容 C99，不含任何 C++ 型別，並
對外提供一個不透明的 `aos_instruction` handle。

## 建置與連結

CMake 會產生供連結期使用的 `libaos_inst.so`、SONAME `libaos_inst.so.0`，
以及帶版號的函式庫 `libaos_inst.so.0.1.0`（CMake target 是 `aos::inst`）。
從儲存庫根目錄、建置目錄為預設的 `build/` 時，用以下指令編譯用戶端程式：

```sh
cc -std=c99 example.c -Icore/inst/include -Icommon/include \
   -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst
```

`-laos_inst` 在連結時會挑選 `libaos_inst.so`；動態載入器則會記錄並載入它的
SONAME。上面的 rpath 對於尚未安裝的建置很方便。已安裝或已封裝的用戶端則應改為
把 `libaos_inst.so.0` 放到平台正常的函式庫搜尋路徑上。如果用戶端本身也是
CMake 專案，改用 `find_package(aos CONFIG REQUIRED)` 再連 `aos::inst` 更省事
（見[架構](architecture.md)）——上面這行手動旗標是給不透過 CMake 的場合用的。

（若某次建置額外開了 `AOS_BUILD_MERGED_LIB`，還會多產出一份把所有小專案合在
一起的單檔 `libaos.so`／target `aos::merged`；那是另一個獨立的產出，跟本節
講的 `libaos_inst.so` 不是同一個檔案。）

## 完整範例

```c
#include <aos/inst.h>

#include <stdio.h>
#include <stdlib.h>

int main(void) {
    static const char record[] =
        "{\"argv\":[\"printf\",\"hello from C\\n\"],"
        "\"exit\":\"status.txt\"}";
    aos_instruction *inst = aos_instruction_new();
    aos_exec_result result;
    aos_inst_state istate;
    aos_exec_state estate;
    char *encoded = NULL;
    size_t needed = 0;
    int rc = 1;

    if (inst == NULL) {
        fputs("allocation failed\n", stderr);
        return 1;
    }

    istate = aos_instruction_read_buffer(record, sizeof record - 1, inst);
    if (istate != AOS_INST_OK) {
        fprintf(stderr, "parse: %s\n", aos_inst_state_string(istate));
        goto done;
    }

    estate = aos_instruction_execute(inst, &result);
    if (estate != AOS_EXEC_OK) {
        fprintf(stderr, "execute: %s (errno %d)\n",
                aos_exec_state_string(estate), result.error);
        goto done;
    }
    printf("child status=%d signalled=%d timed_out=%d\n",
           result.status, result.signalled, result.timed_out);

    istate = aos_instruction_write_buffer(inst, NULL, 0, &needed);
    if (istate != AOS_INST_BUFFER_TOO_SMALL) goto done;
    encoded = (char *)malloc(needed + 1);
    if (encoded == NULL) goto done;
    istate = aos_instruction_write_buffer(inst, encoded, needed + 1, &needed);
    if (istate != AOS_INST_OK) goto done;
    fputs(encoded, stdout);
    rc = 0;

done:
    free(encoded);
    aos_instruction_free(inst);
    return rc;
}
```

這段程式解析一筆指令、執行它、印出結果、把指令序列化，並釋放所有自己持有的
配置。

把它存成 `example.c`，依上面的編譯指令產生 `a.out` 後執行 `./a.out`，會看到：

```text
hello from C
child status=0 signalled=0 timed_out=0
{"argv":["printf","hello from C\n"],"exit":"status.txt"}
```

目前目錄也會產生內容為 `0` 加換行的 `status.txt`。

## 生命週期與欄位

`aos_instruction_new()` 會建立一筆預設指令，並在配置失敗時回傳 `NULL`。
`aos_instruction_clear()` 會還原成預設值，而 `aos_instruction_free()` 接受
`NULL`。

argv 請使用 `aos_instruction_push_arg()` 搭配 `aos_instruction_argc()` 與
`aos_instruction_arg()`。五個字串欄位透過欄位的 getter/setter 以
`AOS_FIELD_STDIN`、`STDOUT`、`STDERR`、`EXIT` 與 `CWD` 來選取。環境變數項目則
使用 count/key/value 的 getter 與 `aos_instruction_set_env()`；設定一個已存在
的 key 會取代它。key 依字典序排列，必須非空，且不能包含 `=`。逾時的
getter/setter 值以毫秒為單位；零會停用截止時間。
`aos_instruction_stderr_merge()`／`aos_instruction_set_stderr_merge()` 操作 stderr
併流旗標；`aos_instruction_parallel()`／`aos_instruction_set_parallel()` 操作批次中的
並行旗標。兩者皆以零表示 false、非零表示 true。

所有 setter 都會複製它們的字串。getter 回傳的字串是借用(borrowed)的、以 NUL
結尾，且只在該指令被變更、清除、讀入或釋放之前有效。無效的 handle、欄位與
索引會依回傳型別回傳其記載的無效狀態、零或 `NULL`。

## 讀取、寫入與執行

讀寫各有三個入口，成對出現：

| 來源／目的 | 讀 | 寫 |
| --- | --- | --- |
| 記憶體 | `aos_instruction_read_buffer()` | `aos_instruction_write_buffer()` |
| 已開啟的 fd | `aos_instruction_read_fd()` | `aos_instruction_write_fd()` |
| 檔案路徑 | `aos_instruction_read_file()` | `aos_instruction_write_file()` |

`read_buffer()` 從提供的位元組中剛好解析一個 JSON 指令物件。
`read_fd()` 會一路讀到 EOF、讓呼叫端持有的 fd 保持開啟、將其標記為
close-on-exec、對被中斷的讀取進行重試。
`read_file()` 自己用 `O_RDONLY | O_CLOEXEC` 開檔、讀到 EOF、然後關掉自己開的
那個 fd；呼叫端不需要碰 fd。三者都會在解析前清除目的地，都只接受單一指令物件、
不接受批次陣列，也都不使用 `FILE *`。

`write_fd()` 序列化之後把全部位元組寫進呼叫端的 fd（處理部分寫入與 `EINTR`），
不關閉它、也不動它的 flag，**也不替你 `fsync`**——那個 fd 是你的，要不要落盤、什麼時候
落盤由你決定。`write_file()` 用
`O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC`（權限 0666）開檔、寫完、`fsync`、關檔，
`fsync` 或關檔失敗都算成失敗——寫入路徑上的 `close()` 錯誤可能代表資料沒落地。
截斷而非附加，跟 `exit` 欄位同一個慣例。

**`write_file()` 是先驗證、後開檔**：指令無效時它回傳對應的驗證狀態，而那個檔案
連建立或截斷都不會發生。所以一次失敗的寫出不會毀掉目標檔案既有的內容。

開檔、讀取或寫入失敗會回傳 `AOS_INST_READ_ERROR` 或 `AOS_INST_WRITE_ERROR`，
並讓 `errno` 保持在失敗那個 syscall 設定的值。這兩個狀態不區分「檔案不存在」與
「I/O 錯誤」——要那個區別就自己看 `errno`。

沒有任何上限：`read_fd()` 與 `read_file()` 都會一直讀到 EOF，`argv`、`env` 與
JSON 巢狀深度也都不設上界。記憶體用量由輸入大小決定，配置失敗會回報成
`AOS_INST_ALLOC_FAILED`。要設界是呼叫端的責任（`ulimit`、cgroup，或在餵進來之前
自己先量）。深層巢狀的輸入會讓解析器遞迴爆堆疊而崩潰，那不是一個可回報的狀態
——只餵可信來源的指令檔。

只有 `write_buffer()` 採用兩次呼叫的大小查詢，如範例所示。所需的位元組數包含
最後的 LF，但不含為方便而附加的 NUL。緩衝區必須能容納 `needed + 1` 個位元組。
查詢或緩衝區過小的呼叫會回傳 `AOS_INST_BUFFER_TOO_SMALL`、回報所需的數量，並讓
緩衝區維持原狀不動。`write_fd()` 與 `write_file()` 不需要這套協定——它們自己知道
要寫多少。

`aos_instruction_execute()` 會重置一個非 NULL 的 result、等待命令完成，並回傳
一個 `aos_exec_state`。result 的 `status` 是子行程的離開值或 `128 + signal`；
`signalled` 標示因訊號而終止，`timed_out` 標示由函式庫發起的逾時，而 `error`
則為適用的 API 失敗攜帶 `errno`。子行程若回傳如 1、126 或 127 這類狀態，仍會
回傳 `AOS_EXEC_OK`。完整規則請見[execution semantics](exec.md)。

回傳狀態字串的函式會回傳靜態的診斷字串，而 `aos_version_string()` 會回報函式庫
版本。這套 API 不再揭露任何上限查詢函式，因為已經沒有上限可查。C++ 例外絕不會跨越 C
邊界：回傳狀態的操作會把它們對應成配置失敗；其他回傳形式則使用 `NULL` 或零，
而 void 的清理操作則會抑制它們。

## 投遞（deliver）

投遞是三步交接協定裡唯一由外部生產者執行的一步
（[SPEC](../../../docs/SPEC.md) §D-3），所以 C ABI 也開放它。協定細節——唯一檔名
`<pid>-<seq>.json`、先寫 `.temp` 再排他 `rename`、發布 canonical 位元組、目錄
`fsync`——全部包在函式裡；行為與 C++ 的 `aos::deliver_instructions()` 完全相同，
細節見 [handoff 指南](handoff.md)。

```c
typedef enum aos_handoff_state {
    AOS_HANDOFF_OK = 0,
    AOS_HANDOFF_INVALID_ARGUMENT = 1,
    AOS_HANDOFF_BUSY = 2,
    AOS_HANDOFF_NO_INSTRUCTION = 3,
    AOS_HANDOFF_INBOX_READ_FAILED = 4,
    AOS_HANDOFF_INSTRUCTION_READ_FAILED = 5,
    AOS_HANDOFF_PUBLISH_WRITE_FAILED = 6,
    AOS_HANDOFF_RENAME_FAILED = 7,
    AOS_HANDOFF_RELEASE_FAILED = 8,
    AOS_HANDOFF_DELIVERY_INVALID = 9,
    AOS_HANDOFF_ALLOC_FAILED = 10,
    AOS_HANDOFF_READ_ERROR = 11,
    AOS_HANDOFF_BUFFER_TOO_SMALL = 12
} aos_handoff_state;

#define AOS_DELIVER_NAME_MAX 64

typedef struct aos_deliver_result {
    size_t count;
    aos_inst_state inst_state;
    size_t error_record;
    int error;
    int sync_error;
} aos_deliver_result;

aos_handoff_state aos_deliver_buffer(
    const char *instruction_path, const char *data, size_t size,
    char *name, size_t name_size, size_t *needed,
    aos_deliver_result *result);
aos_handoff_state aos_deliver_file(
    const char *instruction_path, const char *path,
    char *name, size_t name_size, size_t *needed,
    aos_deliver_result *result);
const char *aos_handoff_state_string(aos_handoff_state state);
```

`instruction_path` 是那個世界的 instruction base path（例如 `.aos/inst.json`）；收件匣
是從它推導的（`.json` → `.tempd`），**必須已經存在**——不存在回
`AOS_HANDOFF_INBOX_READ_FAILED`，不會替你建世界。`aos_deliver_buffer()` 投的是記憶體
裡的位元組，`aos_deliver_file()` 先把檔案讀到 EOF 再投，開檔或讀取失敗回
`AOS_HANDOFF_READ_ERROR`。

值 0–9 鏡射 C++ 的 `aos::HandoffState`，10 起是 C ABI 專屬的延伸（配置失敗、讀取失敗、
緩衝區太小），跟 `aos_inst_state` 是同一套做法。`aos_handoff_state_string()` 回傳靜態
診斷字串（`"Ok"`、`"InboxReadFailed"`、`"BufferTooSmall"`…）。

診斷都在 `aos_deliver_result` 裡，`result` 可以傳 `NULL`：`count` 是這批幾筆（空批次
`[]` 合法，`count` 為 0）；驗證失敗（`AOS_HANDOFF_DELIVERY_INVALID`）時看 `inst_state`
與 `error_record`（第幾筆出問題，1 起算，還沒進到逐筆解碼時為 0）；`error` 是依狀態而
定的 `errno`；`sync_error` 非 0 代表**投遞已經完成**、只是收件匣目錄的 `fsync` 失敗
（警告，不是失敗）。

### `needed` 不是「先探大小」

`aos_instruction_write_buffer()` 那種「先用 `NULL` 問長度、再配置、再呼叫一次」的兩段式
協定，**在這裡不適用**：

- **呼叫一次就投遞一次。** 副作用在函式回來之前就發生了；第二次呼叫是**另一份新的
  投遞**，不是重試。
- `name`／`name_size` 只影響「能不能把投遞後的檔名回報給你」。`name` 為 `NULL` 或緩衝區
  裝不下（需要 `needed + 1` 個位元組，含結尾的 NUL）時，投遞**已經完成**，函式回
  `AOS_HANDOFF_BUFFER_TOO_SMALL` 並把實際長度寫進 `needed`——**看到這個狀態不要重打**，
  重打會多投一份。
- 給 `AOS_DELIVER_NAME_MAX`（64 位元組）就永遠不會遇到它：`<pid>-<seq>.json` 在任何平台
  上都塞得進去。
- `needed` **不得為 `NULL`**（傳 `NULL` 回 `AOS_HANDOFF_INVALID_ARGUMENT`）。
  `instruction_path` 為 `NULL`、`aos_deliver_file()` 的 `path` 為 `NULL`，或
  `aos_deliver_buffer()` 的 `data` 為 `NULL` 而 `size` 非零，同樣回
  `AOS_HANDOFF_INVALID_ARGUMENT`——這些是純參數錯誤，**不會**投遞。

### 例子

在一個已經有 `inst.tempd/` 的目錄裡投一批（base 用相對路徑，所以要在那個目錄裡跑）：

```c
#include <aos/inst.h>

#include <stdio.h>

int main(void) {
    static const char batch[] = "[{\"argv\":[\"printf\",\"hi\\n\"]}]";
    char name[AOS_DELIVER_NAME_MAX];
    size_t needed = 0;
    aos_deliver_result result;
    aos_handoff_state state;

    state = aos_deliver_buffer("inst.json", batch, sizeof batch - 1, name,
                               sizeof name, &needed, &result);
    if (state != AOS_HANDOFF_OK) {
        fprintf(stderr, "deliver: %s (errno %d)\n",
                aos_handoff_state_string(state), result.error);
        return 1;
    }
    printf("delivered %s count=%zu\n", name, result.count);
    return 0;
}
```

存成 `deliver.c`，用本檔開頭那行編譯指令產生執行檔，在備好收件匣的目錄裡執行：

```text
delivered 91715-0.json count=1
```

（`91715` 是實跑當下的 pid，每次都不一樣。）換到一個沒有 `inst.tempd/` 的目錄再跑，
就會看到：

```text
deliver: InboxReadFailed (errno 2)
```

## 執行緒

這套 API 可以安全地在多執行緒行程中使用。具體來說，執行會在 `fork` 之前，於
父行程中完整地合併環境、配置 `argv`/`envp` 並解析 PATH。子行程接著在 `execve`
之前只使用 async-signal-safe 的 POSIX 操作，藉此避開其他執行緒留下的配置器
鎖。

不同的 handle 可以並行使用。單一 handle 沒有內部鎖：請勿並行變動它、在另一個
執行緒正變動它時執行它，或在變動之後仍保留一個借用的 getter 指標。與其他
行程層級(process-wide)的 API 一樣，呼叫端也必須同步對行程環境的並行變更。

## ABI 穩定性

SONAME 就是 ABI 的邊界。相容的釋出版本會保留 `libaos_inst.so.0`；不相容的變更則
需要一個新的 SOVERSION。只要保留該 SONAME，既有的已匯出函式簽章、公開的結構
佈局，以及既有的列舉數值都不會改變。列舉值是凍結的，新值只能被附加，絕不會
透過重新編號插入，也不會被重複使用。

這道凍結從第一個標記出來的釋出版本起算。在那之前（目前仍是這個狀態，尚無任何
release tag）列舉值仍會重新編號：移除各種上限所對應的狀態時，後面的值就往前
遞補過了。

新的函式與被附加的列舉值是可以新增的。不透明的 `aos_instruction` 內部結構、
診斷文字、實作細節，以及版本號，都可以在不破壞 C ABI 的
情況下改變。編譯期的 `AOS_VERSION_*` 巨集描述的是標頭；載入的函式庫請改用
`aos_version_string()`。
