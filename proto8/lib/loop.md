# loop（`aos_loop.py`）

← [proto8/lib](README.md)｜上一份：[inst](inst.md)｜下一份：[daemon](daemon.md)

包一個 inst：跑幾次、隔多久，一邊讀一個 ctl.json。

```
python3 proto8/lib/aos_loop.py LOOP.json
```

```jsonc
{
  "inst": {"$ref": "job/inst.json"},   // 一份 inst 格式（內嵌或 $ref）
  "times": null,                       // 總數；null＝不限；沒寫＝1
  "interval_ms": 5000,                 // 沒寫＝0
  "interval_mode": "after",            // after＝跑完再隔；fixed＝固定週期，跑超過就跳拍（state 的 skipped）
  "grace_ms": 5000,                    // 收掉這次時整群 SIGTERM 之後等多久整群 SIGKILL
  "ctl": "job-ctl.json", "ctl_poll_ms": 1000,
  "state": "job-state.json",
  "error_wait_ms": 1000                // aos_inst 自己出錯之後至少隔多久
}
```

- `LOOP.json` 可接 `#/位置`（見[指示詞](directives.md)）：loop 本體是那一格，id（state 的 `id`）＝realpath#/位置。
- loop.json（含 `inst` 那格與裡面的指示詞）**只在起來時讀一次、解一次**；`inst` 不對＝起不來（沿用 aos_inst 的碼，參考 125）。跑的途中要改只能走 ctl.json。
- 每一次：起子程序 `aos_inst.py`（自成一個 session）→ 等它結束 → 整群補 SIGKILL 清孫程式 → 收屍。解好的 inst 在起來時寫成暫存資料夾裡的一份 inst.json，每次都把它的路徑交給 aos_inst，結束刪掉。
- 結果：aos_inst 回 0 → `last_code`＝exit 檔最後一行（沒寫 exit＝null）；非 0 → `last_error`＝它 stderr 的最後一行。
- **ctl.json**（宣告式，NORMS N-06～）：`paused`、`stop`（`true` 或 `{"val": true, "now": true}`；now＝當場收掉正在跑的）、`times`、`interval_ms`、`interval_mode`。沒寫的欄位＝loop.json 的初始值（只在 `want()` 一處）。stop 是終點。壞檔、型別錯、不見了＝維持上一次、印一次。每次讀整份、內容跟上次不同才重驗（不靠 inode／mtime：ext4 上 4 ms 內的等長改動會撞）。
- 次數跑完（runs ≥ times）就結束、退出，有 ctl 也一樣；想再跑就重新起。
- **state.json**（選填）：共同骨架（見 [ctl-state](ctl-state.md)）加上 `skipped`、`last_code`；`last_error`＝aos_inst 自己出錯時它 stderr 的最後一行。暫存再改名。
- 退出碼只說 loop 自己：0＝正常結束（子程式回非 0 不算）；最後一次是 aos_inst 自己出錯＝沿用它的碼；被訊號停掉＝128＋N；loop.json 不對＝125。`run(path)` 正常回 None，否則丟 `LoopError`（`exit` 屬性＝退出碼）。
- 給 daemon 共用的：`load_config()`（在 `aos_loop.py`）；ctl 那組（`parse_ctl()`、`want()`、`CtlFile`）、state 那組（`STATES`、`state_doc()`、`read_state()`、`StateFile`：欄位、狀態值、讀、寫只在這裡）、`write_json()` 在 `aos_ctl_state.py`；`kill()`／`reap()` 在 `aos_proc.py`。後兩檔的名字 `aos_loop` 都 re-export，`from aos_loop import ...` 照用。
