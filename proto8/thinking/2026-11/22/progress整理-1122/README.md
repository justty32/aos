wf/progress.json 的 open 段 42 條逐條歸類：13 條被 11-21、11-22 的工作蓋過或做完、8 組可合併、待答題濃縮成一句加選項、發想表、可派工的小尾巴、暫停名單，外加「邊用邊建」下一步三件事（11-22 線 progress-tidy-1122，只寫報告，沒改 progress、沒刪條目、沒碰活樹）。

# progress.json 整理（11-22）

← [2026-11-22](../README.md)｜同一天：[工作區與 _stack](../工作區與stack-1122/README.md)、[公司體制](../公司體制-1122/README.md)、[筆記調查](../筆記調查-1122/README.md)｜逐條全表：[entries.json](entries.json)

## 使用者原話（11-22，逐字）

> 我必須說這些都只是初步的調查規劃，那實際上我會是一邊用一邊去把它建起來那些都會只是參考那所以不用太擔心啊所以你也可以大膽想啊說說啊對那可以多多想想然後還有什麼要做的嗎我記得我們還累積就不少事情

eca-aos 提議整理 progress.json，使用者答「好可以去」。

## 大白話摘要

- **open 段實際是 42 條**，不是任務書寫的 44 條。
- **13 條可以關掉或改寫。** 主要原因有三個：
  - 11-21 活樹裝了七次新版，很多條「要 install.py 才吃到」的前提已經滿足。
  - 今天的 `_stack` 規劃與線 1～5、9 蓋過了「重建 ~/aos-home」「正規工作區」「stack 遷移」。
  - 有幾條自己就寫著「本條沒有待做」。
- **可以合成 8 組**，最大的兩組：
  - 「編譯與 Python 庫」6 條，都只剩「你親手試」這一步。
  - 「前端大修」4 條加 2 個片段。
- **progress 裡還在等你的題目約 30 題**，另外還有今天公司體制七題、筆記調查四題。每題濃縮成一句加選項，在第 3 節。照規矩，你不在時不追問。
- 「可合併」那類主類只有 7 條，但組成 8 組，因為各組也收了別類條目拆出來的片段。
- **progress 裡缺三樣今天才長出來的東西**：
  - `_stack` 的線 6、7、8 與題 4。
  - 公司體制的七題。
  - 筆記調查的四題。
- 這份只是建議，關哪條、併哪條由你挑。逐條的理由與根據在 [entries.json](entries.json)。

| 類 | 條數 | 條目 |
|---|---|---|
| 1 被蓋過或已完成 | 13 | rebuild-aos-home、later-1115、small-questions、workspace-stack-alloc、design-tails-1113、old-lines-1112、decisions-1118-night、default-stack、aos-vs-c、aos-gdb-1120、aos-hook-iface、aos-home-browse-1120、llm-effort |
| 2 可合併 | 7 | refactor-tidy-inventory、overview-page、eca-rest、home-cleanup、aos-compile、aos-pylib、aos-compile-base |
| 3 等使用者回答 | 8 | norms-text、pages-trial-1116、subuid-1119、aos-base-audit、compact-improve、kb-zh-md-redo、waiting-1121、kb-feedback-1121 |
| 4 大方向發想 | 5 | aos-ns、aos-inherit、aos-init-kernel、aos-kres、shell-metaphor |
| 5 小尾巴可派工 | 4 | codex-trust-company、eca-lab-1118、prompt-cost-cache、kb-md-leftovers |
| 6 暫停或凍結 | 5 | wrapup-1115、arcagi、arknights-kb、aos-htop-1119、agent-fsm-py-folder |

每條只歸一個主類。拆開後的片段會出現在別類的題目或組裡。

## 1. 被蓋過或已完成（13 條）

