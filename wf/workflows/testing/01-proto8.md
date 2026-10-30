← [入口](../testing.md)｜涵蓋：proto8（不在 ctest 裡）｜下一份 [02-測試分類與綠燈](02-測試分類與綠燈.md)

## proto8（不在 ctest 裡）

10-23 起 proto8 的 aos-exec、aos-loop、aos-fsm、aos-daemon 只剩 C++ 版（`proto8/impls/<名>/bin/`；使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python），aos-tick 還是 `proto8/bin/` 的 Python。`proto8/tests` 與 `proto8/demo/run.sh` 都把這幾個 `bin/` 放進 PATH 跑（`proto8/tests/aos_bins.py`；沒建好會直接停、說要先建），所以**先建 impls**（各專案獨立的 CMake 專案，照依賴順序；`bin/`、`build/` 不進 git）：

```sh
(cd proto8/impls && for p in inst aos-util aos-directive aos-schema aos-exec aos-json aos-loop aos-fsm aos-lock aos-post aos-daemon aos-kernel-llm aos-gate; do (cd $p && cmake -B build && cmake --build build && ctest --test-dir build) || break; done)
python3 -m unittest discover -s proto8/tests      # 全過（python-dotenv 沒裝時 1 個 skip）
sh proto8/demo/run.sh                            # 結束碼 0、各段都「結束碼 0」（10-23 加 agent-dan 後五段；10-24 加 kernel-llm 後六段）
```

impls 各專案自己的 ctest（`test_cli`、`test_demo`…）說明在 [proto8/impls/README.md](../../../proto8/impls/README.md)。

10-23 起 `proto8/tests/test_dan.py`（agent-dan）裡連真模型的案例，在 `localhost:4000/v1/models` 連不上時 skip（其餘用假 server，離線也跑）。

10-28 Windows 機的 WSL（`networkingMode=mirrored`）：連 `127.0.0.1` 低號的空埠（原本測試拿 `http://127.0.0.1:9/v1` 當腦壞了）會**等到逾時**而不是馬上被拒，test_dan、test_human、test_ai_tools、test_talk、test_grow、test_topdown_galtxt_a 那 7 案因此逾時失敗——是環境，不是程式壞。**已解（10-28）**：改從 `proto8/tests/dead_brain.py` 拿 `DEAD`（本行程 bind 一個埠、不 listen、一直拿著，連上去一定馬上被拒）；WSL 上 `python3 -m unittest discover -s proto8/tests` 全過（657 案、31 skip），`sh proto8/demo/run.sh` 結束碼 0。

同一天 impls 的 aos-loop、aos-fsm、aos-daemon 自己的 `test_cli` 各一案多一行「Terminated」：那是測試裡的 `sh -c` 小程式自己印的（內嵌單子收的是整群的 SIGTERM，`sleep` 也被殺，dash／bash 看時序會在自己的 stderr 報一行），不是被測程式；**已解（10-28）**：那幾支小程式開頭加 `exec 2>/dev/null`，斷言照舊看被測程式自己的 stderr 是空的。WSL 上 11 個 impls 的 ctest 全過。

10-29 skip 從 31 變 11：這台 WSL 13:35 裝了 bubblewrap（`/var/log/dpkg.log`），`test_sandbox` 用 bwrap 的 20 案從跳過變成真跑，不是測試條件改了。**這台 WSL 還缺 s6**（`s6-softlimit`、`s6-setuidgid`；PATH 或 `~/code/try/sandbox/s6-root/bin` 有就跑）與 `unshare --map-auto` 的假 root，所以 `test_sandbox` 還跳 4 案（上限、身分、bash-boxed、信箱權限）；裝了就能跑。其餘的 skip 是 LiteLLM／`localhost:4000` 連不上、沒設 `AOS_REAL_MODEL`、沒裝 python-dotenv。
