← [入口](../proto8.md)｜涵蓋：`proto8/impls/aos-json`（讀、改 aos 的 JSON 設定，10-24）

> 2026-10-24 收尾補（commit 8cd0f70d 做的時候沒改 code map）。逐專案說明在 [aos-json](../../../../../proto8/impls/aos-json/README.md)；設計紀錄 [thinking 2026-10-24-aos-json](../../../../../proto8/thinking/2026-10-24-aos-json.md)。
> 一個 lib（`lib/libaos-json.a`，**沒有公開標頭**、沒有 `include/`，元素的標頭從 `src/` 互相 include）加一支命令列 `bin/aos-json`，再加兩個給腦掛的工具 `tools/json/`、`tools/json_edit/`。

| 哪裡 | 負責什麼 |
|---|---|
| `src/main.cpp` | 命令列 `aos-json 子命令 [旗標...] 檔#/指標 [...]`：第一個參數查表挑子命令（`get`、`peek`、`where`、`set`、`batch`、`del`、`append`、`merge`、`env`、`ref`、`check`）；錯一行 `aos-json: 代號 原因`、退 1（同 aos-exec，N-60） |
| `src/common/common.hpp` | 自己的錯誤代號（`FileMissing`、`FileBad`、`SpecBad`、`PointerMissing`、`ValueMissing`、`ValueBad`、`TargetBad`、`CheckFailed`、`FollowMissing`；check 報的 `DirectiveFormBad`、`ExecBad`）；全家共用的（含 10-30 收過去的 `CommandUnknown`）從 aos-util、`DirectiveBad` 從 aos-directive |
| `src/doc/doc.hpp` | 【doc】`File`（原文、`#!` 行、縮排、結尾換行、權限）、`Docs`（讀過的檔都留著、改完一起寫）、`Spec`、指標 |
| `src/doc/file.cpp` | `load_file`（記 `#!`、猜縮排、權限）、`render_body`、`save_file`（同資料夾 `.名字.<pid>.tmp` → fsync → rename，N-05；值沒變不寫；捷徑寫到它指的檔） |
| `src/doc/splice.cpp` | 寫回時只重寫有變的那一塊（自己掃 JSON 找起訖、一行的寫一行、跨行的照檔的縮排），其他原文不動；做不到才整份重排 |
| `src/doc/pointer.cpp` | `parse_spec`（`檔#/指標` 拆開，N-62）、RFC 6901 指標的拆接、往下一格 `child`、印給人看的位置 `shown` |
| `src/follow/follow.hpp` | 【follow】`Kind`（Plain／Ref／Env／FormBad）、`Cursor`、`Mode`、`Located` |
| `src/follow/kind.cpp` | 認指示詞（寬容規則同 aos-directive：寫法不合＝`FormBad`、原封不動）、拆 `$ref` 的每一份 |
| `src/follow/locate.cpp` | `locate`：從 `檔#/指標` 往下走、記走過的每一站；`--follow` 時穿 `$ref`（`fetch`、`settle`、`$ref` 陣列挑「最後一份有這個 key 的」）。**跟 aos-directive 的規則要一起改** |
| `src/cmd/cmd.hpp` | 【cmd】每個子命令一個函數；`problems_of`（check 的本體，`--check` 也用） |
| `src/cmd/read.cpp` | `get`（`--follow`、`--resolve` 交給 aos-directive 解、`--str`）、`where`（一站一行，最後一站＝值實際寫的地方） |
| `src/cmd/peek.cpp` | `peek`：漸進展開，第一行位置＋形狀、每個孩子一行摘要（字串截 80 位元組、物件 `{N}`、陣列 `[N]`）；`--follow`、`--depth N` |
| `src/cmd/write.cpp` | `set`、`batch`（全部成功才寫）、`del`、`append`、`merge`、`env`、`ref`（`--move` 先寫新檔再改原檔）；共用 `Edit`：找位置 → 改 → `--check` 比原本多出問題才擋 → 有變的檔才寫 |
| `src/cmd/check.cpp` | `check`：`$ref` 指得到（一路驗進被參照的檔、繞圈、陣列合得起來）、指示詞寫法、`exec` 形狀（最上層、`states/<名>/exec`、`loops/<名>/exec`）；問題一行一個印 stdout、退 1 |
| `tools/json/` | 腦用（P-41）：`_tooldef.json`＋`_entry`（python3）——`{"cmd", "target", "value"?, "depth"?}` 一次一個動作，寫一律帶 `--check --follow`；aos-json 的錯印 stdout `錯：…`、退 0 |
| `tools/json_edit/` | 腦用、自己問腦（`AOS_BRAIN_URL`）：「小念頭」兩步——peek 一層層找出指標（最多 `AOS_JSON_EDIT_MAX_ROUNDS` 輪）→ 每個指標各問一次新值 → `aos-json batch --check --follow` 一次寫 |
| `tests/test_cli.py` | ctest `test_cli`：命令列黑箱 126 個 |
| `tests/test_tool.py` | ctest `test_tool`：兩個工具經 `aos-exec` 跑、假 OpenAI 端點，30 個；`../aos-exec/bin/aos-exec` 沒建＝跳過 |
| `CMakeLists.txt`、`vcpkg.json`、`.gitignore` | 照 aos-directive 改名；靜態庫＋`-static-pie` 執行檔；nlohmann-json；`bin/`、`lib/`、`build/` 不進 git |

依賴：aos-json → aos-directive、aos-util（`add_subdirectory` 一起編）；`test_tool` 另外要 aos-exec 的 `bin/` 先建好。共用建置順序與 for 迴圈見 [impls/README「建置」](../../../../../proto8/impls/README.md#建置)、[testing](../../../testing.md)。

誰叫它：`proto8/lib/base/json_edit`（10-24 遷移，原 demo/file-tools/json_edit；PATH 上要有 aos-json）、`proto8/extras/ai_tools`（`aos-ai` 自己把 `impls/aos-json/bin` 放進 PATH；`make` 有它就用 `check`／`set`）。`proto8/tests/aos_bins.py` 10-24 遷移起把它放進 PATH（沒建就停、說要先建）；`demo/run.sh` 不放它（run.sh 跑的 agent 沒掛 json_edit）。
