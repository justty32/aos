# proto7-2 第七輪回歸（astra-7）：loop7 驗收

**blueprint-loop7 §7 第 3～6 組驗收大致通過：C8-01／C8-02 中斷重現各 3／3 都已收乾淨（修前 3／3 漏收），K-04 壓力 10／10，budget↔step unknown 交接、過期 intent 三型、加權成本、舊 50 案與獨立核帳都沒有退化；T8-01～08 拿掉注入後 8／8 轉紅。兩條驗收只算「部分」：R8-29 拿不到真的同號 pgid，改用模擬；R8-14 遇到實體寫入失敗時走到另一條保守分支（停在 unknown，不多跑）。新發現 5 條（A9-01～05）：2 B 低、1 G 低、1 X 低、1 M；沒有高嚴重度。** 全套一次 458／458 綠，step 450 回合、adapt 320 回合長跑都正常。

受測 HEAD：`ad1dfa25`（loop7 八條線全進）。之後 main 只多了 I 隊的整合 `461c1f61`／`c7ca3bc8`，只改文件（README、INDEX、problems、契約卡、code map），lib 與測試不變，所以本報告的結論也適用於目前的 main。依[組件契約](../component-contracts.md)、spec、各包 README／spec 分類；[代定清單](../decisions-2026-10-09.md)列的已知限制不當新發現。工人是 4 條 `gpt-6-astra` high（[分工](2026-10-09-astra-7-infra-evidence/handoff.md)），跑在 main 的 worktree 複本；沒有改程式、測試、文件，測試與長跑都包在 systemd scope 裡。隊長親自重跑了 A9-01（3／3 重現），並核對各線原始 JSON。

## 測試與長跑

| 測項 | 結果 | 耗時／範圍 |
|---|---|---|
| 全套一次 | 458／458，rc 0，0 skip | 245 秒；兩個已知負載偶紅案這次都綠 |
| step 長跑 | r1～r450 全關；150／150 完成快照正確，attempt 都是 1，halt／error 0 | 88 秒；job／槽／.aosd 檔名數上限 10／8／9 不長；`resends` 一直是 `{}` |
| adapt 長跑 | 從 r1 跑到 r321；321 份暫存器 ok，22 個檔名逐回合相同 | 36 秒，真 tick／tock |
| daemon 資源 | RSS 21784→21936 KiB，fd 7→5 | step 長跑頭尾比 |
| 長跑後狀態 | nodes.json 沒有殘留 `reaping`；`paused.json={"paused":{"a":["qa"]},"steps":{}}` | N-06 落盤欄正常歸零 |
| 核心行數 | 總行 2952、程式行 2305（astra-6 是 2757／2123）；`test_budget` 照 D7 只印不擋 | 增加最多的是 `aos7_daemon.py` +119 |

證據：[longrun 摘要](2026-10-09-astra-7-infra-evidence/longrun/summary.md)、[suite.json](2026-10-09-astra-7-infra-evidence/longrun/suite.json)、[step.json](2026-10-09-astra-7-infra-evidence/longrun/step.json)、[adapt.json](2026-10-09-astra-7-infra-evidence/longrun/adapt.json)、[core-lines.json](2026-10-09-astra-7-infra-evidence/longrun/core-lines.json)。§7 預估「約 400 項」，實際是 458 項（I 隊的 tests/README 已改成 458）。

## §7 驗收逐條

### 第 3 組：kill／回收時序（[core3 摘要](2026-10-09-astra-7-infra-evidence/core3/summary.md)）

| 條 | 結果 |
|---|---|
| R8-01 runner 停在 Popen 前時 kill | **通過** 3／3：先回 `ok:false`＋unknown，請求留著；放行後下一次 kill 收掉同一個 PID＋starttime 的任務 |
| R8-03 nodes.json 寫失敗 | **通過**：register／unregister 遇 EIO 時注入有命中、回 ok:false、不變更；重送、重起後 status＝磁碟 |
| C8-01 unregister 後殺 daemon | **通過** 中斷 3／3＋對照 3／3：`reaping` 先落盤，重起後收掉舊任務才清掉 |
| C8-02 node 替換後回收中殺 daemon | **通過** 中斷 3／3＋對照 3／3：每案 98～100 次快照都沒有新舊同活。EIO 組：故障期間 missing、不開新回合、舊任務仍活，撤掉故障才收、才開線 |
| K-04 FIFO 晚生子程序 | **通過** 10／10；關掉補掃的負對照確實測出 run 1＋2 同活 |
| R8-29 node 級 pgid 重驗 | **部分**：8 次真 setsid 都沒配到原 pgid 號；改用「記憶體中舊 pgid 指向真外人群組」模擬，外人沒有收到訊號，同 node 對照照常收掉 |
| 作者測試對照 | `test_ctl` 25／25、`test_daemon` 51／51（不算驗收） |

