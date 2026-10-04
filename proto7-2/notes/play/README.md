# proto7-2 試玩與回歸紀錄

← [proto7-2](../../README.md)

一輪一列。報告與證據（腳本＋精簡 JSON）放同名 `-evidence/`。

| 日期 | 輪 | 報告 | 結果 | 後續 |
|---|---|---|---|---|
| 2026-10-04 | astra-1（第一輪：新設計承諾實測、K 對照、使用者建議落實） | [報告](2026-10-04-astra-1-infra.md) | 既有測試 102／103；500 回合核心不長歷史成立；A2-01～A2-13（A2-01～05 結構性：未知狀態沒傳到底、回合／槽身分證據不足、控制重播不冪等） | 已修（5cf34d7f～fb2fb8e1；測試 219） |
| 2026-10-04 | astra-2（第二輪：A2 回歸、審矩陣、審偏離約定處、人工停點、長跑 50×1000） | [報告](2026-10-04-astra-2-infra.md) | 219 全過；A2 原反例都改善；長跑檔數固定；A3-01～A3-09（A3-01～03 結構性：restart 完成證據隨換 run 消失、environ EACCES 例外可雙開、非一般檔當不存在繞過保護）；矩陣 healthy /proc 12 案有 9 案故障沒命中 | 已修（537ef674～fb5d1b7e；測試 252；A3-02／A3-03 依原則 9 標誤用、已寫的保護留待精簡） |
| 2026-10-04 | astra-3（第三輪：精簡後回歸、六個模組包、step 包、step 對照手寫 Python、until_round 探針、step 長跑 450 回合） | [報告](2026-10-04-astra-3-infra.md) | 272 全過 ×3；A2／A3 精簡後仍成立；G1／G2 已修驗證；A4-01～05 B（加掛讀不到當空值毀 birth、控制包並行同 ID 多起一次、step 初始 wait 無耐性起點、step checker 壞型別拋例外、audit 不更新巢狀登記）、A4-06～08 G（control 去重期限、step 選項／停點名稱、契約卡精簡後過時）；step 與手寫 checkpoint Python 在指定中斷點恢復成本相同；長跑檔數不長 | 已修（[loop4 藍圖](../blueprint-loop4.md)；daf8d5cf 核心 A4-01＋F47＋線頭 1、39681eec step、62e8c46b control／audit、4150733f 契約卡；測試 280；A4-09 X、A4-10 M 不修；G3 未重現、界線已寫） |
| 2026-10-04 | astra-4（第四輪：loop4 修補驗收、F47 後果、§4.4 新保證、G3 壓力、step 450 回合、account 草稿意見） | [報告](2026-10-04-astra-4-infra.md) | 280 全過 ×3；A4-01～08 修好、A4-09 X／A4-10 M 不變；F47 後果合各包契約；§4.4 (a)(b) 成立；**A5-01〔B／subd〕G3 壓力 10／10 重現**：父 kill 後子空間原任務在新子 daemon 下活過兩回合未收；account 草稿 5 條意見 | 已修（loop5：subd 8c2145c4，同探針 10／10，見 [loop5 驗收](2026-10-04-loop5-subd-evidence/summary.md)；budget 包 025d2bfe） |
| 2026-10-04 | astra-5（第五輪：loop5 驗收——subd 回收前代、budget 包、獨立核帳、step 450 回合） | [報告](2026-10-04-astra-5-infra.md) | 322 全過 ×3；A5-01 G3 正式並行 10／10；sibling／同名前綴／無身分程序不誤殺；budget 50 案、35 個真 SIGKILL、獨立核帳 109 快照全過、無重扣無重複效果；**A6-01〔B／subd〕** 合法 stop 記錄提交中斷後重開錯收應保留的任務；**A6-02〔B／budget〕** 後端讀取故障回 1 而非 unknown 的 3；快照目錄已打包（見 evidence 的 SNAPSHOTS.md） | 已修（loop6：subd 95426b17、budget bd9dcc10；另 adapt 包 d3738e04） |
| 2026-10-04 | astra-6（第六輪：loop6 驗收——subd allowed_stop、budget A6-02／§9／§10、adapt 獨立矩陣含 10 ms／2 s 極端流速、step 450＋adapt 320 回合） | [報告](2026-10-04-astra-6-infra.md) | 363 全過 ×3、無 flaky；A6-01 24／24、G3 10／10；A6-02 通過、獨立核帳 127 快照全過；adapt 獨立 29＋9 案過；**A7-01〔B／adapt，低〕** scale 平手取偶數、違 spec「四捨五入」；藍圖 §3.3 門檻例子算錯（實作照公式是對的）；subd 倒鐘後果宜寫進 README | 小修（見下一列 commit） |
