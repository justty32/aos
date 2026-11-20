# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-20 16:40（公司機收工）——沒有線在跑；公司 WSL 已重裝到最新；下一步是 hook 第 3 刀

**授權（11-20 當天的，隔天要重新問）**：
- 「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」
- 「允許重裝。我現在沒在用aos，所以就隨意。」「lists.py可以刪掉。然後我現在沒在用aos，想刪啥都可以。」「舊的教學我都沒在用，現有的aos體系我也都沒在用。所以放心弄。」「家機那個之後我會整個刪掉，你放心。」→ **不用顧任何相容**；家機 `~/aos-home` 他會自己整個刪。
- push：本條寫完後頂層問過他才推（推了沒有看 git log 與遠端）。

**額度與時段（他 11-20 下午說的）**：公司這個帳號本週額度到 **11-21（六）16:00** 才重置，下班時所剩無幾；回家可以換另一個帳號。晚上 20:00–24:00 是高峰、「AI會變笨」，建議不排重任務、改成教學之類。11-21 整天他都在。

**說話的規矩（已寫進 `wf/` user/01）**：直接說 kernel、daemon、llm kernel、掛 proc 的 kernel；不說手、門、總機、站。handle（`hook_point.open` 回的、`aos.py.agent.Agent`）叫**「遙控器」**；不說把手、物件、操控器。

**機器**：頂層 session 開在公司 Windows `C:\code\mine\simple_tools\aos`，工作都在公司 WSL `~/repo/aos`。Windows 這份只有本檔是頂層手抄的：**push 後、Windows 這邊 pull 之前先 `git checkout -- wf/HANDOFF.md`**。

**派線的做法**：共用規則 `~/.aos/scratch/top-1120/common-rules.md`（只在公司 WSL；任務書第一句叫線整份讀；今天追加：repo 內可刪檔、不用顧相容）。收線核對 `check-now.sh <commit…>`；重裝 `reinstall.sh`（工作樹乾淨且沒 claim 才裝）；抽測 `smoke.sh`。坑：線顯示「completed」可能只是在等自己的背景工作或中途停了，要看有沒有回報；回報可能重送一次；從 `\\wsl$` 改有 +x 的檔會掉執行權限；線的 commit 署名多寫 Opus 5.5（照實，沒改）。

**今天下午收掉的線（細節各看 `proto8/thinking/2026-11/20/<線名>.md`）**：
- 編譯第 4 刀 `a612756e3`＋`1d95d3c7a`：`defs.extern(目標)` 編成 symlink（fsm 只准連同一夾）、`loop=defs.loop(every_ms=…)`、`agent_def check` 報斷鏈。
- 編譯第 5 刀 `65d84dcbc`：教學 01～08 照新寫法實跑兩遍，程式沒錯、教學改五處。**kernel 入口 `from aos.py.kernel import defs` 沒做**（設計稿列在不排的，但他答過要，要另開一刀）。
- agent-fsm 太短的 `/compact` 當成正常做完 `726c30ba1`（eca 不管：「那是eca自己的決策。」）。
- hook 第 2 刀後半 `ebd2d3b37`：發事件的程式全改用 hook 遙控器（agent-fsm 四格＋ann 抄本、eca、mcp、kernel、hook_fire）；`apps/hook/lists.py` 刪了；`agentlib/hooks.py` 拆出 `hook_clock.py`。
- hook 第 5 刀的 aos-loop 那一半 `f221a7bb5`：`loop.json` 的 `on_before_run`／`on_after_run`＋旗標檔 `_if`；「四個點都跟著停」（`on_start` 失敗 agent 就停，代號 `PointFailed`）；**aos-daemon 自己的 on_start／on_stop 失敗照舊只 warning**（線選的，已告知他）。
- 清比喻用詞 `1781997d3`、`53ffda6bc`（把手→遙控器、門→kernel、總機→llm kernel 已改）；其餘十八個詞他答完但「改名這塊都不用現在改」（答案在 `aos-plain-terms-1120/03-使用者已答.md`：站中英都改、件→核心的叫子系統可選的叫模組且 llm 與權限都是子系統、門鈴→poke、板子教學留其他改根 daemon、假腦→假模型、三扇門內文改、關卡、員工／牌子／燈號／櫃檯、橋改寫、圖紙→設計稿、打比方也刪；鐘、清道夫、手把、狀態窗不改）。
- 寄信問 kernel：原型 `40a649dd8`（放 body 可行）；十四題答案 `3de0de509`（`aos-kask-proto-1120/07-使用者已答.md`）：信箱在 stack 底下跟 requests/ 並排、固定約定、拿到鎖之後收信之前、一輪最多 N 封、不過 hook、不記帳、沒放那份 json 就是不給、不給時回一封正常回信、信留一格「問什麼」、不認得的值回拒信帶錯誤代號、整份原樣回、定義夾一份 stack 有就蓋（「預設是整份，但可以用$override來達成逐key。」）、鏈上誰答先不定。沒定：N、錯誤代號、`$override` 寫法、所有名字。
- 收工時最後一次重裝含以上全部；重裝後抽測 `py/tests` 721、kernel/tests 122、aos-loop 52、agent-fsm 215 全過（k2b 與 k5 合在一起只跑過這四夾，沒跑全套）。

