結論：普通 exec cpu 接兩支 CLI 的方向成立；「零程式」只涵蓋人工投遞，還不能承諾安全取消、限額與可靠續聊。

已核對提案、規範、程式與指定 help；版本為 Claude 2.1.281／Codex 0.156.1。全程唯讀，未跑模型或碰 LM Studio。

**必修**

1. **as-cpu §3，兩份 inst** → 相對路徑說反了。依 inst-posix/fields §3.1，只有 cwd 相對 inst 家；stdin、stdout、stderr 及後續 $ref 相對「解出的 cwd」。範例會去工作區找 task.md，不同單可能互蓋 out。→ 任務書與輸出填每張單的絕對路徑；argv 不改寫的說明保留。

2. **as-cpu §7，砍完須 boot** → daemon 自己不重拉，但仍活著的 kernel 每格會補 spawn（aos_kernel_engine.py:ensure_cpus）。→ 改成「工作 cpu 通常由 kernel 補回」。取消另有競態：查到 cpu 後，舊單可能完成、cpu 已換跑別單；不能把按 cpu 名 kill 包成可靠的單張 cancel。rm 當下回 Removed，並非等 stopped；寬限內完成也可能正常成功。

3. **as-cpu §6、§9** → --wait-ms 0 是立即逾時，不是不等；找不到 claude 的 127 是 kind=child，不是 aos（aos_kernel_cli.py、cpu/methods）。→ 不等就省略 --wait-ms；修正分類，補收回音後 ack，避免一直留檔。

4. **cost-safety §1、uses §8，池大小與連敗** → 池只限外層同時跑幾張，不限總額度、內部分身或直接另開 CLI。預先放進 kernel 的十張 once，也不會因 aos-cli 連敗自動停；同家也會 busy，不能連 say 十張。→ 區分「手動佇列」與「受控投遞器」，後者逐張放、送前扣配額、暫停後不繼續放；登入來源須明定，不能整包繼承環境就斷言只吃訂閱。

5. **cost-safety §2、others §2，K2／delegate** → 隱藏路徑不是權限；同 UID 可讀 daemon 帳本找 K2，甚至直接叫 CLI。能放任意 inst 就能跑任意指令。→ K2 定位為管理分區；要擋越權，採實際隔離＋受信任投遞入口，固定池、模型、程式、工作區與額度，不收任意 argv／inst。

6. **cost-safety §3～4，牢與 push** →「沒列出的憑證就 push 一定失敗」過滿：工作區的 remote URL、設定、憑證或 socket 仍可能通出去；net=true 還能碰本機服務。整張單可寫也讓 inst／結果被竄改。→ 輸入與控制檔唯讀，輸出另掛；照 agent-access 契約排除 socket、清環境並限網路目的地。

7. **README 拍板 5、cli-facts Codex、cost-safety 預設** → --ignore-user-config 只跳過 CODEX_HOME/config.toml，不等於不讀 AGENTS.md、專案設定或所有客製化；實際預設 argv 還漏了此旗標。→ 專用 CODEX_HOME 要保存登入與 session，並明列允許的設定來源。

8. **cli-facts Claude、cost-safety §4、others §4** → --restricted 仍可被 --tools 加回執行工具，MCP 要另限；--bare 也接受 apiKeyHelper／第三方供應商，非只認一個環境變數。--safe-mode 又會關掉所建議的 skill／MCP。→ 照本機 help 補例外，分開「封閉任務」與「准用 aos 工具」設定；acceptEdits＋prompts none 不保證能跑測試，需核定 Bash 權限。

9. **as-cpu §5～6、README 階 1** → run 先寫 session，之後才回 exec 結果；中間被砍可能出現「kernel 判失敗但 session 已前進」。fork 不會解決，也不會回復檔案。→ 補鎖、持久單號、結果與 session 的提交／恢復規則；取消尚未確認停止前保持 busy，不自動重送。Codex help 另有共享背景 server，須驗證工作確在受管 process group，不能只看 CLI 被砍。

10. **others §3，大腦備援** → stopped 不加失敗計數但下一格照樣重問；加一句「上次中斷」擋不住重複副作用。HTTP 只留四欄又會破壞既有額外欄位透傳契約。→ 有工具副作用的失敗先停待裁決；HTTP 僅移除自訂 aos_brain。此安全行為可能要改 agent，不能承諾只改 aos-llm。

11. **uses §9，試玩員** → 唯讀掛整個 proto5 仍能讀原始碼，也不能直接寫 notes/play。→ 只掛允許閱讀的文件與必要執行資源；報告寫獨立輸出，由牢外收件。

**建議**

1. **cli-facts，Codex 未實測項** → 官方已列 thread.started.thread_id、item.completed 的 agent_message、turn.completed.usage 與 turn.failed。→ 用成功事件判完成，不能撿最後一行當答案；標「官方契約，未實跑」。([非互動文件](https://learn.chatgpt.com/docs/non-interactive-mode))

2. **cli-facts，resume／fork 與網路** → 子命令 help 沒列 -s，不代表只能用 -c；本次以 help 驗過「codex exec -s read-only -C /tmp resume/fork --help」可解析。→ 父層旗標放子命令前，實際套用仍待驗。workspace-write 預設關的是命令網路，可被設定打開；模型連線與搜尋另算，範本應明設網路策略。([安全文件](https://learn.chatgpt.com/docs/agent-approvals-security)) exec 搜尋可用 -c 'web_search="live"'。([設定參考](https://learn.chatgpt.com/docs/config-file/config-reference))

3. **README，300 行／一天** → 七個命令、雙引擎、恢復與取消，估計只夠順利路徑原型。→ 分成基本投遞、可靠 session、取消隔離三段估；假的 CLI 測半行 JSON、提交後崩潰與取消換單。

4. **uses，漏掉的用法** → 可補故障診斷、失敗測試最小重現、交接摘要、規範差異審查。→ 先產報告／patch，附基準 commit 與驗證結果。

**確認沒問題的**

- 不共用 agent 家，以池標籤＋普通 aos-exec 工作接入，符合 cpu §9。
- once 的 Interrupted 原樣交回、不自動重跑；rm 不停正在跑的工作；halt 等在途工作。
- aos-exec 逾時 TERM→兩秒→KILL 砍 process group；自行脫組後代不在保證內。
- 兩個 kernel 可共用 daemon，但所有 cpu 名須避撞，K2 仍須 kernel cpu；缺 llm 池確實被 check 判 bad。
- llm.json 整份驗 endpoint；message 額外欄位保留；proto5-2 仍是草稿。