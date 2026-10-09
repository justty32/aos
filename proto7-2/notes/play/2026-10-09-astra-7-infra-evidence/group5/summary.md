group5 驗收完成，HEAD=`ad1dfa25`。第 5 組指定案例通過；T8-01～08 原版全綠、移除注入副本全紅。另記 2 項發現：history 升級混檔（G／中，既有代定的延伸）、超長索引例外外洩（B／低，原已存在）。只記不修。

每支 `probe_*.py` 的 docstring 都有 repo 根重跑命令；探針只用 Python 標準庫。所有測試均在指定 systemd scope 內執行，快照收於各 `*-snapshots.tar.gz`。

| 第 5 組驗收 | 結果與證據 |
|---|---|
| A8-11＋R8-20 | 通過：±10**309 用預設、記錯，同 daemon 另一 node 繼續；83ms 修復於 round 4→5 生效。[core.json][core] |
| R8-05 | 通過：真 tick/tock 關回合後，父程序精準注入兩次 EIO，僅開一回合、倒數清空並以原 owner pause。[core.json][core] |
| N-06 | 通過：round 1 已關且 steps=2 落盤後 SIGKILL，重開到 round 3 暫停、同 owner。[core.json][core] |
| A8-07＋R8-09 | 通過：after-symlink 真 SIGKILL，中間快照有 link、無 birth 提交；重送成功，靜態 error 紀錄也能重試。[core.json][core] |
| N-66 subroot | 通過：D2 根為 D1/n1/sub；D1 flock 仍被持有，競爭 daemon rc=1；孫任務無 SUBROOT。[modules.json][modules] |
| N-66 audit＋subd／D9 | 通過：audit→subd→真 daemon，子根 .aosd 寫入紀錄全為 ok:true。[modules.json][modules] |
| N-86 | 通過：once 移項前被殺，推遲 from_round、停用再啟用兩型；同名 keep 確實重用槽，副作用各僅一次。[core.json][core] |
| R8-04 | 通過：LIVE 槽第二次讀 pid.json 注入 EIO，記憶中的 pgid 不變。[core.json][core] |
| R8-06 | 通過：完整 error loop 100 圈、EIO 命中100次、wait 200次；2.018s wall／0.013s CPU。此段將退避上限縮至20ms；另以正式8秒上限驗 n=10**100 不溢位。[error-loop.json][error]、[core.json][core] |
| R8-07 | 通過：300次 fstat EIO，fd 頭尾相同。[core.json][core] |
| R8-10 | 通過：真 aos7-run birth EIO 命中，exit run=37、code=127。[core.json][core] |
| R8-11 | 通過：真任務參數帶 x/aos7-run，仍被辨認為任務並由 tock kill 收掉。[core.json][core] |
| R8-12 | 通過：真 Linux comm 含0xff，程序掃描成功；依 K1 代定用 bytes 解析，保留可辨認身分。[core.json][core] |
| R8-28 | 通過：全形／非ASCII數字與 $at:null 都回具名錯誤；額外長索引問題見下。[core.json][core] |
| R8-17 | 通過：a/b、a+b、a%2Bb、daemon-events 新檔不互蓋；舊檔升級另有缺口。[modules.json][modules] |
| R8-18 | 通過：真 subd 連續50次 SIGKILL，attempt 1→50、prev不巢狀增長、362–363 bytes；實際檔名是 subd-life.json，state=recovering。[modules.json][modules] |
| R8-24 | 通過：registered node 的 symlink 別名被正確納入包住檢查、啟動拒絕。[modules.json][modules] |
| R8-25 | 通過：第一 thread 的 audit hook 停250ms，第二 thread 重疊寫入；兩筆皆記錄。[modules.json][modules] |
| R8-26 | 通過：真 after-birth lost 候選後，同名 keep 真正重用槽；舊 pending 不補回 once。[modules.json][modules] |

R8-05、R8-04、R8-06、R8-07 等精準 I/O／計數邊界使用產品函式與受控替換，並非全部以 daemon CLI 驗證。N-06 未擴張為驗證「回合已關、steps尚未存」的已知窗口；once_retry 提交窗口也不宣稱已消除。C8-03 依分工跳過；R8-30 依要求跳過；R8-21 的 test 欄為「無」，未另設行為案。

| T8 抽驗 | 結果與轉紅原因 |
|---|---|
| T8-01 | 通過：原版0／副本1；未注入時存在正常 exit.json，死亡快照斷言失敗。[pair][t801] |
| T8-02 | 通過：原版0／副本1；拿掉三個 crash marker，step 槽未被殺，等待結束斷言失敗。[pair][t802] |
| T8-03 | 通過：原版0／副本1；拿掉 subd-reaped SIGKILL，預期死亡的包仍活，wait(15) 逾時。[pair][t803] |
| T8-04 | 通過：原版0／副本1；拿掉 ledger crash marker，wait(10) 逾時；後續 subtest 因帳本仍存在再紅。[pair][t804] |
| T8-05 | 通過：原版0／副本1；拿掉第二次讀回注入，Unknown 未拋出。[pair][t805] |
| T8-06 | 通過：原版0／副本1；無 crash 的 tock 已關回合，open:true 斷言失敗。[pair][t806] |
| T8-07 | 通過：原版0／副本1；僅拿掉 runner 那條注入，check_rules 指出該規則0命中。[pair][t807] |
| T8-08 | 通過：原版0／副本1；拿掉 after-birth crash，實測 code=0，與 lost／never_started 快照不符。[pair][t808] |

