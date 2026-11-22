各 agent 的私有地盤（wf/ws/<名>/，subagent 嵌在上層底下）與地盤規矩：放什麼、怎麼嵌、什麼進 git、誰建。

# wf/ws：私有地盤

← [AGENTS.md](../../AGENTS.md)｜依據：使用者 11-22 決定 B、C（[01-決定與調查](../../proto8/thinking/2026-11/22/工作區與stack-1122/01-決定與調查.md#決定)）、[02-規劃 線 1](../../proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md#線-1gitignore-與私有地盤)

地盤像每個人在公司裡分到的一格抽屜：辦公室（工作區）大家共用，抽屜裡放自己的東西。使用者 11-22：「這是未來的權限的基礎。現在就是讓他們有自己的私有地盤這樣」。

## 地盤規矩

1. **工作區（cwd）不變**：大家都是 `~/repo/aos`。地盤是另外配的一塊，放自己的草稿、筆記、任務書、自己做的定義夾。
2. **路徑照掛的層級**：頂層 agent 是 `wf/ws/<名>/`，它掛的 subagent 是 `wf/ws/<上層>/<名>/`，再往下照樣嵌（例：`wf/ws/eca-aos/eca-aos-templates/`）。
3. **地盤進 git；任何一層的 `temp/` 不進**（根 `.gitignore` 的 `temp/` 那行）。放不放 `temp/` 的判準一句話：**換台之後還要用的放地盤，其他放 `temp/`**（大檔、跑出來的產物、log、抄來的複本、暫存樹都算其他）。
4. **誰建**：上層替下層建——`subagent add` 之前先 `mkdir` 並放一份 `README.md`（第一行一句話說這是誰的地盤；git 不收空資料夾），在任務書裡告訴它地盤在哪。同一步在它的 stack 寫 `notes_path`（一行：它的筆記檔路徑，相對工作區 `AOS_WS` 或絕對，例：`wf/ws/eca-aos/eca-aos-kb/notes.md`），並在它的系統文字寫一段筆記用法（筆記在哪、什麼時候寫、compact 後先讀它）。壓縮後重讀的 [`compact_reload.sh`](../tools/compact_reload.sh) 在 subagent 裡不貼頂層的 `wf/HANDOFF.md`，改指向 `notes_path` 寫的那個檔（使用者 11-22 照[提案](eca-aos/eca-aos-templates/notes-hook-提案.md#要使用者選的題目)推薦定第 3 題 A＋b、第 4 題 a：「我人還在外面玩，總之先按推薦做」）。
5. **現在只是規矩，不是牆**：commit-request 不查誰交了誰地盤裡的檔，其他 agent 讀得到也改得到。牆等以後的權限系統。
6. **交件一樣走 commit-request**（[規矩卡「交件」](../workflows/common/rules-card.md#交件aos-teams-第-1-件07commit)）。commit-request 會查單檔大小：`--files` 點名的檔有一個超過 1 MB（1,048,576 bytes），整個申請不收（`FAILED RequestBad`，什麼都不 commit）。門檻與放行名單是 [`wf/tools/commit_queue.json`](../tools/commit_queue.json) 的 `max_file_bytes`、`big_ok`；那份從 main 讀，要改門檻或放行一個檔得先把它交件；`_stack/` 底下、`--rm`、`--op` 不查。單檔太大被擋，多半是該放 `temp/` 的東西進了追蹤（使用者 11-22：「如果太大，那就代表agent不守規矩，把本該進temp的也進track」）。

另外：地盤裡不建 `_index.json`（`wf/tools/index_gen.json` 的 `skip_dir_names` 跳過名叫 `ws` 的夾，只在上一層留一項）。

## 現有的地盤

- `eca-aos/`：頂層 `eca-aos`。
  - `eca-aos/eca-aos-templates/`、`eca-aos/eca-aos-kb/`、`eca-aos/aos-eca-frontend/`：掛在 eca-aos 底下的三個 subagent。
