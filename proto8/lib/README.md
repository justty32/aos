# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫，沒有命令列。測試在 [../tests/](../tests/)，跑法：`python3 -B proto8/tests/run.py`（哪裡跑都行）。

## 指示詞 lib（`aos_directives.py`）

讓 JSON 裡某一格的值「從別處來」。一個檔、一個入口：

```python
from aos_directives import resolve, DirectiveError
out = resolve(doc, base_dir)   # doc＝parse 好的 JSON；base_dir＝相對檔名的基準路徑
```

整份 JSON 一層層全部解掉，回一份新的（原本那份不動）。`base_dir` 整趟都用它，進了別的檔也不換。

兩種指示詞（兩個都寫了只看 `$ref`，其餘 key 忽略）：

```jsonc
{"$ref": "other.json#/a/0"}          // 讀一份 JSON 的某一格；"" 是目前這份；位置也可寫成 "$at": "/a/0"
{"$ref": "#../x"}                    // ./ ../ 從這個指示詞所在的位置算
{"$env": "HOME"}                     // 讀環境變數
```

取回來的東西裡如果還有指示詞，照它所在的那份檔、那個位置接著解。繞回自己（指到正在解的位置或它的上層）＝`ReferenceCycle`。
錯了一律丟 `DirectiveError`，代號七種，寫在檔頭。

**沿革**：2026-10-12 從 proto7-2 拿來，同日照使用者要求精簡：刪 `$opt`／`$val`、`$fmt`；入口從「解一格 `resolve(value, ctx, position)`」改成「解整份 `resolve(doc, base_dir)`」；三檔併一檔（233＋111＋73 行 → 161 行）。原本的完整規則在 [proto5/spec/directives/](../../proto5/spec/directives/README.md)，`$ref`／`$at`／`$env` 那幾節仍適用；選項、`$fmt` 兩節不再適用。測試：[test_directives.py](../tests/test_directives.py) 38 條。

## inst（`aos_inst.py`）

讀一份 JSON → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次。

```
python3 proto8/lib/aos_inst.py TARGET
```

- TARGET：`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`）。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。
- `cwd` 沒寫＝呼叫 aos_inst 時的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算（使用者 10-12 改）。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`、`timeout_ms`（時間到 SIGTERM，2 秒後 SIGKILL），加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- 兩條路分工（使用者 10-12 定）：**子程式的結束碼只寫進 `exit` 檔**（十進位＋換行、fsync；訊號＝128+N；沒起來就不寫）；**命令列退出碼只說 aos_inst 自己**：0＝子程式跑完了、1＝aos_inst 自己出錯、子程式沒跑（stderr 一行「代號: 白話」）。exit 寫不進去不管。
- API：`load(target)`、`parse(doc, base_dir)`、`run(inst)`。

**沿革**：2026-10-12 照使用者決定重寫，不是搬：原本的 `$opt` 選項改成平的布林 key；基準一律是呼叫者的 cwd（同日先做了 `--base inst|cwd`，使用者說拿掉），串流跟著 `cwd`，`cwd` 沒寫就繼承呼叫者的；跑法先最小（直接起、等它結束），process group 等還沒做；`exit`、`timeout_ms` 同日補上。測試：[test_inst.py](../tests/test_inst.py)。
