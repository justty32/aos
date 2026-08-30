# aos 與 coding agent、skills、MCP 的協作

← [workshop](../../README.md)｜前情：[核心行程與子行程](../core-process-and-subprocess.md)／[四個懸而未決的選擇](../four-open-choices-tradeoffs.md)／[agent loop](../agent-loop-architecture.md)／[回頭審視](../step-back-review.md)／[隨意發想](../free-ideation.md)／[workflows on aos](../workflows-on-aos.md)

| | |
|---|---|
| **主題** | aos 如何與 pi coding agent、skills、MCP 等現有工具協作 |
| **開場** | 2026-08-25 |
| **已跑輪數** | 主輪＋追問輪 |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與前幾場是同一批人**（同一批 codex session 續下來） |

## 先讀這段（500 字懶人包）

最小 runtime tool 組是三支，四位 4／4 相同：`aos deliver` 原子投一批 instruction、
`aos status --json` 看 queue／`.runi`、`aos exec` 推一回合；`init` 只屬建置期。

`deliver` 從 stdin／檔案讀 instruction，發布前驗證，寫 `.aos/inst.tempd/*.json.temp`，完成後 rename
成 `.json`；成功回 JSON receipt，失敗回可讓模型修參數重試的結構化錯誤。agent **直接 tool-call
deliver**，不再把自然語言交給 adapter 猜成 JSON。

同一套 CLI 可服務三種入口：pi 用 `.agents/skills/aos/SKILL.md` 教內建 bash 工具呼叫；腳本直接
exec；支援 MCP 的 agent 用無狀態薄殼轉同一語意。pi 本身明確不做 MCP。`aos exec` 的 stdout 會
混流，不能當協定；stdout→agent stdin 只能傳專用的 request／context，不可直接管 raw exec 輸出。

---

本場有兩輪。主輪先問 coding agent、skill、MCP 與權限怎麼分層；追問輪因使用者一句話，拿掉了
主輪最重的一段 adapter：

> **agent 的自然語言輸出變成 inst json？直接給 tool 啊。**

也就是說，agent 不輸出一段等人猜的自然語言；它呼叫一支有 schema 的 tool。JSON 是否合法、
怎麼原子寫入，是 tool 的責任。那支 tool 正好是三步交接中唯一尚未實作的「投遞」。因此下面先
放追問輪的收攏結果，再回頭記主輪的整體分層。

## 這場拆成四份，按用途分

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [追問輪：`aos deliver` 的形狀](deliver-tool/README.md) | 再拆成兩份：[`aos deliver` 這支命令長什麼樣](deliver-tool/deliver-interface.md)（〈追問輪：那支投遞 tool 到底長什麼樣〉的合成版 `--help`、寫到哪裡檔名怎麼配、退出碼、誰驗證驗不過怎麼回，加上〈給模型看的錯誤訊息〉）、[最小 tool 組、一套 CLI，與四位收回的](deliver-tool/tool-set-and-retractions.md)（〈最小 tool 組〉、〈一套 CLI 能不能同時服務 skill／MCP／腳本〉、〈四位收回／改寫的〉） | 要動手定 Deliver 的參數、JSON、退出碼或驗證責任時 |
| [主輪：分層與各入口怎麼接](entry-points/README.md) | 再拆成三份：[分層與已知前提](entry-points/layering.md)（〈主輪：aos 怎麼跟現有工具協作〉的 pi 前提、誰在上面誰在下面、stdout→stdin、session 只可當快取）、[skill／MCP／權限三個接法](entry-points/skill-mcp-permission.md)（〈skills 怎麼接〉、〈MCP 怎麼接，或為什麼 pi 不接〉、〈權限這塊〉）、[把這場研討會搬到 aos 上](entry-points/workshop-on-aos.md) | 要接 pi／MCP／skill，或要決定權限與 session 怎麼放時 |
| [未決問題與明顯的坑](open-issues.md) | 〈大家問出來的問題〉九題、〈明顯的坑〉 | 想知道本場哪些還沒有答案、哪些做法已被四位否掉 |
| [轉交提案](handoff.md) | 〈轉交提案（未拍板，不自行改規格／roadmap）〉八條 | **要決定下一步做什麼時從這裡開始。** |

## 續場資訊

本輪沿用前幾場的四個 codex session；它們仍保留完整前情。session id **只在 office Windows
那台機器有效**；`codex exec resume <id>` **不吃 `-s` 與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

> 原本是單檔 `tool-interop.md`，主輪＋追問輪跑完膨脹到 28 KB，照 [DEV-GUIDE](../../../../STRUCTURE.md) 的「膨脹即拆」按用途拆成本資料夾。