T8 每組均以 /tmp 的測試副本移除注入，隨後跑原版；原 tracked 測試 SHA256 前後相同。T8-03／04 的負對照屬預期程序未死而逾時轉紅，未將它說成已走到後段恢復斷言。原始完整輸出在同名 `*-red.log`／`*-green.log`。

遷移測試通過：`proto7-1/tests/test_astra5.py:334` 的同名案例位於 `proto7-2/tests/core/test_errors.py:103`；單跑1項、rc=0。[ported-interval.log][ported]

文件抽查證據：[docs-edges.json][docs]。

| 文件項 | 有／無＋位置 |
|---|---|
| spec §2.3 | 有：proto7-2/spec.md:62，unregister 回收意圖落盤 |
| spec §2.6 | 有：proto7-2/spec.md:97，reaping 阻止新時間線 |
| spec §4.3 | 有：proto7-2/spec.md:170，once 改排程不重跑 |
| spec §5.5 | 有：proto7-2/spec.md:244，槽外 tmp 由寫者清 |
| spec §6 | 有：proto7-2/spec.md:252，啟動中 kill unknown 留請求 |
| 契約卡2.1 | 有：proto7-2/notes/component-contracts.md:50 |
| problems A8-05 | 無：未見，HEAD=ad1dfa25 |
| problems A8-06 | 無：未見，HEAD=ad1dfa25 |
| problems A8-07 | 無：未見，HEAD=ad1dfa25 |
| problems A8-08 | 無：未見，HEAD=ad1dfa25 |
| problems A8-09 | 有：proto7-2/notes/problems.md:210 |
| problems A8-10 | 無：未見，HEAD=ad1dfa25 |
| problems A8-11 | 無：未見，HEAD=ad1dfa25 |
| problems C8-01 | 無：未見，HEAD=ad1dfa25 |
| problems C8-02 | 無：未見，HEAD=ad1dfa25 |
| problems C8-03 | 無：未見，HEAD=ad1dfa25 |

文件整體為部分；缺列依任務要求不列 bug。

自由挖：一年上限前一值／等值／後一值，以及多欄同時非法，通過；AUDIT_ALLOW 空段、相對路徑與 node 外路徑不會誤豁免，通過；mount readlink 連續EIO會保留請求，解除後即成功，分類X、不是永久卡住。[core.json][core]、[modules.json][modules]

- **NEW-group5-1｜G／中：history 升級混檔，已知代定的延伸。** 契約：`modules/README.md:28`、`modules/history.py:10`；代定 `notes/decisions-2026-10-09.md:53` 明說舊檔名不變。最小重現：舊版為 a+b 寫一回合，保留輸出與 state，新版續跑 a+b 並新增 a/b；a+b.jsonl 會混入兩個 node，原 a+b 的新紀錄另在 a%2Bb.jsonl。影響是同一來源分檔、不同來源混檔且無來源標籤。建議明訂升級封存／搬移流程，有歧義不得直接追加。使用真舊／新 history writer 重現。[docs-edges.json][docs]
- **NEW-group5-2｜B／低：超長 ASCII 索引逸出 ValueError。** 契約：`proto6/spec/inst.md:37、47`、`proto5/spec/directives/ref.md:48`（proto7-2 的 aos_inst.py:3 引用）。最小重現：inst 的 argv 參照 `#/array/` 加5000個9，array=[0]；真 aos-exec 回1並印 traceback，應是 ReferencePointerInvalid／rc125。4300位正常回具名錯誤，4301位起逸出。影響解析錯誤的退出碼與錯誤格式；未啟動子任務。建議在 int 轉換前檢查長度／範圍或轉譯 ValueError。510dd134 與 HEAD 同樣失敗，非本輪引入。[docs-edges.json][docs]、[error-loop.json][error]

完整分類、契約、重現與修法：[findings.json][findings]。未修改任何既有 tracked 檔，未 commit／push，未呼叫 LLM。自建暫存根均清除、無本線殘留活程序；ps-before／ps-final、逐探針清理紀錄與最終核對在 [cleanup.json][cleanup]。外部啟動器的 `/tmp/astra7-group5-codex.log` 保留未動。

[core]: core.json
[modules]: modules.json
[error]: error-loop.json
[docs]: docs-edges.json
[ported]: ported-interval.log
[findings]: findings.json
[cleanup]: cleanup.json
[t801]: T8-01-pair.json
[t802]: T8-02-pair.json
[t803]: T8-03-pair.json
[t804]: T8-04-pair.json
[t805]: T8-05-pair.json
[t806]: T8-06-pair.json
[t807]: T8-07-pair.json
[t808]: T8-08-pair.json
