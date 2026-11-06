# aos-util

`libaos-util - aos 這一家命令列工具共用的小函式庫`（NAME，C-54 R1）

**一句話：aos 這一家命令列工具共用的小函式庫——錯誤型別與通用的錯誤代號、三扇門（stdin／stdout／stderr）、旗標（`aos/util/cli.hpp`；較早一代沒人叫的 `aos/flags.hpp` 11-04 刪了）、設定檔、路徑與原子寫入、行程身分、時間與訊號。** 沒有執行檔，只出 `lib/libaos-util.a`。全家慣例見 [impls/README.md](../README.md)。

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

`parse_cli` 的內建短名表與 Python 的 `aos_flags.SHORT` 同義；`parse_cli` 第五參數只開選中的短名，`-h` 隨 help 內建。短名不黏值、不併、不帶 `=`；aos-exec 開 `-w`／`-s`，aos-llm ls 開 `-j`。

`read_stdin` 先用 `require_stdin_body()` 拒絕終端 stdin（`ArgumentsBad`），請從管線或檔案給內容；讀原始文字的命令也可先呼叫這個檢查。非終端的空輸入仍是 `{}`。

## 元素（一個標頭一個元素）

逐檔「哪個檔負責什麼」從檔頭一句話生成，在 code map 的 [proto8 生成冊](../../../wf/workflows/common/code-map/proto8/README.md)（`impls` 冊的 `aos-util/` 段）；改說明去改檔頭。

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

`aos/util/signals.hpp` 另提供 `sigset_t the_signals()`、`void block_signals()`、`int take_signal()`：同一組 SIGINT／SIGTERM／SIGHUP；開執行緒前阻擋，之後非阻塞取出一個訊號，沒有就回 0。

`aos/util/proc.hpp` 提供 `signal_group`、`proc_started_at_ticks`、`boot_id`、`utc_now_ms`、`utc_now_ns`、`utc_ms_at`、`unique_id`（無參數或指定奈秒）與 `identity`，供行程辨識、送訊號及產生時間與名稱。

## 建置與測試

```sh
cmake -B build && cmake --build build
```

- 別的專案怎麼連、vcpkg、產物：見 [impls/README.md「建置」](../docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md#建置)。

## 已知限制

- 只支援 Linux（`/proc`、`killpg`、`sigtimedwait`）。