| 條目 | 建議 | 根據（一句） |
|---|---|---|
| workspace-stack-alloc | 改寫成「_stack 剩的線」 | 11-14 要的正規工作區今天規劃三版、施工線 1～5、9（`780056063`…`db7d1b9be`）；剩線 6、7、8 與題 4，progress 裡沒有任何一條記它們 |
| rebuild-aos-home | 改寫，併組 1 | 決定 D「_stack 取代 ~/aos-home」，~/aos-home 往後只裝 llm，不再照步驟單重建；公司那台走線 8。**對不上的一處**：條目說公司 WSL 現在沒有 aos，今天你說「公司現有的樹沒在用」 |
| later-1115 | 關掉 | 「stack 遷移」被 _stack 整套蓋過；其餘（前端大修、VIEW_* 改名、systemd、全景頁常掛）歸組 2 |
| decisions-1118-night | 改寫成一句 | 這是 11-18 晚裁定的逐字留底，各項已落進別條；只剩「litellm 兩台版本要不要統一」，「家機重建」被線 6 蓋過 |
| default-stack | 關掉 | install.py 11-21 跑過多次，`e8d87d7cd` 在活樹驗過省略 -t／-d；「站在 stack 外要 export AOS_DAEMON」已寫進換機說明書；N-63 加註歸組 4，「stack 裡記定義夾」歸題目 |
| small-questions | 關掉 | ⑥ 已做（`6f09d3f93`）；只剩一個代號「A② gate 設計等使用者開口」，歸組 6 |
| design-tails-1113 | 拆開，大半關掉 | compact_reload：11-15 起多次 compact 都照常讀回，user/02 第 7 行已寫（推測已驗，沒逐次核）；外部 MCP 三項 11-18 已驗；codex 身歸組 5；index 三題在 index_check 整支重寫（`6c769595d`）後要重看；P1 `--envs`、skyrim 同步轉小尾巴 |
| old-lines-1112 | 關掉，剩的想法搬進發想表 | B21 重起退避已做（P12 `0b23509a1`）；B14 你裁留大修＝不做；11-10、11-11 的真模型補驗，對象已被重建與大改換掉；eca_tidy SUMMARY 11-14 已判過時 |
| aos-vs-c | 關掉 | 條目自己寫「本條沒有待做」 |
| aos-gdb-1120 | 關掉，併組 3 | install.py 已跑；`370962554` 在活樹用 `aos-gdb --def-hooks` 列出宣告；剩你親手試 |
| aos-hook-iface | 改寫成兩件 | 活樹換新格式已做（`62129fe49`）；hook_handle.py、hook_flags.py 已刪（`370962554`）；fsm-guard 已改 hookeds（README 第 46 行）。剩兩件：看「替你做的選擇」、gdb 岔路。條文字歸組 4 |
| aos-home-browse-1120 | 改寫，併進 agent-fsm-py-folder | 九個沒人用的檔已刪（`dff53b667`；repo 的 start-api ann 也沒有 .py 了）；宣告格式你 11-21 已審。只剩 start-eca 的 compact_hook 要不要也改成借的 |
| llm-effort | 關掉（請 eca-aos 核一眼） | kernel.json 那幾鍵 11-21 第一次更新已做（`e8d87d7cd`）；ann 格程式已改動態連結（`cf5ad9bf6`）；eca 範本今天加 high（`ca8b4666a`），四隻 eca 直接跑範本 |

## 2. 可以合併（8 組）

