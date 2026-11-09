# proto8 討論紀錄：2026-11-09

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [clock-and-hot-writes](clock-and-hot-writes/README.md) | 使用者兩個想法：`_tick` 改名（裁大改；名字待在 clock／turn 二選一，推薦 clock＋單位 cycle）、熱寫檔拉出 json 改 .txt＋旗標（實測閒置每秒約 25 次整份重寫，元兇是 `responded_at` 與表的 `tick` 欄，不是 runs；5 題待裁）；只盤點未改 |
| [daemon-interrupt](daemon-interrupt/README.md) | 使用者想給 daemon 真正的中斷（訊號／socket／plan9 三條路）：現況閒著最慢 1 秒、跑身體整段叫不動；規劃成「門鈴」（指令仍寫檔）；使用者 11-09 裁：先做訊號、只做一個指令 `aos-daemon-ctl poke [--ctl|--mail|--all]`（預設 `--ctl`）、順手擋 SIGUSR1／2；N-17 加「其他人不碰 pid」的 poke 例外；施工結果見 05 |
| [clock-decouple](clock-decouple/README.md) | 使用者「_clock 與 daemon 耦合很深……別那麼深」：耦合點全表（最重五個：`clock` key 自動展開、寫死 `aos-clock`、daemon setenv `AOS_CLOCK`、判卡住讀鐘、鐘看鐘）、四方案（推薦 B：拿掉 key、範本寫普通鐘列＋`.env` 給 `AOS_CLOCK`）；方向題 3 題待裁，只規劃未改 |
| [format-versioning](format-versioning/README.md) | 使用者問 json／佈局改了有沒有相容或升級機制（重心：正式版之後）：現況全無版本標記，問題是 C-48 舊 key 忽略讓壞看不出來（實測 state_flux 拆分前的 stack 開門即下表、`tick`／`timeout_ticks` 默默失效、procs_state 壞默默蓋空表）；選項 A→B→C、現在可埋的種子 S1～S5（不跟 11-05 衝突）；4 題待裁，只審未改 |
