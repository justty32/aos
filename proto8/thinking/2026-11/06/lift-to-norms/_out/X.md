# X：任務書 1～18 項 NORMS／CONVENTION 落條文回報

舊句保留、未實作標排程；同項多條分列。

| 項／條號 | 檔 | 標記 | 改前 → 加註後一句 | 盤點 id |
|---|---|---|---|---|
| 1／N-01 | [時空][time] | 註／改讀 | 都看 tick → 引推薦原話，內部 tick；對人／外部／Linux proc 牆鐘，待 T1～T6。 | B01、B02 |
| 2／N-03 | [時空][time] | 註／改讀 | kernel 公告回合打包 → 現況 daemon sleep 硬凍；軟凍未做。 | B22、D15 |
| 3／N-65 | [時空][time] | 新條／已定 | 無兩鐘條 → 有鐘比 tick、無則換牆鐘；停鐘不退、跨樹信毫秒、標稱只慢先不補，待 T1～T7。 | B11、B16、B17、B19、B06 |
| 4／N-15 | [鎖][lock] | 改讀／規劃中 | pid／flock 加速 → ③④、收屍、並存段改讀檔案鎖待 T2；引上鎖原話，自動寫鎖待 W。 | C10、C16 |
| 5／N-16 | [投遞][mail] | 註／改讀 | 壞信混述 → 四格「不換」、三層分開；不回限信封壞，body 壞轉 N-66，補解耦原話。 | A113、B30、D04 |
| 6／N-66 | [非同步][async]、[窗目錄][windows] | 新條／現況與已定 | 無呼叫條 → 一箱一函數、stdin JSON、不看 PATH、inst 沙箱特例；stdout／error 回信，進度看 cur 窗，沒回即失敗；aos-serve 與 ctl 壞 body 回信待大重構後、P6 後。 | D03、D04、D05、D06、D14 |
| 7／N-17 | [判活與 stuck][stuck] | 註／已定 | 判活與 stuck 未分 → 三處補 responded_at 比刺激、不改 ping；只標，選填 restart_on_stuck 才由上一層殺整群重起；秒數代定，待 P7。 | C04、L01 |
| 8／N-28 | [daemon][daemon] | 註／改讀 | 未開 sleep／未列 tick → 已開放、add 原話限該例；tick 展 _tick、傳兩變數、近的贏、例外重起待 T7（P6 後）；最近 daemon／setrlimit 已裁。 | A011、A120、B08、B15、B18、B21、B54、C35 |
| 9／N-06 | [名詞表][terms] | 註 | 缺 sleep／wake → 引 11-03 原話、補 sleeping 與 11-05 開放指令。 | A006 |
| 10／N-42 | [LLM kernel][kernel]、[能力包][packs] | 改讀／註 | 可翻案 → 照跑不丟、fixed 衝突／額度錯誤已裁；跨樹 deadline 毫秒、相對 kernel stack 記帳待 T4。 | A093、B17、C36、C37、B66 |
| 11／N-63、性質表 | [hub][hub]、[四性質][env] | 註／改讀 | 未述跨樹／tick → hub 外接、人重設、重寄待 P8；引 JSON 理由，AOS_TICK 非 hub、缺退牆鐘；interval 特許、1000 暫定、近的贏，待 T1／T7。 | D27、B03、B05、B06、B18、B39 |
| 12／NORMS 索引 | [條號表][numbers]、[出處][sources]、[主題][topics]、[入口][norms] | 索引 | 缺新條／本批 → 加新條、各條摘要與批次出處，保留時空頂端。 | 第12項 |
| 13／P-15 | [P-15][p15] | 註 | 定義不被寫 → stack 只指向定義、不主動存副本。 | B56 |
| 13／P-19、P-35 | [P-19][p19]、[P-35][p35] | 改讀 | think 答完退10 → 四格起由 act 答完退10；think 退10 是尾巴沒要答的，非 idle 的10仍由表接住。 | A141 |
| 13／P-23 | [P-23][p23] | 註 | 四題可翻案 → 已定、細節仍代定；寄收信、只走 kernel。 | A092、A095 |
| 13／P-27 | [P-27][p27] | 註 | 格程式放置未明 → 放範本、每隻複製自己改，第三份相同才抽 lib。 | A142 |
| 13／P-41 | [P-41][p41] | 註／已定待實作 | 等信不收代定 → 已定；子動作工具定義先看實作再定稿；補環境脫鉤。 | A094、B49、C07 |
| 13／P-42 | [P-42][p42] | 註 | 操作三樣 → 只管表上 agent；手跑走 post／history；add 不驗身體、首圈報錯。 | A044、A064、A062 |
| 13／P-43 | [P-43][p43] | 註／改讀 | 未述設定／tools 副本 → 工作區設定照吃、風險自負；工具改差異覆蓋層。 | A076、B57 |
| 13／P-43（續） | [P-43 續][p43more] | 註 | 入口掛 daemon 未述 → _entry 可叫 ctl add，aos-exec 不加 --daemon。 | B63 |
| 14／P-44 | [P-44][p44] | 註／改讀 | 舊解析／長旗標 → tool_io 待 J5，env-file＋envs 待 J3＋J6；人用依 Unix、連 C-82；九短名、man、終端確認／yes／No退0三項清單待 S8。 | B50、C09、D33、D35、D37、D38、D39 |
| 15／P-45 | [P-45][p45] | 新條／現況 | 無旗標映射條 → 補充 stdin、巢狀只換一葉、旗標＞stdin＞環境變數、只吃想吃的；J1／J2 已做照實標。 | B43、B44、B45、B46 |
| 16／P-46 | [P-46][p46]、[原草稿][draft] | 新條／升格 | 草稿等定 → 使用者 11-05 夜已定、K8 已做；正文搬入，原位留升格指標。 | C27 |
| 17／二、佈局 | [佈局][layout] | 註／已定待實作 | 範本時鐘未列 → 試驗場／templates／kernel 帶 tick:true，程式預設不帶，待 T7 同 commit。 | B21、D28 |
| 18／CONVENTION 索引 | [入口][convention]、[分檔表][conventionindex] | 索引 | 缺08／09 → 兩處列 P-45／P-46；範圍 P-05～P-46，兼列拆出的 P-15／P-43。 | 第18項 |

