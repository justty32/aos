# proto6/src/py

← [proto6 plan](../../plan/README.md)

inst 與 `aos-exec` 直接從 proto5 **原樣複製**（proto5 `470f5a04`，即 `git log -1 --format=%h -- proto5/lib proto5/cli`），不重寫。說明文件看 proto5 的 [lib/docs/exec.md](../../../proto5/lib/docs/exec.md)、[directives.md](../../../proto5/lib/docs/directives.md)。

| 這裡 | 來源 | 內容改了什麼 |
|---|---|---|
| `bin/aos-exec` | `proto5/cli/aos-exec` | 沒改（它本來就找 `../lib`） |
| `lib/aos_exec.py`、`aos_exec_run.py`、`aos_exec_spawn.py`、`aos_directives.py` | `proto5/lib/` 同名檔 | 沒改 |
| `lib/aos_inst.py` | `proto5/lib/aos_inst.py` | 唯一改動，見下 |
| `tests/test_exec.py`、`test_exec_full.py`、`test_exec_spawn.py`、`test_inst.py`、`test_directives.py` | `proto5/lib/test/` 同名檔 | 沒改 |
| `tests/_util.py` | `proto5/lib/test/_util.py` | 只改 `LIB`、`EXEC` 兩行路徑 |
| `tests/test_user.py` | 新寫 | 測下面那個改動 |

## 唯一改動：認得頂層 `user`

proto6 inst 第 1 版多了頂層 `user`（[inst.md](../../spec/base/inst.md)）。`aos_inst._check_user()` 在解任何指示詞之前看原始頂層的 `user` 字面值：

- 沒寫或空字串：照跑。
- 名稱或 UID 解析後跟目前行程的 euid 相同：照跑。**不切換身分。**
- 不同：`UserNotGranted`；型別錯、放指示詞、負數、查不到帳號：`UserInvalid`。都是 125、不跑、不寫 `exit`，stderr 一行「aos-exec: 代號: 白話」。

整份 `$ref` 引進來的 `user` 不看（照 proto5 忽略）。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
