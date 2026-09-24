← [agent](README.md)｜[spec 總導航](../README.md)

# 1. 資料夾長什麼樣

```
agent-bob/
  info.json      人寫的設定（§3）
  state.json     程式寫的進度（§4）；檔不在＝全預設
  tick.json      aos-agent start 寫的：kernel 反覆跑的那份 inst（aos-agent.md §11）
  .tick.lock     tick 整格持著的 flock（aos-agent.md §2.1）；內容是持有者 pid，不刪（09-24 fix-r4 補）
  .admin.lock    管理鎖：tools／access 的寫入指令持著的 flock（空檔、不刪；tick 不拿）（09-24 access-impl 補）
  paused         有這個檔＝手動暫停，tick 什麼都不做（aos-agent.md §1.6）；pause 建、continue 刪（09-24 fix-r4 補）
  access.json    人寫的：工具關進牢裡看得到哪些資料夾（§3.5）；沒有＝要關牢的工具都不送、NoAccess（09-24 access round2 改；`init` 現在會生一份預設）
  resumed        有這個檔＝continue 解了連敗暫停、還沒等到一次成功（aos-agent.md §1.4）；continue 建、think 成功結清時 tick 刪（09-24 fix-r5 補）
  prompts/       慣例：人格、記憶
  tools/         慣例：工具檔
  input.json     慣例：輸入（§4.1）
  work/          aos-agent 的工作區：<工作名>.inst.json、.in、.out
  done/          收過的輸入與 consume 過的門檔（§4.1）（09-24 試玩 r1 補）
  log/           llm.err、agent.err，以及工具自己指定的
```

- 只有 `info.json`（且 `_metainfo._type` 是 `llm_agent`）是「這是 agent 家」的依據。
- 相對路徑一律相對 agent 家。**只有** `input`、`tools` 的元素、`waits` 的路徑可以指到資料夾＝裡面所有 `*.json`（`.done` 結尾的不算）照檔名排序；
  `system`、`history` 必須是單一檔案（指到資料夾＝`FieldTypeMismatch`），因為記憶要整份寫回同一個檔。
- 慣例上 `info.json`、`access.json`、`prompts/system.json`、`tools/` 是人寫的，其餘是程式寫的；規範不管權限。
- 頂層都是嚴格的物件或陣列；不認得的 key 一律忽略。
- **寫檔的兩種做法**（別混）：agent 家自己的檔（`state.json`、記憶、`tick.json`、`work/` 的 inst 與 `.in`）用同目錄
  `.tmp` 再 `rename`；投進 kernel 家 `K/requests/` 的 request 與 ack 用 [cpu.md §3.1](../cpu/messages.md) 的唯一 `.tmp`＋`link`。
  `work/*.out` 是工作 inst 的 stdout 重導向產物，不保證原子，只在那件工作的回音到了之後才讀（aos-agent.md §6）。
- `work/` 由 aos-agent 建、由 aos-agent 清（清的條件在 aos-agent.md §10）。
