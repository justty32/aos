# 2026-11-09 procs_state.json 讀不了要說話、壞檔留證（format-versioning 必修 1 施工結果）

← [2026-11-09](../README.md)｜出處：[format-versioning](../format-versioning/README.md)（必修 1、01 #8、03 S3、04 D5）

## 使用者原話（11-09，經頂層轉述）

> 先修必修

## 結論

- 以前：daemon 開門讀 `procs_state.json`，壞 JSON、不是物件、缺 `procs`、分檔解不開、有一列壞——一律當沒有，接著寫新表蓋掉，上一班睡著／stopped 的列默默失聯。
- 現在（`aos-daemon/src/daemon/adopt.cpp`）：
  - **檔不在**＝第一次起來，照舊安靜。
  - **整份壞**＝主檔改名成 `procs_state.json.bad-<UTC 毫秒時間>`（冒號換連字號、不蓋舊的 bad 檔、撞名加尾碼），stderr 印 `aos-daemon: warning: procs_state.json is unreadable (<原因>); kept it as <檔名> and started with an empty table`，daemon.json 定義的列照起。
  - **幾列壞**＝複製主檔留證、每個壞列印一行 warning、好列照接回。
  - 同樣的原因進 log（開了 `--enable-logs`）與 `state_flux.json` 新欄 `adopt_warning`（沒事＝null，這次活著期間不變）；有警告的那一班不清舊分檔（留證的主檔可能還指著它們）。
- 條文：N-28 `adopt` 加 11-09 註（不是 C-48 的「當沒看到」：程式自己寫的狀態檔讀不了要看得出壞了）、N-28 state_flux 欄位加 `adopt_warning`、N-05 加註；aos-daemon README 與 docs/04。

## 代定（隊長，可翻）

1. 採審查 03 S3 的推薦「警告＋留證＋照定義重建表」，**不拒起**：拒起會讓根 daemon 起不來、整棵樹停擺，而留證已經「看得出壞了」。
2. 壞列只跳過那一列、好列照接（不再「一列壞整份不接」）。
3. 改名或複製失敗（例：資料夾唯讀）＝`WriteFailed` 起不來（大聲）。

## 判準實測（WSL）

- test_lifecycle 加 4 組（壞 JSON、陣列、壞一列、正常路徑沒有警告），連跑兩次全過；test_ctl、test_poke 全過。測試輔助 `support.py` 等 daemon 起來時改成容許表暫時不是物件（壞表測試開門前檔是 `[]`）。
- 試驗場複本（`/tmp/pgcdc-*`，三層、已起過一輪）手測三案：各有一行 warning、`.bad-*` 各留一份（累計 3 份）、`adopt_warning` 同字；壞一列那案點名 `switchboard`，其他列照接；三案 daemon.json 的三列都照起、沒有默默失聯。
