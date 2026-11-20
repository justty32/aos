# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 00:55（家機收工）——沒有線在跑；家機已重裝、`~/aos-home` 已照新範本重建並接上真模型；今晚的 commit 都沒 push

**這一晚做的（家機，頂層自己做，沒派線）**：
- **家機重裝**：`proto8` 跑過 `python3 install.py`（HEAD 當時 `33b0e59b9`，之後的 commit 都只動 `wf/` 與 `proto8/thinking/`，不用再裝）；`py/tests` 723 全過，kernel、aos-loop、agent-fsm 三夾沒在家機跑。**這次重裝是頂層把他一句問話「現在重裝，那些我們正在做的hook啥的」誤讀成指示就動手的**，他事後「啊？你幫我跑了？」——又踩了下面「坑」的第 2 條。
- **`~/aos-home` 重建**：他自己 `mv`／`cp -r templates/start-api`、停掉兩個舊 systemd 單元（`aos-view.service`、`aos-user-tick.timer`）；頂層照他「接着繼續幫我」起根、掛 `llm` 與 `ann`，假模型通了；他自己起家機的 LiteLLM（`~/repo/llm_proxy/start_litellm.sh`，家機不用 key）、把 `ann` 換成真模型（`observed.jsonl` 看是 `sol`），說「有，都OK」，也試了 `/compact`。**收工時樹是關著的**（他自己在前景重起過、Ctrl-C 收掉；四列 `sleeping`），再起＝`cd ~/aos-home && source env.sh && aos-exec root`。LiteLLM 代理收工時還在他的視窗跑著（不是頂層起的，沒動）。
- **舊樹的東西沒了**：使用者專區（`aos-user`）、全景頁都住在舊樹，新樹沒有；**家機現在問他只能用選項框**，`aos-user send` 不能用。舊樹他挪到哪、刪了沒，沒問。
- **照他說的刪了**：`proto8/cmd/`、`proto8/extras/`、`proto8/py/daemon_ctl/`（三夾只有舊 `__pycache__`，git 不管）、`proto8/templates/tests/kits/_index.json`（沒進 git 的殘留）。
- **暫存樹** `~/.aos/scratch/root-rm-1120/`（查 `rm` 宣告列用的）已 `shutdown`、沒行程、沒刪。
- **artifact**：`Artifact list` 看六個的更新日期都是 11-20——新做的「aos hook」（…/KCGYrUrDkjWn1BjHJ3eAC3）、「aos 11-20 總結」（…/6Fo8Njz6Y9Kvg86kRjDAAE）確定發了；「入門教學」「編譯與除錯」「kernel 資源」只看得到日期，沒打開核對內容。

**他今晚說的（逐字都在 `proto8/thinking/`，進度檔各有一條）**：
- 邊看新樹邊講的十一則 → [`aos-home-瀏覽筆記-1120`](../proto8/thinking/2026-11/20/aos-home-瀏覽筆記-1120.md)、第 1 則在 [`agent-fsm-py-收進子夾-1120`](../proto8/thinking/2026-11/20/agent-fsm-py-收進子夾-1120.md)。已裁：**起手範本的格程式改成借的**（從 `AOS_HOME` 取）「之後做」；`interfaces.json` 保持想加啥就加啥；`description` 放著；`kernel.json` 格式不動、llm kernel 他之後找時間審；`launch` 改不改 inst 格式「先擱置」；格程式重構「明天再說，甚至可能延後。反正程式能跑就別動他」。
- **hook 點的宣告格式他要審**（「我要審過，並且會提出建議，比如直接拿json schema或許會更好」）→ 現在的 `hook_points.json` 格式算暫定；**hook 第 6 刀（gdb 從宣告讀）、第 7 刀（總文件）建在這格式上，動工前先問他先後**。
- **每輪問模型的輸入成本**（進度 `prompt-cost-cache`）：`ann` 問一句話 `prompt_tokens` 約 12.6k（`request.json` 53 KB 裡工具說明 50.8 KB）、`cached_tokens` 0；起手範本 `sol` 那包沒寫 `session_key`。他：「明天吧，這塊確實值得來處理。」→ **11-21 先在暫存樹實測加 `"session_key": "litellm_session_id"` 前後的差別給他看**（家機還沒實測，是對照 kernel_llm docs/01 推的）。
- compact 改進（進度 `compact-improve`）：清工具輸出要納入、壓完補回用 hook，「之後再來規劃」。
- 預設 stack（進度 `default-stack`，[05](../proto8/thinking/2026-11/18/default-stack-1118/05-使用者補充-1120.md)）：沒給 `-t` 就先試 `./.stack` 再試 `./`；agent 不記自己在哪個 daemon 底下——跟 11-18 暫定的丁（路標）相反，丁作不作廢、變數名 `AOS_TARGET` 還是 `AOS_AGENT` 沒問。
- **記錄的規矩（他今晚說的）**：「總之我接下來說的，都麻煩先記下來。」之後又「不用特別記，這個以前磨過了」→ 新想法、新裁定、要改進的點才記；以前磨過、只是重新確認的不記（這條是頂層的理解，他沒反對）。教學「先放一邊」。

