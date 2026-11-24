家機 `main`（家機工作室負責人）的筆記：家機的活狀態與還開著的事，新的寫上面。

← [地盤](README.md)

## 2026-11-24 晚（家機）

- **push 授權**：使用者 11-24 20:1x「晚上十一點統一推」——23:00 推一次 `origin main`，只這一次；鐘 `push-2300` 已登記（clock_register，到時寄進 main 的 queue）。之前的 commit 都等那次。
- **core 兩件**：`.gitignore` 的 .stack／_stack 註解（使用者「做」）；接著 narr-amber-fb-1124 的 listen 擋其他工具等三件（使用者「做，盡量做，反正就是今天晚上十一點push」，22:45 前交件）。→ core 交 `4b17a8341`、`aa8bd9cef`、`bc8938198`、`255d6da30`；kb 跟上 `37a101e9a`、`e7a73061f`；四個位子都睡了。剩真 session 端到端驗（progress narr-amber-fb-1124）。
- kb 第二件（線 home-docs-1124 續）：wf/tree 與 dev-env/03 註「家機掛 daemon-sub、設定同 wf/tree/root」、刪常見錯誤表 `.stack 整個不見了` 那列；`~/aos-home.old-1122` 不動（使用者「好，都如你所說」）。

- **建組織**：使用者「家機這邊你也來建組織吧，學學公司那邊」→ 五題「1.a,2.a,3,a,4.a,5.a」（記在 [wf/org「家機」](../../org/README.md#成員表)）。`main` 加了 `subagent`、`agent_def` 兩支工具；掛了 `eca-aos-kb`、`eca-aos-templates`、`eca-aos-core`（定義 `$AOS_HOME/templates/agents/eca-claude`，各自 `system.txt` 與 `notes_path` 寫在 stack 裡）。templates、core 掛完就 sleep；kb 接家機文件跟上那件。
- **三分在家機已就位**：19:05 整棵樹重起，跑在新路徑；`stack_paths.py` 的 `.bak-trisplit-1124` 五份使用者「可以刪」後刪了；舊範本夾只剩 `__pycache__` 的兩個刪了；push 到 `be448758e`。
- **信**：repo-vc 的 main 兩封都回了 DONE（根的 AOS_LLM_KERNEL；知識庫 source.md 的 .json→.md，`e8439c021`）。
- **文件跟上**：kb 交 `4936939e5`（12 檔）＋筆記 `71e2dd871`，progress `home-stack-move-1124` 刪了。kb 留給 main 的：家機 repo-aos 那列的定義是 `templates/daemons/daemon-sub`（文件寫 `wf/tree/root`，兩者設定相同）；dev-env/03 常見錯誤表「.stack 整個不見了」那列已不適用；不碰清單還列著家機已不在的 `~/aos-home.old-1122`（公司那台可能還在）。三個位子都 sleep 了。
