# fsm（`aos_fsm.py`＋方法表 `aos_methods.py`）

← [proto8/lib](README.md)｜規範：[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子.md#fsm)（N-20、N-36～N-41）｜demo：[demo/fsm](../demo/fsm/README.md)｜決定：[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md)

一拍跑一格的狀態機：**現在是 A 狀態，就跑 A 那格的 inst**；狀態內部、inst 內部的事 fsm 都不管（C-49）。壽命一拍，要一直跑就讓 loop 拍它。基礎實作（N-18；10-15 收工後瘦身）。

```
python3 proto8/lib/aos_fsm.py [--key 值 ...] [FSM.json | -]
```

```jsonc
{
  "start": "idle",                          // 必填，要在 states 裡
  "states": {                               // 必填：狀態名 → 格
    "idle": "idle.json",                    //   aos-inst TARGET（檔、資料夾、可接 #/位置）；相對路徑從本檔所在的資料夾算
    "thinking": "think/",                   //   資料夾＝aos-inst 的找法；裡面可以是另一個 aos_fsm（巢狀）
    "tool": {"argv": ["python3", "tool.py"], "stdin": "cfg.json"},   //   內嵌一張 inst；格要參數就寫自己的 stdin
    "done": {"target": "done.json", "next": "idle"}                  //   帶表上靜態 next
  },
  "end": ["done", "out"],                   // 選填：名字可以在表裡（跑完那格就結束）也可以不在（回這個 next 就結束）
  "state": "fsm-state.json"                 // 必填（N-19）；從 cwd 算
}
```

- 設定從哪來照 `aos_cli`：FSM.json（可接 `#/位置`）、`-`＝stdin；`--start`、`--state` 鏡射；`states`、`end` 不鏡射；`--` 不收。`run(x, ident=None, base=None)` 收路徑或一份設定 dict，回這拍的退出碼。不認得的 key 一律忽略（C-48；舊設定的 `ctl`、`lock`、`max_steps`、`max_fails` 也是）。
- **相對路徑**（N-36）：字串格從 FSM.json 所在的資料夾算（設定從 stdin／dict 來＝從 cwd 算，`run()` 可給 `base`）；state 窗從 cwd 算；格的 argv、`cwd`、`stdin` 照 aos_inst 從 cwd 算。
- **一拍**：讀 state 窗（檔還沒有＝從 `start` 起）→ 查格 → 跑格 → 讀格 stdout 最後一份完整 JSON → 換狀態、寫 state → stdout 吐一行。
- **跑一格**（`aos_methods.run_cell(inst, ident)`）：在本行程用 `aos_inst.run()` 跑那張 inst；**stdin 不碰**（照那張 inst 自己寫的，N-37），stdout 蓋成暫存檔（跑完刪）；stderr、exit、cwd、`timeout_ms` 照 inst。inst 寫了 `stdout_inherit`＝Conflict（格出錯）。
- **下一狀態**：格 stdout 最後一份的 `next` ＞ 表上靜態 `next` ＞ 留原狀態。**格沒輸出**（結束碼 0、stdout 空的或只有空白）＝照表上靜態 `next` 走；表上沒寫＝錯 `NoResult`（10-15 使用者）。沒輸出的格走進結束時沒有結果可交，這拍只吐那一行。
- **結束**（N-40）：(a) next 在表裡、不在 end＝進入；(b) 剛跑的狀態在 end 裡（next 在表裡也在 end，下一拍跑完它）＝結束；(c) next 不在表裡、在 end＝直接結束；(d) 都不在＝錯。結束＝那格的結果原樣吐成這拍 stdout 最後一份、phase 歸位 `start`。
- **出錯**（N-38；格結束碼非 0、吐了東西卻沒有完整 JSON 物件、沒輸出又沒寫表上 next、查不到格、next 不對）：phase 不動（下一拍重跑同一格），這拍那行多 `error`: `{"code", "msg"}`，退出碼 1。代號：`CellFailed`（msg＝格自己 stderr 最後一份 N-29 錯誤「代號: 白話」，格沒吐就寫「格 X 結束碼 N」）、`NoResult`、`UnknownState`、`UnknownNext`、`BadNext`，aos_inst 的照原代號。`error` 不是特別的格；要優雅處理、連錯停住，都是格自己的事（例 [agent.md](agent.md) 的 think 連錯回 `halted`）。被殺一半＝phase 沒變＝下一拍重跑，冪等不保證（N-20）。
- **state 窗**（只有 fsm 寫；不寫時間、pid，N-39）：`{"phase": "thinking"}`。
- **stdout**：起了格（或查格就出錯）吐一行＝那格的 aos_inst 結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、`exit_file`；沒起成格＝null）＋`from`、`to`，出錯多 `error`；這行永遠不帶 `next`，所以內層沒結束時外層留在原格。
- **巢狀**：某格的 inst 是 `aos_fsm.py 內層.json`。內層有自己的 state 窗、從自己的 TARGET 拿設定，不繼承外層的設定。巢狀格不宜寫表上靜態 next。
- **不做的**（交給拍它的 loop 或格自己，N-39）：ctl（暫停／停止）、lock、步數上限（loop 的 `times`）、連錯停住。表裡指回自己的遞迴不擋（卡死不防護）。
- **退出碼**（N-43 只認 0／非 0）：0＝這拍正常；1＝格出錯；125＝fsm 自己出錯（設定不對、窗缺 `WindowMissing`、state 讀不懂 `StateBad` 或寫不了），stderr 吐一份 `{"error": {"code", "msg"}}`。
- 格怎麼跑是格的事（N-41）：同步或非同步都行，都不自己 setsid／fork；格裡放 loop／daemon 會阻塞一拍，靠那張 inst 的 `timeout_ms` 守。
