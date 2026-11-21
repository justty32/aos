← [入口](../STRUCTURE.md)｜涵蓋：archive 規則、資料檔慣例｜上一份 [03-成長軌跡與統一形式](03-成長軌跡與統一形式.md)

## archive 規則

- 過時 / 被取代的文檔搬進**所屬工作流**的 `archive/`（共享的進 `common/archive/`），**不刪**、不在維護鏈。
- **例外：已封存工作流的空入口集中搬、不留指標頁**（使用者 11-17 待裁網頁 wf-4 選 a）：收進 `wf/workflows/archive/`（頂層的 `salvage/` 進 `advices/archive/`，停用的 `progress_board`、`decide_page` 進 `tools/archive/`，wf-4b a），交件帶 `--rm`、要使用者親跑或點頭。
- **預設留指標頁，不移除舊路徑**（頂層 2026-11-14 定）：全文抄成 `archive/` 底下的新檔，原路徑改成幾行的指標頁（為什麼停用、現在怎麼做、全文在哪；別處連進來的錨點在指標頁補 `<a id>`）。這樣交件不帶 `commit-request --rm`、不用使用者親手跑，也合使用者「不刪」的偏好。只有使用者明說要移除舊路徑時才真的搬走（`mv` 後 `--files` 新路徑加 `--rm` 舊路徑），那種要預先排使用者跑：agent 的權限模式不讓跑帶 `--rm` 的指令。出處：10a75ac53（封存 hackathon、workshop，卡在 `--rm`、最後使用者親跑）、`dispatch/aos-teams/04-進度回報.md`（指標頁做法）。
- 檔名保留原名（放進別層的 `archive/` 會撞名或看不出來源時，可加來源前綴）；檔頭第一行加 `> 封存 YYYY-MM-DD，由 <取代它的路徑> 取代`（沒有取代者就寫原因）。
- **指向被封存檔的連結從活文件拿掉**（改純文字或刪句），**當它不存在**；不改指到 `archive/` 路徑。
- `archive/` 內**只有 `README.md` 索引**（可省略；一列一檔：檔名、封存日期、取代者或原因；**只准追加列**），是唯一可以連進 `archive/` 的地方；不套大小門檻、不維護內部連結。

## 資料檔慣例

新寫的預設寫 `.md`、用 index json 當骨架，要用 `.md` 還是 `.json` 都可以（使用者 11-21；門檻是建議、不做檢查）。抽成 `.json`／`.csv` 的門檻與格式契約 `wf-table/1` 在 [workflows/common/data-files.md](../workflows/common/data-files.md)；讀寫走 `tabledb.py`；整理流程走 [workflows/tidy/README.md](../workflows/tidy/README.md)；json 內跨層路徑可用 `$fmt` 代號（見 [data-files-fmt](../workflows/common/data-files-fmt.md)）。
