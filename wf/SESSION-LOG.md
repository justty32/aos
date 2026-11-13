# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**，完成即刪（完成的記[日誌](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件）。

## 最新進度

- **open｜主 session 接 aos（明天開始）**：登記檔 11-12 晚已修好（10 支，等使用者重連）；明天接著四件：Skill 放哪、主 session 的身分（連帶 mailbox 能不能掛；使用者已說人開的 Claude Code 若是 claude code eca，其他 proc 面對的就是那隻 eca proc，見 [linux-user § 續：C-64 以今晚為準；人的行程算樹外還是樹內（不是問題）](../proto8/thinking/2026-11/12/linux-user.md#續c-64-以今晚為準人的行程算樹外還是樹內不是問題)）、always-on 規矩怎麼進主 session、`todo` 歸誰 → [wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md#明天主-session-開始現在卡在三點)
- **open｜thinking→docs 提取（10-29～11-12）**：W1～W7、W9 做完進 main；W8 等使用者裁 U1，U1～U6、U8 待裁（U7 已結案；WAIT_USER） → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
- **open｜程式碼庫整理（fable 領隊，11-12 晚）**：批次表各批做完（行為不變）；下次可接：agent-fsm brain／act 逐字相同兩段與四份 `clock_tick` 收成一支、`lib/aos` 找 lib 五種寫法（待裁 9）、兩處文件指舊出處；待裁十題（原第 1 題已結案；WAIT_USER） → [codebase-cleanup](../proto8/thinking/2026-11/12/codebase-cleanup/README.md#做到哪11-12-晚收線)
- **open｜tidy（11-12 晚三輪做完）**：沒掃到的 proto8 說明（`impls/aos-json`、`impls/aos-directive` 整夾、`py/README`、`cmd/docs/03` 各一處舊指向）與 wf 檔之後照同一條規矩（content-trim「清舊不必逐項先問」三段）再過；留給使用者裁的在 WAIT_USER → [tidy 報告](workflows/tidy/reports/2026-11-12-收尾.md#第三輪沿革只留結論11-12-晚)
- **open｜使用者自己從零搭小樹（一個 daemon＋一隻 opus eca）**：照抄步驟已寫好，等他自己做 → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)
- **open｜搬兩隻 Codex agent 進 aos**：盤點完，等使用者拿真 token 起第一隻（WAIT_USER） → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md)
- **open｜eca 子 agent 與 skill**：claude 身已施工、codex 身只調查；畫面那條路沒驗、U1／U2 待裁 → [eca-task-subagent](../proto8/thinking/2026-11/12/eca-task-subagent.md)
- **open｜index**：index 每筆可帶 `index`、檔內 `_index` 可為路徑，相對路徑照 json／檔案系統同像從裝著它的容器算，`#/` 開頭＝本檔根（`$ref` 也收 `#/`，見 ref-hash）；index-link 剩三題使用者裁都維持現狀；仍未定：同一節點多處有 index 聽誰的、過時、專屬工具；代定 L2～L12、R1～R7 待看（WAIT_USER） → [index](../proto8/thinking/2026-11/12/index.md)、[index-link](../proto8/thinking/2026-11/12/index-link.md)、[ref-hash](../proto8/thinking/2026-11/12/ref-hash.md)
- **open｜外部 MCP**：fsm 經 aos 匯入九步與 stdio 路徑統一（Q2）做完；剩：接真的別人寫的 stdio server（使用者「外部MCP，明天再說」；要下載先問）、codex 沙盒對 stdio、`disabled_tools` 沒驗、留題 P1（`--envs` 明文）／P3（server 壞了 aos 看不到）、代定 G3／G4 待看 → [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md#沒做沒驗)、[06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)
- **open｜fsm 真腦跑一晚（假日）**：使用者「fsm真腦跑一整晚...假日再說。」（頂層轉述）；指令在 WAIT_USER 真機驗證那條 → [wait-user/02](wait-user/02-真機驗證.md)
- **open｜四個新想法（11-12 晚）**：`_metainfo`／index、`$ref`／`$at` 已裁已施工（剩代定待看，WAIT_USER）；kernel 照舊：已細聊出「手／門」、名字都不改，剩嚴到哪、圖紙；linux user：是 aos 眼中能收信的對象、不需要哪台 root daemon 代表、一個帳號一整棵樹（C-64 已照改）、root 小 daemon 先不做、人開的 Claude Code 算樹外還樹內不是問題（結案） → [metainfo-views](../proto8/thinking/2026-11/12/metainfo-views.md)、[ref-index-unify](../proto8/thinking/2026-11/12/ref-index-unify.md)、[kernel-as-bridge 06](../proto8/thinking/2026-11/12/kernel-as-bridge/06-細聊-手與門.md)、[linux-user](../proto8/thinking/2026-11/12/linux-user.md)
- **open｜eca_tidy 產出已抽查（可用，命中約九成）**：十條修了九條（1～7、9、10，11-12 晚）；剩第 8 條 `feedback/*.jsonl` 帶家目錄路徑（使用者「明天再說」）與第 1 條留的「範本要不要掛 `jsonx`」一題（WAIT_USER 01）；它的產出還沒做 SUMMARY → [eca-tidy-review](../proto8/thinking/2026-11/12/eca-tidy-review.md)
- **open｜通用 kernel 框架**：圖紙出了、開工等假日（兩處待使用者，WAIT_USER）；只設 `AOS_KERNEL` 仍 `DaemonMissing`；新看法（橋樑）下圖紙不用重畫，見 [kernel-as-bridge](../proto8/thinking/2026-11/12/kernel-as-bridge/README.md) → [kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)、[kernel-small-fixes](../proto8/thinking/2026-11/12/kernel-small-fixes.md)
- **open｜wf/ 往 aos 體系走**：使用者先玩；11-12 晚裁了五點（內容走 json、人當成一個 agent 收信、檢查與 always-on 之後自然做），對標調查已回：必須的都有、沒有硬性缺的，缺的是小輔助（人讀 json、信「回了才消」、人收信通知）；主 session 接 aos 另見上面一行 → [wf-to-aos 調查結論](../proto8/thinking/2026-11/12/wf-to-aos.md#調查結論)
- **open｜試驗場**：家機 11-12 21:04 已照 main `415cf6a2c` 第三次整個重建（fsm 48 含 fake_echo、eca 各 26、子 agent 那台 9；假腦／gemma／haiku 子 agent／codex luna／index_view／`$ref #/` 都實跑過）；21:34 起樹開著（五隻含 `eca_tidy`）；之後 impls 又重 build 過 → [playground-home](../proto8/thinking/2026-11/12/playground-home.md)；公司遊樂場 11-13 已全部刪掉、改住 `~/aos-home`（一隻 opus `eca_main`，repo `~/repo/aos`） → [aos-home](../proto8/thinking/2026-11/13/aos-home.md)
- **open｜線 K 已知問題**：do_task 在摺疊中途被砍、留下的訊息會重複一次 → [fork-and-do-task 02](../proto8/thinking/2026-11/11/fork-and-do-task/02-do_task.md)
- **open｜11-11 線 I／線 C 補驗**：claude haiku 補一輪（new_mail；線 C 撞額度沒問成那輪）；i18n 只記想法 → [mail-notify](../proto8/thinking/2026-11/11/mail-notify.md)、[knowledge-fix 02](../proto8/thinking/2026-11/11/knowledge-fix/02-施工結果與待裁.md)、[i18n](../proto8/thinking/2026-11/11/i18n.md)
- **open｜11-10 總整合最後一輪沒跑完的**（gemma 五項、eca haiku 整項、MCP tools/list 字元數） → [tonight/04](../proto8/thinking/2026-11/10/tonight/04-最後一輪整合驗收.md)
- **open｜two-machines 剩項**：B16、B20、B21 大修，B22 整理階段，B14 留大修（親手驗 T7 在 WAIT_USER） → [next_todo](../proto8/thinking/2026-11/10/two-machines/next_todo.json)
- **open｜大修材料**：四批做完（桌面 `aos-大修材料/`、不進 repo），使用者在 `impl_cpp/` 手寫；問題清單第二三批 56 列待裁 → [11-09 日誌](session_logs/2026-11/2026-11-09.md#2026-11-09)
- **open｜node-pool**：第五輪開工照 03 §7 N2～N5、06 §6 N6～N10 → [node-pool](../proto8/thinking/2026-11/08/node-pool/README.md)
- **open｜special-cases**：剩 K-1（llm kernel 改走 daemon 公開介面）；`_` 保留等撞名 → [apply-ideas 02 § special-cases](../proto8/thinking/2026-11/06/apply-ideas/02-排程.md#11-06-special-cases-排程k-隊)、[special-cases](../proto8/thinking/2026-11/06/special-cases/README.md)
- **open｜apply-ideas 剩項**：序 5 條文日那批文件句子、序 6 aos-serve（沒做）；K-1 見上一行 → [apply-ideas 02](../proto8/thinking/2026-11/06/apply-ideas/02-排程.md)
- **open｜LLM kernel `_metainfo` 第二步**：`llm_tokens` 預估額度、閘門帶 `from` 做按函數統計（沒做） → [10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **暫停｜arcagi**：等 aos 大修完再續，待裁題跟著擱 → [11-09 日誌](session_logs/2026-11/2026-11-09.md)、[11-10 日誌](session_logs/2026-11/2026-11-10.md)
- **暫停｜arknights-kb**：五輪做完後暫停；`~/code/playground-ak5` 不刪 → [27 總結](../proto8/thinking/2026-11/07/arknights-kb/27-第五輪總結簡報.md)、[交棒](../proto8/thinking/2026-11/07/arknights-kb/交棒.md)
- 導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；停在半路的見 [restart](../proto8/thinking/2026-10/11/restart/README.md) §4

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
