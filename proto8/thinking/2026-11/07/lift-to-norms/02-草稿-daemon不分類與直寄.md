6 份條文草稿：daemon 不分類（B）與 aos-daemon-ctl 永遠直寄落實後，條文還沒跟上的改讀與加註。

← [lift-to-norms](README.md)｜[2026-11-07](../README.md)

# 草稿二：daemon 不分類與直寄的收尾加註

來源：[arknights-kb 07](../arknights-kb/07-停不下與消失.md)、[os-impl 08](../../06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md)。盤點員 B（opus）。規則本身已在 N-28／N-54／N-17／N-63，這裡只補連帶改讀。

> 草稿裡的路徑是「貼進落點檔後」該用的相對路徑，這裡先寫成程式碼樣式、不當連結。新條號（新 N-68、新 C-84）是本夾暫編，貼進條文前再對一次有沒有被別條線先用掉。

### B13
- 主題：收工時還在跑的一次性程式，開門時會從頭再跑一次
- 類別：已裁（B 的下表規則，選項框「失敗留表，照 opus 選的」；原句「daemon 收工時還活著的留 `sleeping`、下次開門自動叫醒（一次性程式會重跑一次）」）
- 落點：N-28「收工時 sleep、開門時 wake」那條的 11-07 B 註（第 41 行）後面加一句
- 草稿文字：
  > 一次性程式（沒讀 ctl、沒自己的 state 的那種）收工時還在跑，也一樣留 `sleeping`；開門 wake＝照列上記的入口與參數從頭再跑一次，不是接著跑。有副作用、不能重做的一次性工作，要寫的人自己讓它做得起兩次，或收工前先 rm。（11-07 使用者裁定，出處 proto8/thinking/2026-11/07/arknights-kb/07-停不下與消失.md）
- 出處原話：「下表規則選項框選『失敗留表，照 opus 選的』」；規則原句「daemon 收工時還活著的留 `sleeping`、下次開門自動叫醒（一次性程式會重跑一次）」
- 衝突：跟 N-28「子項結束後不自動重起」不衝突，這條本來就只管 daemon 開著的時候；daemon 重開＝重新開始（使用者 10-22）。跟 C-17 的關係見 B14。後半句「要寫的人自己讓它做得起兩次」是我推出來的後果，隊長嫌多可以只留前半句

### B14
- 主題：C-17 硬凍的改讀「loop 型收 SIGTERM」改成任何活著的 proc
- 類別：已裁（B）
- 落點：`proto8/docs/CONCEPTS/02-設計理念-時空.md` C-17 的 11-06 改讀（第 12 行）後加註
- 草稿文字：
  > **11-07 註**：上句「loop 型收 SIGTERM」照 daemon 不分類改讀成「收工時所有還活著的 proc 都收 SIGTERM、留 sleeping、開門再起」；一次性程式沒有自己的 state 可接，醒來＝從頭再跑（見 N-28 收工那條）。（11-07 使用者裁定，出處 proto8/thinking/2026-11/07/arknights-kb/07-停不下與消失.md）
- 出處原話：選 **B：daemon 不分類**；「daemon 收工時還活著的留 `sleeping`、下次開門自動叫醒」
- 衝突：C-17 第 12 行「現在只有硬凍——loop 型收 SIGTERM」照字面只講 loop 型，B 之後範圍變成全部；改讀就好，原句留著

### B15
- 主題：C-52 例外「讀法」的例句還寫「daemon 的 loop 型」
- 類別：已裁（B）
- 落點：`proto8/docs/CONCEPTS/01-設計理念/03-續-C-52-例外.md` 第 13 行「讀法：不認身份、可認公開介面」例句後加註
- 草稿文字：
  > **11-07 註**：例句的「daemon 的 loop 型」照 daemon 不分類改讀成「daemon 對任何列」：stop 寫的是那列的公開 ctl（小格父寫的 loop 設定有 `ctl` 就照它、否則 `ctl.json`），daemon 不翻身體的 loop 設定判型。使用者原話：「argv:[aos-loop loop.json]，我用aos-exec執行，這等同於我變成了aos-loop……在變成loop之前，我確實就是一次性程式沒錯」。（11-07 使用者裁定，出處 proto8/thinking/2026-11/07/arknights-kb/07-停不下與消失.md）