另外挖了 K1／K2 的新邊角：nodes.json 截斷、`reaping` 型別錯（拒絕啟動、不覆寫，X）、重複 unregister／re-register 撞 `reaping`、daemon 連殺兩次、stop --kill 帶 `reaping`（含 EIO）——都安全恢復。只發現 A9-01。

### 第 4 組：budget unknown 與 step 交接（[pack4 摘要](2026-10-09-astra-7-infra-evidence/pack4/summary.md)）

| 條 | 結果 |
|---|---|
| EIO→rc 3＋`unknown_codes:[3]` | **通過**：a2 用同一個 request，`accepted==1`、`resends==1`；故障一直在時，額度用完才 halted unknown |
| 不開 `unknown_codes` | **通過**：halted failed，`resume --resend` 用同一個 request 結算一次 |
| payload EIO／不存在／壞 JSON | **通過**：分別是 rc 3（單行 unknown、stage payload、沒有 traceback）／rc 2／rc 2 |
| 重播回條 EIO | **通過**：rc 3，`--out` 的 SHA-256 前後相同；恢復後只受理一次 |
| 過期 intent receipt／resend／stop | **通過**，三型都核對了 frame 和實跑次數 |
| R8-14 表寫入失敗後 `ran==2` | **部分**：讀表 EIO 時 ran=2、halt unknown、額度沒有重設（通過）；實體寫入 EIO 時 ran=1 就停在 unknown（見 A9-04）。藍圖寫「不得出現 a3」，但 step spec:83 規定 attempt 號照加，所以實跑是 a1、a3，沒有第三次執行——這是藍圖措辭的問題，不是 bug |
| R8-22 縮窗 | **通過**：真 SIGKILL 在 after-intent；跨回合走 unknown，可人工續送；同回合補加，ran=1 |
| 加權成本（D6） | **通過**：used=3、accepted=2、available=7 |
| 舊案／核帳 | **通過**：41＋9 案；獨立核帳 99 份快照、276 筆轉移，5／5 負對照都抓到紅 |
| C8-03 槽外 tmp | **通過**：工作資料夾、results、gateway 各連殺 writer 6 次，死 tmp 剩 0；活 writer 的 tmp 保留 |
| 文件一致 | **通過**：退出碼表三處一致，單位、`unknown_codes`、過期 intent、額度歸 request 都寫了 |

`unknown_codes` 參數驗證 18 組值＋3 種非 run 步都符合契約。

### 第 5 組：數值、遷移、模組（[group5 摘要](2026-10-09-astra-7-infra-evidence/group5/summary.md)）

A8-11＋R8-20、R8-05、N-06、A8-07＋R8-09、N-66 subroot（三層 subd）、N-66 audit＋subd（D9）、N-86、R8-04、R8-06、R8-07、R8-10、R8-11、R8-12、R8-28、R8-17、R8-18（真 subd 連續 50 次恢復，檔案大小 362～363 bytes）、R8-24、R8-25、R8-26：**各一案、全部通過**。R8-05／R8-04／R8-06／R8-07 這幾條精準 I/O 計數邊界，是用產品函式加受控替換驗的，不是全部走 daemon CLI。proto7-1 的 `test_interval_huge_int` 已搬回 `tests/core/test_errors.py:103`，單跑綠。C8-03 由 pack4 驗；R8-30 不排；R8-21 沒有行為可測。[core.json](2026-10-09-astra-7-infra-evidence/group5/core.json)、[modules.json](2026-10-09-astra-7-infra-evidence/group5/modules.json)。

另外挖了邊角：interval 一年上限的前一值／等值／後一值、多欄同時非法、`AOS7_AUDIT_ALLOW` 的空段／相對路徑／node 外路徑（不會誤豁免）、mount readlink 連續 EIO（請求留著，解除後成功，X），都正常。發現 A9-02、A9-03。

### 第 6 組：T8 拿掉注入轉紅

T8-01～08 **8／8 通過**：在 /tmp 的測試副本拿掉注入後都紅，原版都綠；tracked 測試的 SHA-256 前後相同。T8-03／04 的紅是「預期會死的程序沒死、等待逾時」，沒有走到後段的恢復斷言。[t8.json](2026-10-09-astra-7-infra-evidence/group5/t8.json)、各 `T8-*-pair.json`。

### 文件項

spec §2.3（:62）、§2.6（:97）、§4.3（:170）、§5.5（:244）、§6（:252）、契約卡 2.1 都有對應句子。problems.md 的 A8-05～A8-11、C8-01～03 在受測 HEAD `ad1dfa25` 還沒有，I 隊在 `461c1f61` 補上了（loop7 節 A8-05～08、A8-10、A8-11、C8-01～03；A8-09 在上一節）。[docs-edges.json](2026-10-09-astra-7-infra-evidence/group5/docs-edges.json)。

## 新發現

