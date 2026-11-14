# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**，完成即刪（完成的記[日誌](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件）。

## 最新進度

- **open｜換樹（已換：`54789088d`，備份 `~/.aos/saves/tree-swap/20261113-225536`；剩換後收尾）**：第一次被擋是因停 daemon 不關 agent 畫面，紀錄在 tree-swap-1113「實際換樹紀錄」；換後收尾清單在手冊與 [tree-swap-1113](../proto8/thinking/2026-11/13/tree-swap-1113.md)；換後要派線接 5 處 Python `--at`（`cmd/aos-agent/aos_agent/tools.py` 已接完〔線at 11-14，CheckPointerAt 綠〕，其餘待接：`directive_value.py`、`py/aos_clock_register.py`、`lib/mcp_server_file.py`、`lib/hook_run.py`），接完再換一次樹（連同 `user_verify`〔`783a9ad60`〕與之後的 lib 改動）；專區段 2 換後步驟（計時器、notify on、door 重建）照手冊；停樹換檔做法 → [aos-teams/06 § 停樹換檔的做法](workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)
- **open｜明天開工：astra 當 kernel 施工、kernel 限資源施工**：astra-kernel-plan（Q1～Q8 全已裁）、kernel-limits-plan（K1～K18 已裁；cgroup 可選、一台 daemon 一個群組）都已規劃完、未施工；另加 kernel 框架批 5、6、10 重做、批 12～14 → [astra-kernel-plan](../proto8/thinking/2026-11/13/astra-kernel-plan.md)、[kernel-limits-plan](../proto8/thinking/2026-11/13/kernel-limits-plan.md)
- **open｜team-model 來源沒同步**：`~/repo/moddings/skyrim/agentctl/docs/team-model.md`（唯讀、不動）與本 repo `workflows/team-model.md` 未同步
- **open｜公司機：W6 清個人設定檔的舊信任紀錄、W8 刪暫存夾**（改前備份、動的是 repo 外的檔；刪前名單先給使用者看，留 `wf-agent-scratch-1113` 與他點名的；`kf2-1113` 不必再留（補丁不用了），刪前仍給使用者看名單） → [收工待裁-回覆落地 § 逐題落地表](../proto8/thinking/2026-11/13/收工待裁-回覆落地.md#逐題落地表)
- **open｜主 session 接 aos**：公司 WSL 的頂層就是樹裡的 `repo-aos`；家機 `~/aos-home` 已搭好（`repo-aos`、舊 MCP 那行已拿掉）；剩：compact 後 `compact_reload.sh` 有沒有跑補驗一次（驗完才補 user/02「compact 前先寫交接」那句） → [main-session-in-aos § 交給頂層的施工清單](../proto8/thinking/2026-11/13/main-session-in-aos.md#交給頂層的施工清單彙總都沒動手)
- **open｜thinking→docs 提取（10-29～11-12）**：W1～W9 都做完進 main（W8 11-13 線辛 `d103cdcd5`、`412680c03`，帶出的條文 vs agent-fsm 20 題已裁、線丑改完）；剩 U2、U3、U5 待裁（WAIT_USER）與 README「沒做的」兩項（B09-34 漏網一列、NORMS 附錄 1 沿革句） → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
- **open｜tidy（11-12 晚三輪做完）**：proto8 沒掃到的四處 11-13 線乙補過了（`1f6422272`、`c38af8866`）；剩 wf 檔照同一條規矩（content-trim「清舊不必逐項先問」三段）再過，與報告第三輪裡三處過時的「還沒改」（C-81、C-42、aos-teams 入口其實 11-13 都改了）；留給使用者裁的在 WAIT_USER → [tidy 報告](workflows/tidy/reports/2026-11-12-收尾.md#第三輪沿革只留結論11-12-晚)
- **open｜使用者自己從零搭小樹（一個 daemon＋一隻 opus eca）**：照抄步驟已寫好，等他自己做 → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)
- **open｜搬兩隻 Codex agent 進 aos**：盤點完；11-13 公司 WSL 的樹上已有 `gpt-price`（codex 身）、`gpt-soap` 在跑（使用者自己加的，13:48 `ctl ls`）——跟盤點那兩隻對不對得上、照抄步驟還要不要留，待核 → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md)
- **open｜eca 子 agent 與 skill**：claude 身已施工、codex 身只調查（U1 11-13 裁「以後再想辦法處理，不急。」）；畫面那條路沒驗、U2 待裁、P-43 要不要補一句 `tools_sub` 只有 claude 身有分沒定 → [eca-task-subagent](../proto8/thinking/2026-11/12/eca-task-subagent.md)
- **open｜index**：`$ref` 與 index 路徑 11-13 晚已同一套規則（`#` 左邊檔案系統、右邊 json 內部，`$at` 已刪）；仍未定：同一節點多處有 index 聽誰的、過時、專屬工具；代定 L2～L12、R1～R7 待看（WAIT_USER） → [index](../proto8/thinking/2026-11/12/index.md)、[index-link](../proto8/thinking/2026-11/12/index-link.md)、[ref-hash](../proto8/thinking/2026-11/12/ref-hash.md)
- **open｜外部 MCP**：接真的別人寫的 stdio server 11-13 做了（官方三台，eca 兩身與 fsm 都叫得到；`disabled_tools` 有效、codex 沙盒管不到 stdio server），它列的三個問題線庚修了（`f225b4754`、`a4ae7d573`、`1b9fcec2b`）；剩：CLI 自己接的 server 起來之後才壞 aos 仍看不到、沒驗三項（claude `except`→`--disallowedTools`、CLI 自己接的一起來就退／中途死掉、經 aos 的 server 卡住不回）、留題 P1（`--envs` 明文）、代定 G3／G4（sync 不比 annotations 那半）待看 → [external-mcp-real-server](../proto8/thinking/2026-11/13/external-mcp-real-server.md)、[fixes-施工結果](../proto8/thinking/2026-11/13/fixes-施工結果.md)、[external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md#沒做沒驗)
- **open｜fsm 真腦跑一晚（假日）**：使用者「fsm真腦跑一整晚...假日再說。」（頂層轉述）；指令在 WAIT_USER 真機驗證那條 → [wait-user/02](wait-user/02-真機驗證.md)
- **open｜四個新想法（11-12 晚）**：`_metainfo`／index、`$ref` 已裁已施工（`$at` 11-13 晚刪）（剩代定待看，WAIT_USER）；kernel 照舊：已細聊出「手／門」、名字都不改，剩嚴到哪、圖紙；linux user：是 aos 眼中能收信的對象、不需要哪台 root daemon 代表、一個帳號一整棵樹（C-64 已照改）、root 小 daemon 先不做、人開的 Claude Code 算樹外還樹內不是問題（結案） → [metainfo-views](../proto8/thinking/2026-11/12/metainfo-views.md)、[ref-index-unify](../proto8/thinking/2026-11/12/ref-index-unify.md)、[kernel-as-bridge 06](../proto8/thinking/2026-11/12/kernel-as-bridge/06-細聊-手與門.md)、[linux-user](../proto8/thinking/2026-11/12/linux-user.md)
- **open｜eca_tidy 產出已抽查（可用，命中約九成）**：十條都收了（第 8 條 `981dc1859`＋`c39fc540a`、範本掛 `jsonx` `2e1e69de2`，11-13）；只剩它的產出還沒做 SUMMARY（產出在家機） → [eca-tidy-review](../proto8/thinking/2026-11/12/eca-tidy-review.md)
- **open｜通用 kernel 框架（11-13 開工）**：進 main 的＝批 1a、2、3、11a、7a、kf-next 三段、批 4（只改原始碼，新 `aos-daemon` 編在 `~/code/kbuild-1113/`、等停樹換）、批 8、9 問腦那包（Python、假腦）、批 5 前半、批 1b（`56a7fe498`，agent 的 `hooks.py` 改用共用引擎）、照規則分流、留著等表態、工具包 `kernel_gate`、`route_ordered`；**沒做**：批 5 接線、批 6、批 10 **11-14 家機重做**（公司補丁不用了，使用者 11-13 23:20 原話：「不，明天我們重做。」）；批 4 新 `aos-daemon` 已於 11-13 22:55 換進活樹（`54789088d`）；7b、11b、12、13、14 可在家用真腦做；留著的：`letters.py` 到 300 行、kernel tests 整夾 18 次裡第一次紅 1 例原因沒查到、骨架三處不順、範本 `max_running` 沒配 `count_daemon`；「只設 `AOS_KERNEL` 仍 `DaemonMissing`」要等新 daemon＋批 5 接線 → [開工紀錄 § 十二](../proto8/thinking/2026-11/13/kernel-framework-開工.md#十二下午接手線己二使用者中午的裁定與停樹)、[§ 十四 還沒做](../proto8/thinking/2026-11/13/kernel-framework-開工.md#還沒做留給之後)、[eca-as-kernel](../proto8/thinking/2026-11/13/eca-as-kernel.md)、圖紙 [kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)
- **open｜wf/ 搬進 aos（wf-into-aos-plan，14 題已裁，段 1、2、3、7 與 code map 已做）**：剩 段 2b SESSION-LOG 轉 json（要挑沒線在跑時）、段 9 收尾；04 段 7 驗收 grep 要補排除 `:!archive` `:!wf/inbox/done`；日索引 13/README 補「段 7 已做」 → [wf-into-aos-plan](../proto8/thinking/2026-11/13/wf-into-aos-plan.md)
- **open｜試驗場**：家機 11-12 21:04 已照 main `415cf6a2c` 第三次整個重建、21:34 起樹開著（五隻含 `eca_tidy`），關機前使用者自己停 → [playground-home](../proto8/thinking/2026-11/12/playground-home.md)；家機 11-13 晚另從零搭 `~/aos-home`（`eca_main`＋`repo-aos`，main `42a5e704c`，驗完停著（`~/aos-saves` 已刪）；`~/code/playground` 原樣留著） → [aos-home-家機](../proto8/thinking/2026-11/13/aos-home-家機.md)；公司 WSL 住 `~/aos-home`（公司遊樂場 11-13 已全刪），樹整天開著：13:48 九列都 running（`_sweeper`、`eca_main`、`ops-agent`、`me-agent`、`repo-aos`、`gpt-price`、`elsa-watch`、`gpt-soap`、`wf-agent`），15:24 停樹重抄過（`lib`／`templates`／`knowledge`／`py`／`kernel` 五夾是 `159414053` 的、`aos-daemon` 換新），15:29 起樹後同樣九列；各 agent 定義七包沒有 `jsonx`、人開的畫面要關掉重開才有時鐘與 a2a → [aos-home](../proto8/thinking/2026-11/13/aos-home.md)、[aos-teams/06](workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)
- **open｜eca 通知改走 a2a（11-13 線壬、線午做完）剩的**：codex 身沒接（照舊貼字）；沒實測：帳號端關掉跨 session 傳訊時、父對子說話的署名（只有單元測試）、確認框等人時訊息擠進來 → [a2a-施工結果 § 沒做的](../proto8/thinking/2026-11/13/a2a-施工結果.md#沒做的)
- **open｜eca_main 來信七項與線庚剩的（11-13 已裁、還沒施工）**：`set-def` 改成「停→拔→同一個 stack 掛回」（fx-1:B）；換定義後照「睡醒」提醒在等的信（em-Q2:B，做完要重抄 lib 才到樹裡）；改名兩步的寫法寫進說明與知識庫（em-Q4，要補查）；知識庫 `aos/kernel.json` 講 `AOS_HOME` 的那句沒跟上（em-Q1 剩的）；沒驗真 codex／真 claude 實跑 → [裁定落地 § 第二輪](../proto8/thinking/2026-11/13/裁定落地-1113.md#第二輪wu-1113-r2裁定後待施工)、[fixes-施工結果 § 要使用者裁的](../proto8/thinking/2026-11/13/fixes-施工結果.md#要使用者裁的)、[eca-main-six-fixes § 要使用者裁的題](../proto8/thinking/2026-11/13/eca-main-six-fixes.md#要使用者裁的題)
- **open｜ops-agent 六點剩的（11-13 線巳、線辰做完五件）**：「eca 跳 yes/no 時由 hook 接住、寄信給特定目標處理」使用者說之後再做（還缺三樣沒定）；索引檢查做成出廠工具等 ops-agent 自己先寫一版；沒驗：子 agent 跑 Bash 時定義的 hook 有沒有被叫、`settings` 給檔路徑的寫法 → [ops-fixes-施工結果 § 之後要做的方向](../proto8/thinking/2026-11/13/ops-fixes-施工結果.md#之後要做的方向今天不做只寫判斷)、[ops-agent-six-suggestions](../proto8/thinking/2026-11/13/ops-agent-six-suggestions.md)
- **open｜repo 的 index**：生成的 `_index.json` 照鐵律 3（`index_gen.py --apply`）；`index_check.py`、`check_anchors.py` 改想跑才跑；剩 `proto8/lib/packs` 與 `templates/agent-fsm` 超過門檻但沒放（WAIT_USER） → [index-build § 維護](../proto8/thinking/2026-11/13/index-build.md#維護)
- **open｜11-13 各線留的「重抄後才驗得了」與沒驗**：工具印的路徑照叫方 stack 算（線寅）三項沒驗——重抄後腦照印的路徑開檔、非 Python 工具、進 `aos-sandbox` 的工具拿不拿得到變數；do_task 摺疊被砍的修正（`4696428dd`）沒在真 daemon 下真的被砍實跑、`StateBad` 沒測試格 → [tool-stack-path § 沒驗的](../proto8/thinking/2026-11/13/tool-stack-path.md#沒驗的)、[line-b-cleanup § 沒做](../proto8/thinking/2026-11/13/line-b-cleanup.md#沒做)
- **open｜11-13 文件裡還沒對齊的幾處（只列、沒改）**：[裁定落地](../proto8/thinking/2026-11/13/裁定落地-1113.md)兩張待施工表落後 git log（kf-next、kf-t1、a2a、ms-1 已做沒標，「未裁 5 題」下午已在對話裡裁完）；開工紀錄第八、十一、十二節與 line-b-cleanup 第 5 題的舊句「未裁／還沒施工」；codebase-cleanup「下次可接的」三項已做沒加註；eca-as-kernel 生效表兩處（「15:08 釘的 commit 不含」線酉的東西——線酉 13:36 前就進 main 了；`kernel_hold` 改的是存檔即生效的 `py/`）；workflows-into-aos 那句「趕不上今天的重抄」過時 → [11-13 日誌](session_logs/2026-11/2026-11-13.md)
- **open｜11-11 線 I／線 C 補驗**：claude haiku 補一輪（new_mail；線 C 撞額度沒問成那輪）；i18n 只記想法 → [mail-notify](../proto8/thinking/2026-11/11/mail-notify.md)、[knowledge-fix 02](../proto8/thinking/2026-11/11/knowledge-fix/02-施工結果與待裁.md)、[i18n](../proto8/thinking/2026-11/11/i18n.md)
- **open｜11-10 總整合最後一輪沒跑完的**（gemma 五項、eca haiku 整項、MCP tools/list 字元數） → [tonight/04](../proto8/thinking/2026-11/10/tonight/04-最後一輪整合驗收.md)
- **open｜two-machines 剩項**：B16、B20、B21 大修，B22 整理階段，B14 留大修（親手驗 T7 在 WAIT_USER） → [next_todo](../proto8/thinking/2026-11/10/two-machines/next_todo.json)
- **open｜大修材料**：四批做完（桌面 `aos-大修材料/`、不進 repo），使用者在 `impl_cpp/` 手寫；問題清單第二三批 56 列待裁 → [11-09 日誌](session_logs/2026-11/2026-11-09.md#2026-11-09)
- **open｜node-pool**：第五輪開工照 03 §7 N2～N5、06 §6 N6～N10 → [node-pool](../proto8/thinking/2026-11/08/node-pool/README.md)
- **open｜special-cases**：剩 K-1（llm kernel 改走 daemon 公開介面）；`_` 保留等撞名 → [apply-ideas 02 § special-cases](../proto8/thinking/2026-11/06/apply-ideas/02-排程.md#11-06-special-cases-排程k-隊)、[special-cases](../proto8/thinking/2026-11/06/special-cases/README.md)
- **open｜apply-ideas 剩項**：序 5 條文日那批文件句子、序 6 aos-serve（沒做）；K-1 見上一行 → [apply-ideas 02](../proto8/thinking/2026-11/06/apply-ideas/02-排程.md)
- **open｜LLM kernel `_metainfo` 第二步**：`llm_tokens` 預估額度、閘門帶 `from` 做按函數統計（沒做） → [10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **暫停｜arcagi**：等 aos 大修完再續，待裁題跟著擱 → [11-09 日誌](session_logs/2026-11/2026-11-09.md)、[11-10 日誌](session_logs/2026-11/2026-11-10.md)
- **凍結｜arknights-kb**（使用者 11-14：凍結到至少 2026-12-14，見 [user](workflows/common/user.md)）：五輪做完後暫停；`~/code/playground-ak5` 不刪 → [27 總結](../proto8/thinking/2026-11/07/arknights-kb/27-第五輪總結簡報.md)、[交棒](../proto8/thinking/2026-11/07/arknights-kb/交棒.md)
- 導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；停在半路的見 [restart](../proto8/thinking/2026-10/11/restart/README.md) §4

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
