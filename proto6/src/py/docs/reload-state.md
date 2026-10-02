# proto6/src/py — 重讀設定與記住狀態

← [proto6/src/py README](../README.md)｜上一份：[控制模組與 aos-ctl](ctl.md)｜下一份：[收屍／cgroup](cgroup.md)

## 重讀設定與記住狀態（m3m）

照 [plan m3m](../../../plan/m3m-daemon-modules.md) 模組一、三寫的（2026-10-01 第十一批）。各自有寫才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000,
 "modules": {"control": {"socket": "./aos.sock"}, "reload": {}, "state": {"$ref": "aos-state.json"}},
 "insts": {"a": {}, "jobs/report.json": {}}}
```

**重讀設定**（`modules.reload`，`lib/aos_daemon_reload.py`，spec [B-642](../../../spec/settled/daemon/reload.md)）：改了設定檔就 `kill -HUP <pid>`，daemon 重讀同一份（照樣整份展開指示詞）：

- 新的鍵：立刻跑一次，stdout `inst=<inst> added`；不見的鍵：不再排，正在跑的那次跑完照樣印 `exit=`，之後控制指令回 `unknown_inst`，stdout `inst=<inst> removed`；還在的鍵：換新設定，暫停、已停、待補照留，`interval_ms` 改了下一次＝上次結束＋新週期（過了就立刻跑）。最後一行 `reloaded`。
- 頂層 `cwd`、`modules`、`exec_out_path`、`exec_err_path` 改了不套用，stdout `reload: need restart: <鍵名>`（後兩個 2026-10-01 第十二批從「照新的」改成警告；新加的項的輸出路徑也照開起來時的設定算）。
- 設定壞了：整份不套用、stderr `aos-daemon: reload: <說明>`、舊的照跑。
- 沒掛時 SIGHUP 照 Python 預設殺掉 daemon。掛了時用 `signal.set_wakeup_fd` 收（不會漏），主執行緒讀 pipe、重讀。

```text
2026-10-01T16:45:49+08:00 reload: need restart: cwd
2026-10-01T16:45:49+08:00 inst=c.json removed
2026-10-01T16:45:49+08:00 inst=b.json added
2026-10-01T16:45:49+08:00 reloaded
```

**記住狀態**（`modules.state`，`lib/aos_daemon_state.py`，spec [B-643](../../../spec/settled/daemon/state.md)）：原始設定檔的 `modules.state` 必須寫成 `{"$ref": "<檔>"}`（以設定檔所在資料夾為準、不帶 `#`），那個檔就是狀態檔：`{"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}`，只列不正常的項。

- pause、resume、`stop_on_nonzero` 停掉、重讀拿掉項時當場寫整份（暫檔 → rename），內容沒變不寫；檔不在＝全部正常，沒異常就不建。
- 開起來時照檔恢復：暫停、已停的項不先跑那一次，stdout 先印 `inst=<inst> paused`／`stopped`；檔裡有、設定沒有的鍵丟掉。
- 跟重讀設定一起掛時，重讀以記憶體為準，不重讀狀態檔。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon.load_full()`、`Setup`、`_state_ref()` | 讀設定；先把 `modules.state` 的 `$ref` 拿出來（檔不在不算錯），其餘照整份展開 |
| `aos_daemon._items`、`_items_lock`、`snapshot()`、`give_env()`、`start_item()` | 共用的清單（控制模組查的也是它），重讀時原地改 |
| `aos_daemon._catch_hup()`、`main()` 的主迴圈 | 收 SIGHUP |
| `aos_daemon_reload.reload()`、`_update()` | 比對清單、套用 |
| `aos_daemon.state_changed()`、`aos_daemon_state.StateFile.save()`、`restore()`、`dump()` | 寫檔、讀回 |

測試 `tests/test_daemon_reload.py`（15 條，約 11 秒）、`tests/test_daemon_state.py`（11 條，約 4 秒）。