| 組 | 收哪幾條（或片段） | 合併後一句 |
|---|---|---|
| 1 換機與搬家剩的 | workspace-stack-alloc、rebuild-aos-home、home-cleanup、decisions-1118-night（家機重建）、aos-init-kernel（重建那半） | 線 6 家機搬家（等你在場）→ 線 7 改文件 → 線 8 公司那台（先答題 4）；退路 `~/aos-home.old-1122/` 與家目錄清理一起等你點頭刪 |
| 2 前端大修 | overview-page、later-1115（前端那半）、refactor-tidy-inventory（拆 aos-frontend）、waiting-1121 第 7 項（盤點 14 項） | 搬家後 `VIEW_TOOLS` 寫死 `~/aos-home/ws/tools` 會更不對；aos-eca-frontend 掛著沒事，名字與職責還沒答 |
| 3 編譯與 Python 庫：等你親手試 | aos-compile、aos-pylib、aos-compile-base、aos-gdb-1120、aos-inherit、aos-ns | 六條的下一步都是「install.py 後親手試」；install 已做，只剩你試；未答的名字題收成一串（第 3 節） |
| 4 條文大修收集點 | norms-text 加上 kb-md-leftovers（N-62、N-69、C-42）、aos-base-audit（N-28）、default-stack（N-63）、aos-hook-iface（C-90、N-45、附錄 4）、aos-compile-base（C-87） | 你說條文以後大修，先把散在六條裡的加註收到一處，大修時一次看 |
| 5 eca 身體 | eca-rest、design-tails-1113（codex 身） | 兩處你都說「先留著」 |
| 6 權限與牆 | subuid-1119、small-questions（A② gate）、waiting-1121 第 4、5、6 項、aos-init-kernel（權限件） | 私有地盤是「未來權限的基礎」，公司體制缺的「牆」就是這組 |
| 7 知識庫回饋 | kb-feedback-1121、kb-md-leftovers（wf 那半）、HANDOFF 的「讓其他模型走一遍知識庫找缺口」 | 方向定了就派 eca-aos-kb |
| 8 格程式整理 | agent-fsm-py-folder、aos-home-browse-1120（compact_hook） | 你說「能跑就別動」，整組暫停 |

## 3. 等你回答的（濃縮成一句；你不在時不追問）

| 出處 | 題目 | 選項 |
|---|---|---|
| _stack 題 4 | 公司那台的 llm kernel 也放那台的 `~/aos-home/llm`？ | a 是（規劃推薦）／b 放別處 |
| decisions-1118-night | litellm 兩台版本要統一嗎？ | a 統一到 1.109.1／b 不統一 |
| norms-text | 條文大修什麼時候開？ | a 搬家與公司體制定了再一起／b 先把組 4 的加註落掉／c 繼續放 |
| pages-trial-1116 | 要正式發佈了嗎？ | a 還不／b 發（拿 noindex、補 LICENSE，要選授權） |
| subuid-1119 | 子帳號要你裝 uidmap，家目錄怎麼開門？ | a chmod o+x ~／b setfacl 給 group（推薦）／c 搬出家目錄 |
| aos-base-audit | N-28 照新行為改？退避參數開成設定？procs_ctl 宣告的列死了照宣告再起？ | 每題 a 是／b 否 |
| compact-improve | 第 3 刀 `history clear-tools`、第 5 刀範例 handler 做不做？ | a 都做／b 只做第 3 刀／c 都不做 |
| kb-zh-md-redo | 你今天說「kb-zn不用管」，是只是不歸 kb 管，還是整件不做了？ | a 留著以後做／b 不做（凍結；刪夾要你點頭） |
| kb-feedback-1121 | 知識庫先改哪個方向？ | a 每頁開頭三到五行重點／b eca 專屬讀法／c 常見故障頁（可複選） |
| aos-hook-iface | gdb 有宣告時，before_run、before_compact 要改成扣住嗎？ | a 改／b 維持 |
| default-stack | stack 裡要另外記定義夾與工作區嗎？daemon 表的 as_written 已經記了 | a 不用另記／b 要 |
| 組 3 | 編譯那一套你試過了嗎？名字題：std 留不留入口頂層、斷點參數名 `id=`／`tool=`、`skip`／`wait_stopped` | 試了說感想／還沒試就照放 |
| 組 2 | `aos-eca-frontend` 要改名成 `eca-aos-frontend` 嗎？要派它做前端大修嗎？ | a 改名並派／b 只派／c 都先不 |
| waiting-1121 | ① API agent 認 /status、/usage、/exit？② 新 index_check 要看嗎？③ block-3、4 醜頁要改嗎？⑧ gpt 包預設走 /v1/responses？self history set 收 -n？ | 每題 a 做／b 不做 |
| waiting-1121 | ④ kernel 攔截 daemon 存取、⑤ 驗寄件人另五題、⑥ 權限零件頁：你還在想、要自己開沙箱 | 不是選擇題，等你開口 |
| shell-metaphor | 比喻三題（另一個 cpu 指什麼、照來源切還是照碰法切、改別人 stack 算正門還是拆機殼） | 見原條 |
| 公司體制 | 七題，至少第 1 題（為什麼分）、第 2 題（甲乙丙丁） | 見 [03-要問的](../公司體制-1122/03-要問的.md) |
| 筆記調查 | 規矩記在人還是地方、誰讓它讀、底下的人怎麼拿、誰能改 | 見 [筆記調查](../筆記調查-1122/README.md) |

