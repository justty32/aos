# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**，完成即刪（完成的記[日誌](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件）。

## 最新進度

- **open｜重構拆檔＋tidy，之後 fable 領隊整理整個程式碼庫（11-12 晚）**：施工中 → [11-12 日誌](session_logs/2026-11/2026-11-12.md)
- **open｜使用者自己從零搭小樹（一個 daemon＋一隻 opus eca）**：照抄步驟已寫好，等他自己做 → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)
- **open｜搬兩隻 Codex agent 進 aos**：盤點完，等使用者拿真 token 起第一隻（WAIT_USER） → [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md)
- **open｜eca 子 agent 與 skill**：claude 身已施工、codex 身只調查；畫面那條路沒驗、U1／U2 待裁 → [eca-task-subagent](../proto8/thinking/2026-11/12/eca-task-subagent.md)
- **open｜index**：index 裡的路徑已照 json／檔案系統同像從裝著它的資料夾或物件算（`c7cf43613`）；仍未定：同一節點多處有 index 聽誰的、過時、鍵能不能跨層、專屬工具；index-link 代定 L7～L10 待看 → [index](../proto8/thinking/2026-11/12/index.md)、[index-link](../proto8/thinking/2026-11/12/index-link.md)
- **open｜外部 MCP**：兩半都做完；待裁與代定在 WAIT_USER；沒驗的、留題（`--envs` 明文、server 壞了 aos 看不到、常駐 proc）、沒經 Argon 審見 08 → [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md)、[06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)
- **open｜json 工具續行**：aos-json 的 add／ls／search、json_len、複雜組 multi → [json-tools 03](../proto8/thinking/2026-11/12/json-tools/03-multi與複雜組補齊.md)
- **open｜通用 kernel 框架**：圖紙出了、開工等假日（兩處待使用者，WAIT_USER）；只設 `AOS_KERNEL` 仍 `DaemonMissing` → [kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)、[kernel-small-fixes](../proto8/thinking/2026-11/12/kernel-small-fixes.md)
- **open｜wf/ 往 aos 體系走**：使用者先玩，不施工不規劃 → [wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)
- **open｜試驗場**：家機 11-12 晚已照 main `8c4d73d15` 整個重建兩次（第二次含 eca tools_sub、外部 MCP 示範、index 帶 index，實跑過；樹停著），之後 main 的拆檔沒刷進去 → [playground-home](../proto8/thinking/2026-11/12/playground-home.md)；公司那份仍 open（12:45 之後的變更沒刷） → [playground](../proto8/thinking/2026-11/12/playground.md)
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