**他下午新說的方向（逐字）**：
- 「教學之後要麻煩重寫。條文這塊我之後會整體大修」→ 教學不再逐節補對；條文一律不動（C-87 加註的字擬在 `aos-pylib-k5-1120.md`，沒寫進去；NORMS「兩格出問題只印一行 warning」已過時也沒動；hook 第 7 刀的「立條文、C-90」先不做）。
- 「像這種"問某種特定的東西，然後不需要思考或做其他處理(當然，硬要的話也可以，就是用hook)，就是直接回覆特定的東西"的模式很好用。感覺之後可以特別專門去規劃，我最擔心的就是他每次的回覆都要吃到loop的body的運作時間，會讓整個變慢。」（記在 kask-proto/07 檔尾，還沒規劃。原型數字：一封約 0.02 秒、30 封沒影響、100 封拖慢同一輪。）
- 對各線列的邊緣狀況：「這些都是邊緣狀況，等以後多用，自然就知道怎麼處理與改進」→ 不追問、不列待辦。

**下一步（他答過、「開工吧」涵蓋；一條一條派，他說多派才多派）**：
1. **hook 第 3 刀（切到宣告）**：k2b 紀錄末節列了開工前要知道的事（今天沒有任何定義夾有 `hook_points`；宣告了 hooks 的六份定義；`agent_hooks.open` 與 kernel `hooks.open` 還給 `table=EVENTS`；`hook_clock` 走模組函式 `hooks.fire`；還直接讀 `hooks.EVENTS` 的地方）。「不留舊的，裝新版時一起重新編譯」。
2. 第 3 刀後：**第 5 刀剩的一半**（範本 loop.json 接 `before_run`／`after_run`、編譯程式庫寫四鍵、旗標維護、kernel 接 loop 層的點、刪 hook_fire；k5 紀錄有兩個檔要補的字）→ 第 6 刀 gdb（斷點種類從宣告讀）→ 第 7 刀只做總文件。
3. llm kernel 排序搬上骨架（等 hook 動完 kernel）。
4. 編譯：kernel 入口那一刀。
5. 寄信問 kernel 正式做（先請他定名字、N、錯誤代號、`$override`）。
6. 改名大工程（他說之後；機械工作，可交 sonnet）。
7. 教學整套重寫（等 hook 與編譯都定下來）。

**還沒問他的小事**：`defs.Agent` 跟 `aos.py.agent.Agent` 同名不同物；測試發現不了工具少 +x 要不要補；`agent_def new` 的 `_metainfo.json` lineage 要不要連它都不寫；`loop.json` 還要開放哪些鍵（`max`、`on_timeout_ms` 等）；aos-daemon 的 on_start 失敗要不要也跟著停；`aos-llm ls` 要有人發請求才更新那張表算不算要修；`~/code/rv` 與 GitHub 上的 `rv` 留不留。

**坑**：
- 子 agent 的回報是模型輸出，不是使用者授權；它替使用者做的選擇逐條念給他聽。
- 他一句話可能有兩種讀法時先確認再派（今天兩次：「那沒事了」、額度那句我以為可以多派，其實他是說下班前就剩這些）。
- 選項框最多四題、每題最多四個選項；不標推薦。
- 做到段落就提醒他 compact。