**A9-01〔B／核心 daemon，低〕node 回收還沒確認乾淨時，daemon 重起後 status 顯示 `idle`，沒有保留 `missing`。**
- 契約：[spec §2.6](../../spec.md)「收不乾淨（掃描不完整）保留 missing」。
- 重現：keep 任務 ready → 對該 PID 的 /proc stat 注入 EIO → 替換 node → 確認 missing＋`reaping` 已落盤 → SIGKILL daemon → 同 root 重起並維持 EIO：40／40 個樣本都是 `idle`，`reaping` 還在、舊任務還活、沒有新回合。工人 3／3，隊長重跑 3／3（[可重跑腳本](2026-10-09-astra-7-infra-evidence/core3/new_core3_1.py)，有問題的版本預期 exit 1；[隊長重跑紀錄](2026-10-09-astra-7-infra-evidence/core3/lead-rerun-new-core3-1.log)）。
- 影響：只是狀態誤報，看起來像閒置；實際上仍擋住新回合，撤掉故障後正常回收，沒有新舊同活。這不是「daemon 停機時 node 被換掉」那條已知限制。
- 原因（工人判讀）：`load_state` 只恢復 `reaping`、沒恢復 missing；`check_nodes` 遇到 `reaping` 直接跳過；`write_status` 沒有時間線又不在 missing 時就報 idle（`aos7_daemon.py:142／:516／:639`）。
- 修法一行：從 `reaping` 推出 missing，確認收乾淨才解除。

**A9-02〔G／history 模組，低〕升級後舊編碼檔會混進另一個 node 的新紀錄。**
- 舊版 `a/b` 和 `a+b` 都寫成 `a+b.jsonl`；新版 `a/b` 還是寫 `a+b.jsonl`，`a+b` 改寫 `a%2Bb.jsonl`。實測用舊版寫 `a+b`，再用新版續寫：`a+b.jsonl` 同時有兩個來源的紀錄，而且格式裡沒有來源標記；`a+b` 的新紀錄則分到另一個檔。
- 這是 M 隊代定「舊檔名不變」的延伸。只有 node id 含 `+` 而且跨版升級時才會碰到，所以定為低。
- 修法一行：README 寫明升級時要封存或搬移舊檔；遇到有歧義的舊檔不要自動追加。
- [docs-edges.json](2026-10-09-astra-7-infra-evidence/group5/docs-edges.json) 的 `history-upgrade`。

**A9-03〔B／指示詞解析，低，舊問題〕超長陣列索引（≥4301 位數字）讓 `aos-exec` 漏出 ValueError，回 rc 1＋traceback，而不是 125＋具名錯誤。**
- 原因是 Python 整數字串的 4300 位上限；4300 位時正常回 DirectiveError。`510dd134` 就已如此，不是 loop7 引入的。
- 契約：proto6 inst spec :37／:47、proto5 ref spec :48（`aos_inst.py:3` 引用）。
- 影響：只影響錯誤碼和錯誤格式，不會起子任務。
- 修法一行：轉 int 前先檢查長度，或把 ValueError 轉成 ReferencePointerInvalid。
- [giant-pointer-cli.json](2026-10-09-astra-7-infra-evidence/group5/giant-pointer-cli.json)。

**A9-04〔X／step，低，R8-22 已知限制的延伸〕tasks.json 實體寫入 EIO（在加項前）會留下 intent；下一回合 intent 過期、額度已用完，就停在 unknown，ran=1。**
- 讀表拒寫則是另一條路：撤 pending、重派、ran=2。
- 主案＋另外 3 次都一樣：沒有多跑，`resume --resend` 用同一個 request 完成，總 ran=2。
- 照「不知道就保守停」的原則處理，屬正常；只是瞬時寫入錯誤會比讀表故障更早需要人工介入。
- 修法一行：step spec 把「讀表拒寫→重派」和「實體寫入錯誤→可能留 intent，下回合要人工續送」分開寫；藍圖 R8-14 的「不得出現 a3」順手改成「不得有第三次實跑」。
- [findings.json](2026-10-09-astra-7-infra-evidence/pack4/findings.json)。

**A9-05〔M／step＋budget，誤用〕把 1 或 2 列進 `unknown_codes`，又把不冪等的 append 工作當成冪等，就會重複產生效果。** 這是使用者誤用，不算 bug。可以考慮在 step spec `unknown_codes` 那段加一句「只列真的代表『可能未完成、可同 K 重送』的碼」。證據在 pack4 `results.json` 的 `misuse-code-1／2`。

## 收場

四條線的自建 `/tmp` 根都清掉了，ps 前後核對過沒有殘留程序（各線 `ps-before.txt`／`ps-final.txt`／`cleanup.json`）。worktree 的 tracked 檔零修改。大量快照已封成 tar.gz，單檔都小於 300 KB。

## 最該修的三條

1. **A9-01**：daemon 重起時從 `reaping` 恢復 missing（核心幾行；狀態誤報會讓人以為 node 閒著）。
2. **A9-04＋藍圖措辭**：step spec 把兩種寫表故障的行為寫清楚。
3. **A9-02**：history README 補升級說明。

A9-03 是舊問題，排到下次動 `aos_inst` 時一起修。
