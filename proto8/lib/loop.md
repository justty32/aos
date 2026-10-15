# loop（`aos_loop.py`）

← [proto8/lib](README.md)｜上一份：[inst](inst.md)｜下一份：[daemon](daemon.md)

包一個 inst：跑幾次、隔多久，一邊讀 ctl 窗、寫 state 窗。照 NORMS N-12 重做（10-14）。

```
python3 proto8/lib/aos_loop.py [--key 值 ...] [LOOP.json | -]
```

```jsonc
{
  "inst": {"$ref": "job/inst.json"},   // 一份 inst 格式（內嵌或 $ref），必填
  "ctl": "job-ctl.json",               // 必填（N-19）
  "state": "job-state.json",           // 必填（N-19）
  "times": null,                       // 總數；null＝不限；沒寫＝1
  "interval_ms": 5000,                 // 沒寫＝0
  "interval_mode": "after",            // after＝跑完再隔；fixed＝固定週期，跑超過就跳拍（state 的 skipped）
  "grace_ms": 5000,                    // 收掉這次時整群 SIGTERM 之後等多久整群 SIGKILL
  "ctl_poll_ms": 1000,
  "error_wait_ms": 1000,               // aos_inst 自己出錯之後至少隔多久
  "stop_on_end": false,                // true＝包的 fsm 走到 end（那行帶 "end": true）就結束（N-44）
  "id": null                           // 選填；state 的 id（沒寫＝LOOP.json 的 realpath#/位置；stdin 來＝null）
}
```

- 設定從哪來照 `aos_cli`：LOOP.json（可接 `#/位置`，見[指示詞](directives.md)）、`-`＝stdin；外層純量 key 有同名旗標（`--times 3`、`--ctl c.json`），蓋過檔或 stdin；`inst` 不鏡射；`--` 不收。`run(x)` 收路徑或一份設定 dict。
- **窗必填**（N-19）：`ctl`、`state` 缺 key 或 null＝`WindowMissing`、退出碼 1、不執行。ctl 窗起來時不在沒關係。
- 設定（含 `inst` 那格與裡面的指示詞）**只在起來時讀一次、解一次**；`inst` 不對＝起不來（stderr 一份錯誤、代號照 aos_inst 的、退 1；寫了 `stdin_inherit` 也是，因為 inst 從 stdin 灌，D-5）。跑的途中要改只能走 ctl 窗。
- 每一次：起子程序 `aos_inst.py -`（自成一個 session），把解好的 inst 從 stdin 灌進去 → 等它結束 → 整群補 SIGKILL 清孫程式 → 收屍。不再寫暫存 inst.json。
- 結果：aos_inst 回 0 → `last_code`＝它 stdout 那份結果的 `code`（不必寫 exit 檔）；非 0 → `last_error`＝它 stderr 最後一份錯誤，寫成「代號: 白話」。aos_inst 的 stderr **不轉**到 loop 的 stderr，只記在 state 窗（C-52；10-15 使用者「都按照推薦。」，盤點 S2）。
- **stdout**（JSON 串流）：每一次一份 `{"run", "code", "ms"}`（只在真的跑了 inst 時吐；loop 一定有 inst，daemon 沒 inst 就不吐），結束時一份 `{"end": "done"|"stopped", "runs", "skipped", "last_code", "signal"}`。stderr：只有 loop 自己的錯誤（N-29），正常結束不寫（N-43）。
- **ctl 窗**（宣告式，NORMS N-06～）：`paused`、`stop`（`true` 或 `{"val": true, "now": true}`；now＝當場收掉正在跑的）、`times`、`interval_ms`、`interval_mode`、`seq`（流水號）。沒寫的欄位＝loop.json 的初始值（只在 `want()` 一處）。stop 是終點。壞檔、型別錯、不見了＝維持上一次，原因記在 state 窗的 `last_warning`（不寫 stderr；讀到好的就清掉，N-08）。每次讀整份、內容跟上次不同才重驗。
- 次數跑完（runs ≥ times）就結束、退出，有 ctl 也一樣；想再跑就重新起。
- **`stop_on_end`**（N-44）：這次 stdout 裡有 fsm 結束那行（`{"from", "to", "end": true}`）＝不再起新的一次、`end`＝`"done"`。inst 寫了 stdout 檔（附加也行）就讀這次寫進去的那段；沒寫或 inherit＝loop 每次替它接暫存檔、讀完刪。只認帶 `from`、`to` 的那行，格自己的結果帶 `end` 不算。agent 定義資料夾的 loop.json 都寫它（不靠 done 格寫 ctl stop）。
- **state 窗**：共同骨架（見 [ctl-state](ctl_state.md)，含 `ctl_seq` 與心跳欄位）加上 `skipped`、`last_code`、`last_warning`。暫存再改名；內容沒變也每秒碰一次。寫不了＝`StateWriteFailed`：收掉正在跑的、結束、退 1。
- 退出碼只說 loop 自己、**不沿用下層的碼**（C-52；10-15 使用者「都同意。」，[盤點第 1 條](../thinking/2026-10-15-principles.md)）：0＝正常結束（子程式回非 0 不算）；1＝設定不對、state 窗寫不了、或最後一次是 aos_inst 自己出錯（stderr 一份錯誤，代號＝`last_error` 的代號；中途錯、後來好了不算）；被訊號停掉＝1（不寫 stderr；哪個訊號記在 state 窗與結束那份的 `signal`；原 128＋N，10-15 晚使用者「按照推薦」收掉）。`run()` 正常回 None，否則丟 `LoopError`（`exit` 屬性＝退出碼）。
- 給 daemon 重用的：拍引擎 `Loop`（掛鉤 `beat()`、`idle()`、`extra()`、`finish_up()`）、`check_config()`／`load_config()`；ctl 那組（`parse_ctl()`、`want()`、`CtlFile`）、state 那組（`STATES`、`state_doc()`、`read_state()`、`StateFile`）、`require()`、`write_json()` 在 `aos_ctl_state.py`；`kill()`／`reap()` 在 `aos_proc.py`。後兩檔的名字 `aos_loop` 都 re-export。
