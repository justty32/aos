# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-13 20:30 家機頂層（樹外的 Claude Code）交棒給樹裡的 repo-aos

1. **授權與工作方式**：在家機（Manjaro）。使用者開場：「事情盡量交給agent做，普通工作交給opus，簡單工作交給sonnet。agent做事前要讀過wf/規矩，簡單工作除外。晚上十一點睡覺前再push。」；「今天的優先目標是幫我架起aos」；「總之先搭好。後面我要把你這個session關掉，咱們走aos」——**之後的頂層是樹裡的 `repo-aos`**，這個樹外的 session 會關掉。fable 照 user.md「盡量少用」。
2. **push**：23:00 睡前推一次，推之前跟使用者說一聲（數量看 `git log origin/main..main`）。
3. **家機今晚定的**（細節 [aos-home-家機](../proto8/thinking/2026-11/13/aos-home-家機.md)、[日誌](session_logs/2026-11/2026-11-13.md)）：
   - **repo 改放 `~/repo/aos`**（「直接放~/repoaos」「~/repo/aos」）：從舊位置 clone、origin 指 GitHub；舊的 `~/repo/simple_tools/aos`（`simple_tools` 的子模組）使用者說「不用刪」，留著、不再當工作 repo。impls 在新位置全部重 build，`~/.local/bin` 25 條 `aos-*` 與 `.pth` 都指 `~/repo/aos`（舊 `.pth` 改名留著）；全套 69 夾 1599 例全綠（公司機那 4 支既有紅與 gitignore-check 在家機都沒紅，原因沒查）。
   - **樹住 `~/aos-home`、從零搭**，陣容 `eca_main`＋`repo-aos`（都 opus；`repo-aos` 工作區 `~/repo/aos`、定義在 `~/aos-home/agents/repo-aos`）。兩隻會答、互寄信收得到、停樹再起 history 在；存檔 `~/aos-saves/aos-home-1113-home`。**驗完樹停著，起樹由使用者自己下**；指令在 [wait-user/03](wait-user/03-試驗場.md)。沒驗：`aos-agent open`（畫面）；`~/aos-home/ws`、`~/repo/aos` 兩處開畫面前要使用者各開一次 `claude` 按信任。
   - **`.zshrc` 自動 source**（使用者「我想要把它加入我的.zshrc」「要」）：舊的 `export AOS_HOME=…/simple_tools/aos/proto8` 換成 `[[ -z $AOS_STACK && -f ~/aos-home/env.sh ]] && source ~/aos-home/env.sh`（agent 底下的 shell 帶 `AOS_STACK` 就跳過）；三項實測都對。實際檔是 `~/dev/dotfiles/zsh/.zshrc`（那個 repo 有一筆沒 commit 的改動、沒代他 commit），備份 `~/.zshrc.bak-1113-aos-home`。
   - **舊 aos MCP 那行已拿掉**（選項框「搭好就拿掉」）：`~/.claude.json` 裡 `~/repo/simple_tools/aos` 專案的 `mcpServers.aos` 刪了，備份 `~/.claude.json.bak-1113-aos-mcp`；`arcagi` 專案那行與 `~/.cache/aos-mcp-*` 兩格沒動（`aos-mcp-arcagi/tools.json` 有 3 處寫死舊 repo 路徑，舊 repo 留著所以還能用）。
   - 收工待裁頁 W7、W16、W17、W18、W23 已施工（`ff97da487`）；wf-lint 刪掉後的補掃做完。
4. **留著的**：
   - `env.sh` 只清三個 Claude Code 變數；從 Claude Code 的 shell 起樹還會帶 `CLAUDE_CODE_SESSION_ID`、`CLAUDE_CODE_MESSAGING_SOCKET` 等給樹裡的 claude，有沒有影響沒驗、正本要不要改沒定。
   - W16「改口摺疊」那節要不要也補進知識庫（WAIT_USER 01）。
   - `wait-user/03` 裡「家機試驗場 11-12 晚……樹開著」那條可能過時；`~/code/playground` 原樣留著。
   - 線家的代定（`repo-aos` 用 `--tools default`、`--auto-restart`、`--on-busy yield`、`system.txt` 用絕對路徑、不抄 `kernel/`）在 aos-home-家機，可翻案。
5. **接下來**（家機能做的，全貌在下一條第 9 點與 [SESSION-LOG](SESSION-LOG.md)）：各 agent 意見整理成題目、workflows 併入第 3、4 塊（模板 repo 在 GitHub）、`set-def` 與「換定義後提醒在等的信」兩件已裁未施工、kernel 批 7b／11b／12、真腦驗證（批 13、14）。公司機那棵樹要的事回公司機做。