跟盤點對不上的：無。A120 原文已引原話，只補 add 範圍；耦合引用照 thinking 完整字句。

沒落的與原因：A141 結束碼三種與 wait.py 退 11 回 think 的未裁衝突，依任務僅回報；其餘 id 均落。H1～H16 其餘未裁草案未升格。

拆了哪些檔：P-15、P-43、P-36 整條搬到同夾新檔，留錨點／指標、同步目錄；P-36 逐字相同。P-43 單條 8695 bytes 不硬切；原超限 N-28／N-16／P-23 直接加。

驗收：指定 nice lint：docs broken=0、thinking broken=3；缺 lift-to-norms/README.md（範圍外），待隊長補後重驗。diff --check 通過、id 與報告連結齊全。僅改授權檔；其他隊伍的工作樹修改保留。未 add／commit／stash／push。

[time]: ../../../../../docs/NORMS/02-設計理念-時空.md
[lock]: ../../../../../docs/NORMS/05-基礎設施-窗/04-N-15.md
[mail]: ../../../../../docs/NORMS/05-基礎設施-窗/05-N-16.md
[async]: ../../../../../docs/NORMS/05-基礎設施-窗/08-N-66.md
[windows]: ../../../../../docs/NORMS/05-基礎設施-窗.md
[stuck]: ../../../../../docs/NORMS/05-基礎設施-窗/06-N-17.md
[daemon]: ../../../../../docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md
[terms]: ../../../../../docs/NORMS/05-基礎設施-窗/01-N-06～N-08.md
[kernel]: ../../../../../docs/NORMS/09-kernel/01-N-42-1-LLM-kernel.md
[packs]: ../../../../../docs/NORMS/09-kernel/02-N-42-1-能力包與份額.md
[hub]: ../../../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/01-N-63-三件事與跟實作對不上的.md
[env]: ../../../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md
[numbers]: ../../../../../docs/NORMS/附錄1-條號表.md
[sources]: ../../../../../docs/NORMS/附錄2-各批出處/06-11-06-lift-to-norms.md
[topics]: ../../../../../docs/NORMS/主題.md
[norms]: ../../../../../docs/NORMS.md
[p15]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/04-五-stack續-P-15.md
[p19]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md
[p35]: ../../../../../docs/CONVENTION/06-巢狀/02-P-35～P-36.md
[p23]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/05-P-23～P-26.md
[p27]: ../../../../../docs/CONVENTION/03-shell版與inst版.md
[p41]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/06-P-41.md
[p42]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/02-P-42.md
[p43]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md
[p43more]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/03-P-43續-11-04-aos-agent.md
[p44]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/07-P-44.md
[p45]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/08-P-45.md
[p46]: ../../../../../docs/CONVENTION/02-題目stack停錯腦/09-P-46.md
[draft]: ../../../../../docs/CONVENTION/05-不管落實待決.md
[layout]: ../../../../../docs/CONVENTION/01-保證佈局入口/01-一-aos-保證的與二-佈局.md
[convention]: ../../../../../docs/CONVENTION.md
[conventionindex]: ../../../../../docs/CONVENTION/02-題目stack停錯腦.md