- 出處原話：同上，加「選 B：daemon 不分類」
- 衝突：例句照字面變窄、沒錯；改讀就好。「daemon 去翻 loop.json＝上層認得下層（C-52）」是隊長寫的理由、不是使用者原話，所以草稿不寫成「使用者依 C-52 定的」

### B16
- 主題：板子比喻加一行：aos-daemon-ctl＝直接敲板子，aos-agent＝經作業系統（判官）
- 類別：已裁（選項框「aos-daemon-ctl 永遠直寄」，比喻出自使用者選的那個選項的說明原文）
- 落點：`proto8/docs/CONCEPTS/附錄1-續-板子比喻.md` 清單末尾加一行
- 草稿文字：
  > - aos-daemon-ctl＝人直接敲板子（不看 `AOS_KERNEL`、一律直寄 daemon 的 ctl 信箱）；aos-agent＝經作業系統（判官）。判官睡著是設計系統的人要管的風險，手動 `aos-daemon-ctl wake 名字`。對應 C-83「使用者保底」；規則見 N-63 實例 `AOS_KERNEL` 的 11-07 註。（11-07 使用者裁定，出處 proto8/thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md）
- 出處原話：選項說明「分工變清楚：aos-agent＝經作業系統（判官），aos-daemon-ctl＝人直接敲板子，不管 AOS_KERNEL。」；使用者補「判官睡着，這是使用者在設計系統時要承擔與管理的風險。」
- 衝突：無。這張表本來就收 daemon-board 的逐詞比喻；要不要加由隊長決定（規則本身已在 N-63）

### B17
- 主題：C-47 0 號式「唯一能對 daemon 下 ctl」、N-42 (2) 規劃「stop、rm、sleep 也要過判官」跟「aos-daemon-ctl 永遠直寄」的關係
- 類別：已裁（同 B10），這裡只加註說明關係
- 落點：`proto8/docs/CONCEPTS/04-kernel.md` C-47 的 11-05 加嚴（第 16 行）後加註；`proto8/docs/NORMS/09-kernel.md` 第 9 行規劃中那句後加同義一句
- 草稿文字（C-47）：
  > **11-07 註**：aos-daemon-ctl 永遠直寄 daemon 的 ctl 信箱，是人直接敲板子的保底手把（C-83），不是第二個 kernel；0 號式的「唯一」照上句仍靠 Linux 權限＋約定——寄不進 daemon 信箱的人（例：沙箱裡只拿到判官信箱的）用 aos-daemon-ctl 也寄不進。要判官管的走 aos-agent。（11-07 使用者裁定，出處 proto8/thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md）
- 草稿文字（N-42 (2)）：
  > **11-07 註**：「要過判官」指的是經 `AOS_KERNEL` 的路（aos-agent）；aos-daemon-ctl 11-07 起不看 `AOS_KERNEL`、一律直寄，能不能直寄 daemon 信箱照舊靠 Linux 權限（N-63 實例 `AOS_KERNEL` 的 11-07 註）。（11-07 使用者裁定，出處 proto8/thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md）
- 出處原話：選項框選「aos-daemon-ctl 永遠直寄」；說明原文「aos-daemon-ctl＝人直接敲板子，不管 AOS_KERNEL」「也對應 C-83『人是最後保底』」
- 衝突：表面上，C-47「唯一能對 daemon 下 ctl 的 kernel proc」、N-42 (2)「daemon 成了權限閘門」看起來被一支永遠繞過判官的指令打破。改讀：C-47 自己寫了「唯一靠 Linux 權限＋約定、程式不驗身分…繞過＝使用者自擔」，所以不算字面衝突，加註講清楚就好（見打架題 1）

### B18
- 主題：條號表 N-28／N-54 列沒提 11-07 B
- 類別：導航（跟著 B，不是新規則）
- 落點：`proto8/docs/NORMS/附錄1-條號表.md` 第 27 行（N-28）、第 51 行（N-54）的括號尾
- 草稿文字：
  > N-28 尾加：「；11-07 使用者裁定 B：daemon 不分類——退 0 下表、非 0 留 stopped＋reason、收工全睡下、不認 aos-loop 陣列」
  > N-54 尾加：「；11-07 使用者裁定 B：任何 proc 可 stop／start／sleep／wake，翻『exec 型只有跑和拔』」
- 出處原話：同 B01
- 衝突：無。純索引，隊長可以併進統一編號那一輪
