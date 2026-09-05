# 給 codex 的任務書（Janet 綁定收尾，2026-09-05）

你在 /home/lorkhan/repo/langs/janet-lab 工作（Janet 1.41.2、jpm、spork）。另一個 repo /home/lorkhan/repo/simple_tools/aos 是 aos 專案：新規定在 wf/workflows/spec/（先讀 README.md、01-terms.md、07-call.md、07b-result-path.md），能跑的 Python 原型在 proto/（讀 proto/README.md）。

背景：前一隊 Claude agent 已經在 janet-lab 寫好 `modules/aos/`（8 個檔，門面在 init.janet，先整個讀完）、`project.janet` 的 declare-source、四支測試 `test/aos-*.janet`、範例 `examples/aos-call.janet`。它們現在都能跑（`janet test/aos-util.janet` 等四支各印一行「通過 ✓」，範例 `janet examples/aos-call.janet` 跑完退出 0）。那隊在寫文件前被 API 額度打斷，剩下的就是你要做的。

硬規則：
- 不 commit、不 push、不 git add（兩個 repo 都不准）。
- janet-lab 只准碰：`modules/aos/README.md`（新建）、`modules/README.md`（加一列）、`test/aos-*.janet`、`modules/aos/*.janet`（只准修 bug，不准重寫結構）。aos repo 只准新建一個檔：`wf/workflows/spec/notes/janet-binding-findings.md`，並在 `wf/workflows/spec/notes/README.md` 加一列指到它。
- 所有文字用大白話中文；每個 md 檔 ≤ 12 KB。
- 環境變數 `DEEPSEEK_API_KEY` 不准印出、不准寫進任何檔。

要做（照順序）：
1. 讀完 modules/aos/ 八個檔與四支測試，照 janet-lab 其他 module（modules/llm-http、modules/pi-shell）的 README 風格寫 `modules/aos/README.md`：兩句話講它是什麼、怎麼裝／怎麼跑測試、公開 API 一張表（函式名、參數、回什麼、對應 spec 哪條）、`AOS_PROTO`／`AOS_HOME` 兩個環境變數、一段最短範例（從 examples/aos-call.janet 節錄）、已知限制。
2. `modules/README.md`（若存在）加一列 aos；若 janet-lab 根目錄有 README.md／INDEX.md 的 module 清單也加一列。
3. 對照 spec 檢查這個綁定：呼叫記錄欄位、投遞（`.json.temp` → rename）、結果落點與 `<result>.status.json` 三態、登記表那筆，跟 spec 07／07b／08 條款與 `wf/workflows/spec/schemas/` 的 schema 是否一致。不一致的分兩種：綁定寫錯 → 修（只修最小處，改完四支測試與範例仍要過）；spec 沒講或 spec 本身有問題 → 記進第 4 項的發現檔。
4. 新建 `/home/lorkhan/repo/simple_tools/aos/wf/workflows/spec/notes/janet-binding-findings.md`：標題、一段「這是什麼」、然後每條發現一行，格式照 `proto/FINDINGS.md` 的「每條怎麼讀」（**標題**｜依據：條款號｜卡在哪｜怎麼繞｜類別｜擋路程度）。至少要回答：從另一種語言綁這套檔案協定，哪些地方非得 shell 出去叫原型不可（現在是 exec／run／daemon）、哪些純靠寫檔就能做；spec 哪幾條讓純寫檔做不到。
5. 最後跑：`cd /home/lorkhan/repo/langs/janet-lab && for t in test/aos-*.janet; do janet $t || echo FAIL $t; done` 與 `janet examples/aos-call.janet`，全部要過。

回報格式：每項一行「做了／沒做＋檔案」，撞到的事，最後測試結果。
