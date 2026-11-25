家機 `main`（家機工作室負責人）的筆記：家機的活狀態與還開著的事，新的寫上面。

← [地盤](README.md)

## 2026-11-25 晚（家機）

- **開場 pull**：公司 51 個 commit（proto9 開了：介面草稿、aos-procfs、aos-daemon、aos-exec）；家機沒推的 core 筆記 commit 跟公司同檔衝突，兩邊都留、rebase 接上。本地比 origin 多那 1 個（加上之後的）；**沒有 push 授權**。
- **proto9 做減法（線 home-proto9-1125）**：使用者「我決定做減法」——procs/<名>/ 底下不規定（ctl、sock 歸之後的 agent 界面）、daemon 當沙箱／container 給底下假的天空、kernel 接特定呼叫。我派兩隻 sonnet 蒐集（程式、報告與前例），實測不用 root 讓天空裡多一支 /usr/bin/draw 接到外面的 kernel 行程；回答與三題（讀法對不對、PID namespace 開不開、先做小實驗、誰做）記在 [daemon當容器-1125](../../../proto8/thinking/2026-11/25/daemon當容器-1125.md)，原話補進 9p-proc-1125 第 30 段；progress `proto9-sky-1125`（等使用者）。只是討論，沒開工、草稿沒動。
- **第二輪（第 31 段）**：使用者定——攔截用第一種；界面＝檔案布局＋格式＋在指定條件下存取得到（權限、限時回應），做得到就是那個東西；不提供界面 daemon 也能粗管；要當 kernel 就跟 daemon 登記、kernel 可疊；天空由起它的 proc 決定。我回：界面是量出來的（`_metainfo` 客觀那半）、卡住收進「不再符合界面」、daemon 手段分兩級；建議三條（提供與選用分開、只能往下傳自己有的、起來時定好記成表）；kernel 疊 kernel 跟「回答只用記憶」衝突→改「只能往下問、不繞圈、帶期限」。四題＋perm-kernel 是哪種，記在同一夾「第二輪」。
- **第三輪（第 32、33 段）**：使用者定 PID namespace 開（「daemon的死活是使用者必須保証的東西，也是他必須承擔的風險」，取代下午「daemon 掛了底下還活著的不管」）；他還在想 daemon 是不是只管權限／帳號切換、資源與排程歸 kernel。我實測 PID ns 1 號死整片收、subuid 100000:65536 加 newuidmap 在、user@1000 的 cgroup 可寫；回：daemon＝唯一碰 Linux 權力的五樣（起收行程、組天空、給身分、起動前上鎖、發開關），kernel＝所有決定（機制與政策分開）；跨權力邊界才疊 daemon。記在同一夾「第三輪」。

## 2026-11-24 晚（家機）

- **聊 aos 的目標（compact 後，模型換 fable）**：使用者口述六層目標（尋址與 index、_entry、_metainfo 與九軸、aos proc 界面、agent、kernel），要我派 opus 帶 sonnet 蒐集後再想。原話照他交代整理進 `wf/user/advice/`（`3cbaa0d34`）。蒐集報告、我的第一輪反饋、原話都在 [aos的目標-1124](../../../proto8/thinking/2026-11/24/aos的目標-1124/README.md)；**三題等他**（proc 界面要不要先寫一頁規格、九軸定不定稿、kernel 要不要拿非 LLM 的資源實測），progress `aos-goals-1124`。他 23:10 睡，回來接著談；這是聊想法，沒派工，別自己開工。
- **第二輪（23:1x）**：使用者「最後兩分鐘，再來一次回答，回答好後記錄下來並push：你覺得未來該怎麼發展？順帶一體_metainfo我確實打算拿他當kernel的判斷標準，並且有所謂客觀主觀的後續發展。」——我答了五步順序與客觀（能不能）／主觀（值不值得），記在同一夾 README「第二輪」；照他說的推了這一次。`_metainfo` 當 kernel 判斷標準是**他說的方向**，五步順序是我的意見、沒定。
- **第三輪（23:1x）**：使用者更正「我是說，在kernel之上」——他問的是 kernel 之上還有什麼，我第二輪答偏成路線順序。重答：kernel 之上是「改結構的那一層」（把 aos 這棵樹當硬體；生長／Aurbis Development Pattern 的位置；耦合度這類只能量的資源歸這層；主觀屬性在這層用），再上是「多個主人之間」（身分、信譽、交換），最頂是人。記在同一夾 README「第三輪」，照同一句「回答好後記錄下來並push」又推了一次。**之後沒有 push 授權。**
- **23:00 那次推已用掉**：使用者改口「那之前推就好」（23:10 前），22:58 推了 `be448758e..3cbaa0d34`（21 個 commit），鐘 `push-2300` 拿掉了。**現在沒有 push 授權**；之後的 commit（thinking 那夾、這份筆記）只在本地，要帶去公司得他再說推。

- **push 授權**（已用掉，見上）：使用者 11-24 20:1x「晚上十一點統一推」——23:00 推一次 `origin main`，只這一次；鐘 `push-2300` 已登記（clock_register，到時寄進 main 的 queue）。之前的 commit 都等那次。
- **core 兩件**：`.gitignore` 的 .stack／_stack 註解（使用者「做」）；接著 narr-amber-fb-1124 的 listen 擋其他工具等三件（使用者「做，盡量做，反正就是今天晚上十一點push」，22:45 前交件）。→ core 交 `4b17a8341`、`aa8bd9cef`、`bc8938198`、`255d6da30`；kb 跟上 `37a101e9a`、`e7a73061f`；四個位子都睡了。剩真 session 端到端驗（progress narr-amber-fb-1124）。
- kb 第二件（線 home-docs-1124 續）：wf/tree 與 dev-env/03 註「家機掛 daemon-sub、設定同 wf/tree/root」、刪常見錯誤表 `.stack 整個不見了` 那列；`~/aos-home.old-1122` 不動（使用者「好，都如你所說」）。

- **建組織**：使用者「家機這邊你也來建組織吧，學學公司那邊」→ 五題「1.a,2.a,3,a,4.a,5.a」（記在 [wf/org「家機」](../../org/README.md#成員表)）。`main` 加了 `subagent`、`agent_def` 兩支工具；掛了 `eca-aos-kb`、`eca-aos-templates`、`eca-aos-core`（定義 `$AOS_HOME/templates/agents/eca-claude`，各自 `system.txt` 與 `notes_path` 寫在 stack 裡）。templates、core 掛完就 sleep；kb 接家機文件跟上那件。
- **三分在家機已就位**：19:05 整棵樹重起，跑在新路徑；`stack_paths.py` 的 `.bak-trisplit-1124` 五份使用者「可以刪」後刪了；舊範本夾只剩 `__pycache__` 的兩個刪了；push 到 `be448758e`。
- **信**：repo-vc 的 main 兩封都回了 DONE（根的 AOS_LLM_KERNEL；知識庫 source.md 的 .json→.md，`e8439c021`）。
- **文件跟上**：kb 交 `4936939e5`（12 檔）＋筆記 `71e2dd871`，progress `home-stack-move-1124` 刪了。kb 留給 main 的：家機 repo-aos 那列的定義是 `templates/daemons/daemon-sub`（文件寫 `wf/tree/root`，兩者設定相同）；dev-env/03 常見錯誤表「.stack 整個不見了」那列已不適用；不碰清單還列著家機已不在的 `~/aos-home.old-1122`（公司那台可能還在）。三個位子都 sleep 了。
