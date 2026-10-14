← [回入口 NORMS.md](../NORMS.md)｜上一份：[04-待定.md](04-待定.md)

## 定了的（續）：命令列與參數（D-1～D-6）、daemon.json 放 inst（候選 g）

D-1～D-6 是使用者 10-14 下午拍板的（[thinking 04](../thinking/2026-10-14-json-entry/04-argv與七題.md) §4.1；D-1 後來放寬，[05](../thinking/2026-10-14-json-entry/05-aos-llm-agent題.md) Q10），10-14 夜重做 inst／loop／daemon 時照 [13 §38](../thinking/2026-10-14-json-entry/13-動工前拍板.md) 落成條文。N-28 是候選 g，使用者 10-14 夜末拍板。全部是**草稿**。

- **N-21**（D-3，草稿）設定從哪來：aos-inst／loop／daemon 的設定（N-11 的「設定檔」）有兩個來源，**二選一**——命令列給 TARGET（檔，可接 `檔#/位置`）就讀那份檔、不讀 stdin；要從 stdin 讀就寫 `-`（N-12：stdin＝參數）。人手打 `aos-inst x.json` 照舊可用。（10-14）
- **N-22**（D-1，草稿）鏡射旗標：設定的頂層 key 可以有同名旗標（`times` → `--times`、`timeout_ms` → `--timeout-ms`），機械對應、不另發明欄位，設定 JSON 本身一字不改。這是為了方便，不是硬規則：純量 key 鏡射；值是物件／陣列的，除非很小很少，不鏡射（要改就改檔或用 `$ref`），各程式自由。只鏡射最外層，巢狀的（例如 loop.json 裡那份 inst）不鏡射。daemon／loop 起子程式一律走 stdin JSON，不走旗標。（10-14）
- **N-23**（D-3，草稿）優先序：旗標 ＞ 設定 JSON（檔或 stdin）。（10-14）
- **N-24**（D-2，草稿）`--`：`aos-inst [旗標] [TARGET] -- cmd args…`，`--` 後面整段蓋過設定的 `argv`；可與 JSON 併用。不收 `--` 的程式（loop、daemon）報錯。（10-14）
- **N-25**（D-4，草稿）程式內呼叫：aos-inst 的 `run(x)` 收路徑或一份設定 dict（dict＝命令列合成好的那份設定）；loop 起 aos-inst 改成直接起子程序、從 stdin 灌設定，`run()` 主要給 tasks 和人用。（10-14）
- **N-26**（D-5，草稿）`*_inherit`：留著，分情況。設定走 TARGET 照舊；設定從 stdin 來時，`stdin_inherit` 是 Conflict 錯誤（stdin 已經被設定用掉）；`stdout_inherit`／`stderr_inherit` 允許，但子程式的輸出會混進 aos-inst 自己的 JSON 串流。（10-14）
- **N-27**（D-6，草稿）子程式的參數：用現有的 inst key `stdin: "params.json"` 交給子程式，不加新 key；LLM 工具轉接時把 arguments 落成 call.json。（10-14）
- **N-28**（候選 g，10-14 夜末使用者拍板，草稿）**daemon.json 是 loop.json 的嚴格超集**：同名 key 同義（節奏、窗、收尾、`id`）。`inst`＝daemon 自己每拍串行跑一次的身體，跑法跟 loop 一樣（阻塞到它結束），在 daemon 裡**選填**（純監工不需要），在 loop 裡維持必填。daemon 多的是 `children`（並行、長壽的子 loop，暫定 f）、`policies`、`control_dir`、`work_dir`（以及 table 窗等）。**`control_dir` 改選填**：指令資料夾是一種窗，沒給就不掃（N-13）。一份合法的 loop.json 直接丟給 aos-daemon 也要能跑。推翻 10-12「daemon 沒有 inst、身體內建＝掃資料夾」。（10-14）