## 4. 大方向的發想

「接點」欄是整理員的推測，沒有跟你核過。

| 想法（出處） | 一句話是什麼 | 跟公司體制的接點 | 跟私有地盤的接點 |
|---|---|---|---|
| 編譯（aos-compile 一組） | 用一支 agent.py 寫定義，編譯成定義夾 | 部門裡每個座位的定義可以用同一支 agent.py 編出來 | 地盤規矩第 1 條說地盤放「自己做的定義夾」，agent.py 天生就該住在地盤裡 |
| 命名空間 std 與 `defs.lib`（aos-ns） | 工具包當成庫，用庫名區分 | 公司體制第 5 題 b「部門資產含工具與定義」＝一個部門一個庫 | 庫根可以是 `wf/ws/<部門>/lib` |
| 繼承 `defs.load`（aos-inherit） | 一隻定義從另一隻衍生 | 部門員工繼承部門的底；筆記調查「分給底下的人」是同一件事在執行期的樣子 | 上層地盤放底，下層地盤放自己改的 |
| hook 介面（aos-hook-iface） | 宣告了就能掛，實作各家自己做 | 牆還沒有之前，可以先用 before_tool hook 擋跨部門寫檔 | fsm-guard 的 `write_roots` 設成自己的地盤，就是一道軟牆，今天就做得到 |
| 初始 kernel 可選件（aos-init-kernel） | 最小核心、llm 件、權限件，另有一串可選件（待定） | 部門 daemon 要灌哪些件 | 權限件將來照地盤放行 |
| kernel 資源與排程（aos-kres） | kernel 給資源位置與格式，誰先由各 kernel 自選 | 第 6 題「部門經費」、11-14 部門配額樹 | 沒有 |
| aos 版 htop（aos-htop-1119，暫停） | 看 kernel 的紀錄與分配 | 看各部門用了多少 | 沒有 |
| 子帳號 subuid（subuid-1119） | 一隻 agent 一個 Linux 身分，一台 daemon 一個 group | 公司體制缺的「牆」；11-13「一台 daemon 一個群組」＝部門單位 | 地盤從「約定」變成真的擋得住 |
| kernel 攔截與驗寄件人（waiting-1121 ④⑤） | 誰能寄給誰、寄件人是不是真的 | 第 4 題「近的部門直接寄」、通訊錄 | 沒有 |
| shell 指令比喻（shell-metaphor） | 人在 shell 下 aos 指令算哪一種存取 | 筆記調查「使用者怎麼聯絡特定 agent」那一輪 | 人直接改某隻地盤算正門還是拆機殼 |
| node-pool、apply-ideas、`_metainfo` 的 llm_tokens、i18n（old-lines-1112） | 11-12 前的舊想法 | llm_tokens 預估額度可接部門經費；其餘沒查 | 沒有 |

## 5. 小尾巴：可以直接派工

