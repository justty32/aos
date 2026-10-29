← [入口](../proto8.md)｜涵蓋：`proto8/impls/aos-daemon/src/`｜同層：[01-impls與舊lib](01-impls與舊lib.md)（其他 impls）

> 2026-10-29 從 [01-impls與舊lib](01-impls與舊lib.md) 逐字下放（那份超過 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md)），同時加 10-29 拆窗的 `windows.cpp`。逐專案說明在 [aos-daemon](../../../../../proto8/impls/aos-daemon/README.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `aos-daemon/src/daemon/daemon.cpp` | `Daemon`：`read_loops`（10-24：子項 exec 是單子＝只換一層、`abs_refs` 把相對 `$ref` 轉絕對；10-23 晚取代 `check_loops`〔統合前叫 `check_children`〕：`loops` 的每層指示詞（拆檔＝`$ref` 陣列，子項的起點用 `dir_of`）、名字規則；10-23 原本的分頁陣列與 `merge_rows` 同日拿掉）、建構子（10-29：`loops_ctl`／`loops_state` 的路徑，沒寫＝預設檔名、`null`＝不開）、`check_ctl`（10-29：ctl.json 的 `loops*` 不採用，過渡期 `ctl_note_` 提醒搬家）、10-22 起 `taken_names`／`check_names`（子項名字跟自己的窗撞名：起來時 CfgBad〔10-23 統合前叫 Conflict〕、loops_ctl 撞＝不採用）、`adopt`（10-29 起讀 loops_state）、`tend`（期望表＝loops_ctl 的 `loops`＋`loops_added`－`loops_removed`；10-29：ctl stopped／paused 那圈不調表）、`term`／`settle`（10-23：收子項不等，SIGTERM 後每次看一眼、滿 10 秒 SIGKILL；10-24 審後連子 loop 底下自成一群的單子〔`leaders_below`〕；表＝串列＋名字的雜湊表）、`finish`（等子項退時每秒寫 state） |
| `aos-daemon/src/daemon/windows.cpp` | 10-29 拆窗（[medium-plan § 四](../../../../../proto8/thinking/2026-10-29-medium-plan.md)）：`read_loops_ctl`（每圈讀 loops_ctl.json，同 read_ctl 的不採用規則，原因進 loops_state 的 `ctl_warning`）、`check_lists`（原 ctl 的 `loops`／`loops_added`／`loops_removed`）、`write_more`（loops_state.json：`kind`、`ctl_seq`、`ctl_warning`、`loops`、心跳）、`write_parts`（10-23 晚：`loops` 超過 100 列切成 `{"$ref": ["loops_state_loops/<雜湊>.json", …]}`〔10-29 前叫 `state_loops/`〕、清舊分檔） |
| `aos-daemon/src/child/child.cpp` | 子 loop 經 aos-exec 起：寫小格 `loop.json`（補 ctl／state、蓋 `_entry`、相對 exec 轉絕對；10-24 起 exec 是單子＝補／接 `cwd`）、fork 後呼叫 `run_cli({"--", 小格/loop.json#/_entry})`，exec 成 PATH 上的 aos-loop |
