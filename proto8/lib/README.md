# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

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

## inst（`aos_inst.py`）

讀一份 JSON → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次。

```
python3 proto8/lib/aos_inst.py TARGET
```

- TARGET：`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`）。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。
- `cwd` 沒寫＝呼叫 aos_inst 時的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`、`timeout_grace_ms`（要收掉子程式時 SIGTERM 之後等多久才 SIGKILL；預設 2000、0＝直接 SIGKILL）、`kill_leftover`（子程式結束後整群 SIGKILL 清掉孫程式，預設 true），加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- 最多跑多久不放 JSON：Python 用 `run(inst)`（不限時）或 `run_with_timeout(inst, timeout_ms)`；命令列一律不限時。
- 子程式自成一個行程群組（新 session，脫離終端機）；逾時、或 aos_inst 被 Ctrl-C／SIGTERM／SIGHUP 打斷，都整群 SIGTERM → 等 grace → 整群 SIGKILL。
- 兩條路分工：**子程式的結束碼只寫進 `exit` 檔**（十進位＋換行、fsync；自己結束＝它的碼，被訊號停掉＝128＋訊號號碼，沒起來不寫）；**命令列退出碼只說 aos_inst 自己**：0＝子程式跑完了、1＝aos_inst 自己出錯（子程式沒跑）或被訊號打斷（stderr 一行「代號: 白話」）。exit 寫不進去不管。
- API：`load(target)`、`parse(doc, base_dir)`、`run(inst)`、`run_with_timeout(inst, timeout_ms)`（都不回東西，出錯丟 `InstError`）。

