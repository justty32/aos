# aos-util

`libaos-util - aos 這一家命令列工具共用的小函式庫`（NAME，C-54 R1）

**一句話：aos 這一家命令列工具共用的小函式庫——錯誤型別與通用的錯誤代號、三扇門（stdin／stdout／stderr）、旗標（`aos/util/cli.hpp`）、設定檔、路徑與原子寫入、行程身分、時間與訊號。** 沒有執行檔，只出 `lib/libaos-util.a`。全家慣例見 [impls/README.md](../README.md)。

像一家店的共用倉庫：每支工具自己只放自己獨有的東西，「好幾支都要」的一律放這裡，一份就好。

## 用法

```cpp
int main() {
    try {
        aos::Json in = aos::read_stdin();      // stdin 一份 JSON
        return aos::emit(做事(in));             // stdout 一行、退 0
    } catch (const aos::Error& e) {
        return aos::fail("aos-x", e);           // stderr 一行「aos-x: error: 代號 原因」、退 1
    }
}
```

`parse_cli` 第五參數從常用預設表選短名，第六參數可傳各支自己的短名對照；各支可不同義，`-h` 隨 help 內建。`--help` 只在旗標位置觸發，作為前個旗標的值、第一個位置參數後或 `--` 後都照字面傳入。短名不黏值、不併、不帶 `=`；aos-exec 開 `-w`／`-s`，aos-llm ls 開 `-j`。

`read_stdin` 先用 `require_stdin_body()` 拒絕終端 stdin（`ArgumentsBad`），請從管線或檔案給內容；讀原始文字的命令也可先呼叫這個檢查。非終端的空輸入仍是 `{}`。

## 元素（一個標頭一個元素）

逐檔「哪個檔負責什麼」從檔頭一句話生成，在 code map 的 [逐檔表 impls.json](../../../wf/knowledge/code-map/proto8/impls.json)（`#/tree/aos-util`）；改說明去改檔頭。

標頭開頭都有白話說明，從那裡讀；原子寫入的原因另見 `src/files.cpp`。

## 公開介面：目錄、文字與訊號

`aos/util/files.hpp` 提供目錄操作與指定暫存路徑的文字原子寫入。

```cpp
bool is_dir(const std::string& path);
void make_dir(const std::string& dir);
std::vector<std::string> names_in(const std::string& dir, bool directories_only = false);
bool move(const std::string& from, const std::string& to);
void remove_tree(const std::string& path);

enum class TextWriteOperation { open, write, rename };
struct TextWriteError { TextWriteOperation operation; int number; };
std::optional<TextWriteError> write_text(const std::string& path, const std::string& text,
                                      const std::string& tmp);
```

- `is_dir` 用 error_code 查目錄，錯誤回 false。`make_dir` 遞迴建立；建立有錯或結果不是目錄就丟 `MkdirFailed`。
- `names_in` 忽略隱藏名字；預設收所有類型、不排序，`directories_only=true` 只收目錄並照字典序排序。建立 iterator 失敗回空、增量失敗停止並保留已收名字。
- `move` 成功回 true；遇 ENOENT／ENOTEMPTY／EEXIST 回 false，其他丟 `WriteFailed`。`remove_tree` 遞迴刪除並忽略錯誤。
- `write_text` 不建目錄、不修改文字；先以 open（0666 受 umask 影響，既有 tmp 保留權限）開啟指定 `tmp`，write 重試 EINTR，完整寫入並檢查 close 後 rename 至 `path`。成功回 nullopt；任一步失敗都嘗試 unlink tmp，回操作與 errno（close 失敗歸 write，write 回 0 歸 EIO），讓呼叫者決定錯誤代號與訊息。清 tmp 的錯誤忽略。

`aos/util/files.hpp` 另提供 `keep_bad` 與 `read_window`：前者把壞檔改名（或複製）留成 `<檔名>.bad-<UTC 毫秒時間>`，冒號換連字號、撞名加尾碼，失敗丟 WriteFailed；後者旁觀別人的 JSON 物件窗，缺檔安靜、讀不了／JSON 壞／根非物件則當沒有，每個行程對同一路徑只提醒一次，不改動對方檔案。

`aos/util/signals.hpp` 另提供 `sigset_t the_signals()`、`void block_signals()`、`int take_signal()`：同一組 SIGINT／SIGTERM／SIGHUP；開執行緒前阻擋，之後非阻塞取出一個訊號，沒有就回 0。`block_signals` 第一次呼叫時順手記下擋之前的遮罩。
給 aos-daemon 的 poke 用的兩個：`void block_more(const sigset_t&)` 額外擋一組訊號（例 daemon 的 poke 三訊號與 SIGUSR1／SIGUSR2），不改已記下的舊遮罩；`void restore_signals()` 給 fork 之後、exec 之前的子行程用，把遮罩還原成 `block_signals` 之前的樣子（含 `block_more` 多擋的一併解開；沒呼叫過 `block_signals` 就只解三個收工訊號），只用 async-signal-safe 呼叫、不配置記憶體。aos-loop 的 `run_folder` 與 aos-daemon 起子項都用它。

`aos/util/proc.hpp` 提供 `signal_group`、`proc_started_at_ticks`、`boot_id`、`utc_now_ms`、`utc_now_ns`、`utc_ms_at`、`unique_id`（無參數或指定奈秒）與 `identity`，供行程辨識、送訊號及產生時間與名稱。

## 公開介面：時鐘與兩鐘期限

`aos/util/clock.hpp` 提供 `now_cycle()`、`clock_interval_ms()`、`utc_now_epoch_ms()`、`Deadline`、`deadline_after(cycles)` 與 `expired(d)`。

- `AOS_CLOCK` 沒設或空＝沒有時鐘（`nullopt`）；有設而檔案不存在＝印一行英文 warning（每行程每路徑一次），仍當 0、不建檔；空白檔當 0、不提醒。有時鐘的期限只數格，凍住不過期。
- 沒時鐘時，用 `AOS_CLOCK_INTERVAL`（正整數毫秒，沒設或空＝1000）換成 UTC epoch 毫秒期限；能寫檔供跨行程比較。
- 時鐘內容不是非負 ASCII 十進位整數、讀不了、間隔非正整數或期限超出 signed 64-bit，丟通用 `ClockBad`，照一般錯誤退 1。
- Python 的工具版 `proto8/lib/tool_io.py` 與命令列版 `proto8/py/aos_ws.py` 提供同名函數，期限回 `(on_clock, at)`。

## 建置與測試

```sh
cmake -B build && cmake --build build
```

- 別的專案怎麼連、vcpkg、產物：見 [impls/README.md「建置」](../docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md#建置)。

## 已知限制

- 只支援 Linux（`/proc`、`killpg`、`sigtimedwait`）。