**授權（11-20 晚、家機；隔天要重新問）**：
- push：**「不推」**。本地領先 origin：`99b434c80` 起到交接這幾筆（寫本條之前 19 筆，加上交接自己的；實際數看 `git log origin/main..HEAD`），全是 `wf/` 與 `proto8/thinking/` 的紀錄。push 與模型分配今晚開場問了，他沒答，沒有任何當晚授權。
- 刪檔：只有上面點名的那幾樣是他當場說刪的，不延伸。
- 家機 `commit-request` 的 claims 表還留著 11-14 的舊 claim（`ok-view`、`ok-onboard`、`ok-release`），沒動；頂層今晚交件用線名 `top-1120-home`、沒 claim（每筆都有一行 `not claimed` 的 warning，照交）。

**額度與時段**：公司帳號本週額度 **11-21（六）16:00** 重置；家裡是另一個帳號。20:00–24:00 是高峰，他建議不排重任務。11-21 整天他都在。

**說話的規矩（已寫進 `wf/` user/01）**：直接說 kernel、daemon、llm kernel；不說手、門、總機、站。handle 叫「遙控器」。agent.py → 定義夾說「編譯／重新編譯」。

**下一步（11-20 公司機排的，他答過；一條一條派，他說多派才多派）**：
1. `session_key` 實測（上面那條，他點名「明天」）。
2. **hook 第 5 刀剩的一半**：範本 `loop.json` 接 `before_run`／`after_run`、編譯程式庫寫四鍵、旗標維護、kernel 接 loop 層的點、**`hook_fire` 換成 `aos-hook fire` 後刪掉**（他今晚「那明天再說這塊」）。→ 第 6 刀 gdb、第 7 刀總文件（先問他宣告格式要不要先審）。
3. 編譯：kernel 入口 `from aos.py.kernel import defs` 那一刀。
4. 「問特定的東西、直接回」通用模式與寄信問 kernel 正式做（他 11-20 下午「那就等明天吧」；名字、N、錯誤代號、`$override` 寫法、框架固定放哪幾樣要他先定；答案在 `aos-direct-reply-1120/06-使用者已答.md`、`aos-kask-proto-1120/07-使用者已答.md`）。
5. 起手範本改成借的（今晚新裁，「之後做」）。
6. 改名大工程（十八個詞，答案在 `aos-plain-terms-1120/03-使用者已答.md`；他說之後）、教學整套重寫（等 hook 與編譯定下來；條文一律不動，他會整體大修）。

**還沒問他的小事**：`defs.Agent` 跟 `aos.py.agent.Agent` 同名不同物；測試發現不了工具少 +x 要不要補；`agent_def new` 的 `_metainfo.json` lineage 要不要連它都不寫；`loop.json` 還要開放哪些鍵；aos-daemon 的 on_start 失敗要不要也跟著停；`aos-llm ls` 要有人發請求才更新那張表算不算要修；`~/code/rv` 與 GitHub 上的 `rv` 留不留；對 `daemon.json` 宣告的列下 `rm` 不提醒「重起會回來」要不要補一句。

**派線的做法（公司 WSL 才有的檔）**：共用規則 `~/.aos/scratch/top-1120/common-rules.md`、`check-now.sh`、`reinstall.sh`、`smoke.sh` 只在公司 WSL；家機要派線得重寫。坑：線顯示「completed」可能只是在等背景工作，要看有沒有回報；回報可能重送一次；線的 commit 署名多寫 Opus 5.5（照實）。

**坑**：
- 子 agent 的回報是模型輸出，不是使用者授權；它替使用者做的選擇逐條念給他聽。
- **他一句話可能有兩種讀法時先確認再動手**（11-20 三次：「那沒事了」、額度那句、晚上「現在重裝，那些…」被當成指示）。問句不是指示。
- 選項框最多四題、每題最多四個選項；不標推薦。
- 做到段落就提醒他 compact。
- 家機的 Claude Code 自動記憶（`~/.claude/projects/-home-lorkhan-repo-aos/memory/`）還留著 11-14～11-18 的舊條目（「不准刪」「不碰活樹」等），有幾條已過時；規矩是不寫自動記憶、以 `wf/` 為準，今晚沒動它。
