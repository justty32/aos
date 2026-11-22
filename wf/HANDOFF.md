# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-22 下午（家機，使用者在外面、用 Remote Control）——搬家中：外面的 Claude 跑 home-move，eca-aos 從 `~/aos-home` 搬進 `~/repo/aos/_stack`

**醒來先做**（eca-aos，搬完或退回後）：
1. 看 `~/.aos/scratch/home-move-1122/run-all.log` 最後幾行：`run-all: done`＝搬好；`rolled back`＝退回舊樹；其他＝卡住，查 `home-move.log`。
2. 搬好時核對：`subagent ls` 要 3/4；`echo $AOS_STACK` 在 `_stack/procs/eca-aos`；跑 `bash ~/repo/aos/wf/tools/home-move-1122/home-move verify`。
3. 收掉被打斷的線 A（`prompt-cache-key-1122`）留在 `~/.aos/scratch/prompt-cache-key-1122/` 的行程：只收 cwd 在那個夾裡的（`readlink /proc/<pid>/cwd` 核對後 kill），再重派 A（任務書在對話紀錄；要點：暫存 LiteLLM 放行 `prompt_cache_key`、20 輪比改前改後、正式那台不碰、第二段等回覆）。
4. 告訴使用者結果、新的 Remote Control 要在 Claude app 的 session 列表找新的那個。他晚上要：真模型的 `LITELLM_KEY`（`aos-daemon-ctl -d ~/aos-home/.llm-stack shutdown` 後從有金鑰的殼 `home-move start-llm`）、第一次換機 commit（`stack-commit leave`）與要不要 push。

**使用者今天的授權（逐字）**：「可以開工，去吧也可以動活樹」「你也可以先搬家」「zshrc可以動」「停下舊根斷線這件事情，你可以像用剛剛那個tmux一樣就是請他可能隔一段時間做幫你重啟」。push 沒給。刪檔沒給（搬家腳本只 mv、不刪）。`install.py` 今天跑過兩次（上午一次、線 3 後一次，`139d8dd2b`）。

**今天定的（細節都在 `proto8/thinking/2026-11/22/`）**：
- 工作區與 stack（`工作區與stack-1122/`）：cwd 大家都是 `~/repo/aos`；私有地盤 `wf/ws/<agent>/` 照掛的層級嵌套、進 git、任何一層 `temp/` 不進；`_stack` 在 repo 根、根 `.gitignore` 忽略、只在換機時用 `wf/tools/stack-commit leave` 交；llm kernel 各台自己跑（定義 `~/aos-home/llm`、stack `~/aos-home/.llm-stack`），權限站不設；根定義 `wf/tree/root/`；換機說明書 `wf/workflows/dev-env/03-換機.md`。已交：線 1 `b6a3702e2`、2 `15c23d7b5`、3 `139d8dd2b`、4 `7b596847f`、5 `6dff15cdb`、9 `db7d1b9be`、搬家腳本 `88560c0b8`。剩：線 6 搬家（進行中）、線 7 改現行文件（含三處入口連到 03-換機）、線 8 公司那台（使用者「公司現有的樹沒在用，別管」）。
- 使用者：「我必須說這些都只是初步的調查規劃，那實際上我會是一邊用一邊去把它建起來那些都會只是參考…你也可以大膽想」。
- 公司體制（`公司體制-1122/`，`433ab01ad`）：甲～丁四種，規劃員傾向乙（一部門一台子 daemon）；七題沒答。使用者後來說「可以先考慮小工作室」。
- 筆記（`筆記調查-1122/`，`b973b5274`）：`eca-aos-kb` 已寫 `wf/ws/eca-aos/eca-aos-kb/notes.md`（`86a04e2f8`）；五題沒答；使用者要考慮使用者體驗：「vs Code我只是拿來看的」「頂多vs code拿來做一些微小修改」，找 agent 走命令列或對話。
- progress 整理（`progress整理-1122/`，`63e24aaa9`）：42 條分六類、建議關 13 條；使用者：「progress json這塊，一些比較大的段落你可以把它丟到.md，然後用ref指過去」——要做，先查 commit-request `--op`、tabledb、compact_reload 認不認 `$ref`；預設放 `wf/progress/<條目>.md`。
- 輸入成本（`prompt-cost-1122/`，`907ddecc9`）：aos 這邊沒得修；使用者選「做A」。
- Artifact：這個 session 沒有 Artifact 工具；發佈用一般 tmux 的 `artifacts` session（aos 體系外的 claude，cwd `~/.aos/scratch/artifacts-1122/`）。已發：kernel 攔截、權限零件、小工作室筆記、公司體制四頁。

**開著沒答的（不催）**：公司體制七題、筆記五題、輸入成本 B～E、`aos-eca-frontend` 名字與職責、progress 整理裡的等使用者題。

**坑**：
- Claude Code 背景 subagent（Agent 工具）叫不停，我的 session 一停它們就斷；它們起的行程不會自己收。
- 子 agent 不能用 aos 信箱工具，回報都在它最後一則訊息。
- 一句話兩種讀法先標出讀法；語音輸入的錯字照錄並附讀法。
- 乾淨複本要先跑 `install.py`；中文檔名 claim 給真路徑；`ls` 是 `eza` 會卡背景指令。