| 事 | 大小 | 建議模型 | 備註 |
|---|---|---|---|
| 把第 7 節的三樣補進 progress（`_stack` 剩線、公司體制、筆記調查） | 小，10 分鐘 | eca-aos 自己用 `--op`，或 sonnet | 不補的話，下次換 HANDOFF 就會漏 |
| prompt-cost-cache 的兩處文件（self_llm 說明補 reasoning_effort、三份範本的「11 包 40 支」） | 小，15 分鐘 | sonnet | 做完這條可以關 |
| kb-md-leftovers 的 wf 那半（tidy README 第 4 條、wf/public/整理與拆檔.md、proto8/docs 兩處舊路徑） | 小到中，30 分鐘 | opus | 改規矩條文，不派 sonnet；改前改後已寫在規劃夾 19 |
| codex-trust-company | 小，10 分鐘 | sonnet | 要在公司那台做，先備份 |
| eca-lab-1118 試套 patch | 小，5 分鐘試套；要重寫的話中等，1～2 小時 | 試套 sonnet，重寫 opus | 11-18 之後範本大改，大概套不上；也可以直接關，等你追加題目時重寫 |
| team-model 跟 skyrim 同步（design-tails） | 小 | sonnet | 原本「核不到：要家機」，現在就在家機 |
| aos-agent ctl add 的 `--envs` 改成指 env 檔（design-tails P1） | 中 | opus | 要改程式，要再 install.py |
| 月索引 11-22 那列的份數寫 1，日索引有 3 列（這份交了是 4 列） | 極小 | sonnet，用 `month_set` | 照規矩份數要等於日索引列數 |

## 6. 暫停或凍結

wrapup-1115、arcagi、arknights-kb（到 12-14）、aos-htop-1119、agent-fsm-py-folder（加上併進來的 aos-home-browse-1120）。

## 7. progress 裡缺的（今天才長出來的）

- **`_stack` 剩的線**：
  - 線 6 家機搬家（要你在場）。
  - 線 7 改現行文件。
  - 線 8 公司那台。
  - 題 4（見第 3 節）。
- **公司體制**：七題待答，狀態是「發想第一版」。
- **筆記調查**：四題待答；使用者體驗那一輪還沒做。
- **HANDOFF 開著、progress 沒有的**：
  - aos-eca-frontend 的名字與職責。
  - 讓其他模型走一遍知識庫找缺口。

## 8. 照「邊用邊建」，下一步最值得做的三件事（大膽版）

1. **先搬家，開始真的住進 `_stack`。**
   - 線 1～5、9 都交了，只差你在場做線 6。
   - 搬完就能拿真的樹邊用邊修，組 1 的五條也會一次清掉。
   - 搬家那天照說明書改 `.zshrc`，順便驗說明書。
2. **小工作室試營運：三個 subagent 各領一件真工作。**
   - 做法照筆記調查的 A：在它們 `system.txt` 加一句，指到地盤裡的 `notes.md`。
   - 分工：
     - eca-aos-kb 做組 7（知識庫回饋）。
     - eca-aos-templates 做 eca-lab 或 start-eca 的 compact_hook。
     - aos-eca-frontend 做前端大修的第一刀。
   - 試的時候記下哪裡卡、缺什麼。公司體制的第 1、2 題就能用實際感受回答，不用先拍板。
3. **用編譯把「小工作室」寫成程式。**
   - 在 `wf/ws/eca-aos/` 寫一支 agent.py，用 `defs.load` 繼承 eca-claude 範本，把三個 subagent 的職責段寫進去，編譯成各自的定義夾。
   - 今天職責段是手寫在 stack 的 `system.txt`，換機要等 `_stack` commit 才帶得走；改成編譯出來的，就進 repo、會跟著走。
   - 同時也替組 3 的六條做了「親手試」。
   - 順手可以把 fsm-guard 的 `write_roots` 設成各自的地盤，當第一道軟牆。

## 沒做的、沒核的

- 沒改 `wf/progress.json`，沒刪任何條目。沒碰 `~/aos-home`，「活樹已做」都是照 commit 訊息說的，沒去活樹看。
- 「compact_reload 已驗」「llm-effort 活樹已跟上」是從 commit 與文件推的，沒實測。
- 第 4 節「接點」欄是推測。node-pool、apply-ideas 的內容沒查。
