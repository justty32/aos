← [入口](../proto8.md)｜涵蓋：`proto8/impls/`（使用者的 C／C++ 實作）、舊 lib（10-16 那套，已刪）

> 2026-10-21 下午從 [proto8.md](../proto8.md) 逐字下放（那份超過 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md)）。

### `proto8/impls/`（使用者的 C／C++ 實作，git 未追蹤）

總入口與逐專案說明在 `proto8/impls/README.md`（未追蹤，只在家中 Manjaro）。10-21 對齊 bin 版 10-20：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（`inst` C lib、`aos-util`、`aos-directive`、`aos-schema` 是庫）；
aos-loop 的骨架是公開的 `aos::loop::Loop`（`src/engine/`），aos-daemon 繼承它、子 loop 是 fork 後在子行程裡跑同一個 Loop；指示詞（`$ref` 的 `#/`／`at`、`$path`、`$prefix`、寫法寬容）在 aos-directive，
argv 陣列入口的指示詞與「argv[0] 帶 `/` 又 exec 不了交給 aos-exec」在 aos-exec（`launch.cpp`、`run_inst`）。動工前的樣子備份在 `proto8/impls/backup/aos-impls-2026-10-21-pre-align.tar.gz`。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show aa2fec1f:proto8/lib/README.md`（逐檔表）。daemon 10-20 已照新做法重寫（上面 `aos-daemon`）；kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../../proto8/NORMS/08-待定.md)）。
