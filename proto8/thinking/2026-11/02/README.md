# proto8 討論紀錄：2026-11-02

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-11-02 試驗場：bob 串 aos-mcp／aos-tools、資料夾工具 cathy](playground-cathy/README.md) | 使用者 CPU 類比原文（`AOS_CF`／`CD`／`CO`＝執行到哪個指令、`STACK`／`WS`＝最重要的兩個暫存器）；`agents/bob-cathy` 經 aos-mcp／aos-tools 叫跟 bob 並排的 agent `agents/cathy`，haiku 實跑過；代定可翻案 |
| [2026-11-02 小格改放 `.stack/tools/<名>/`](stack-tools/README.md) | 選 B：變動名與固定名分開，工具小格→`.stack/tools/<名>/`、daemon 子項→`loops/<名>/`；已實作（擋名字拿掉），ask_round 對齊 P-32 先不管 |
| [2026-11-02 試驗場：daemon 掛 loop 與 bob](playground-daemon.md) | daemon 能直接掛 aos-exec（`execs`），`agents/bob` 不改，給題＝`aos-daemon-ctl add ../agents/bob -- "題"`；用的時候：stdout 被丟、做完不留名單可同名再 add、用 ctl 停完 `daemon_ctl.json` 會殘留、重起不接回做完的 bob；代定 9 條；一直開著等題的掛法見常駐 bob |
| [2026-11-02 daemon 的環境變數（AOS_DAEMON 指 stack 不對）](daemon-env/README.md) | 變數改叫 `AOS_DAEMON_STACK`（值＝daemon 的 stack）、舊名 `AOS_DAEMON` 退場、旗標 `--daemon-stack`；現階段不切控制口（daemon.json 可用 `$env` 明寫切）；daemon 起子項時給 `AOS_DAEMON_STACK`（11-04 再簡化回 `AOS_DAEMON`，見 [aos-agent](../04/aos-agent/README.md)） |
| [2026-11-02 aos-exec 一環套一環＝像繼承](exec-inheritance.md) | 往下「變成」另一套＝共用 stack（像繼承）、「叫」＝給小格；共用 stack 不做隱性命名空間，常見名字加自己的前綴或開資料夾（控制自身的 ctl／state 例外）；呼叫沒有 base／derived 之分 |
| [2026-11-02 state 窗改成有變動才寫](state-window/README.md) | daemon 的窗啟動寫一次、有變動才更新、加 `updated_at`，心跳拿掉（判活看 pid＋aos-daemon-ctl）、log 預設不印；晚上陸續裁的（`add XXX -- 參數`、子項結束不留名單、`mailbox_warning` 等）；已實作 |
| [2026-11-02 loop／daemon 的 stdin／stdout 與 log](loop-stdio.md) | log 預設不印、stdout 混在一起使用者自理、`execs` 也收內嵌單子；身體與子 loop 寫成內嵌單子就能用 `stdin`／`stdout` key |
| [2026-11-02 晚 loop 這一系的窗檔名：控制自身的 ctl／state 就叫 `ctl.json`／`state.json`](ctl-state-names/README.md) | 控制自身的 ctl／state 就叫 `ctl.json`／`state.json`、不加前綴，白天的 `daemon_*`／`loop_*` 窗名推翻；已實作；方向題：1 由 11-03 procs 解決、2 前綴原則對其他固定名照舊、3 只有帶 ctl 的才算一對 |
