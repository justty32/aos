# astra-4：契約一致性與 account 草稿核對

HEAD `b8568cdbf8122b1aaa11b9e67c49228e0e145d2c`。本線只做靜態文件／程式比對，沒有修改受測程式、測試、文件，沒有起受測 daemon 或任務。本線沒有另確認新的 B／G，但主線回報 G3 動態反例，推翻 subd README 第 55 行的收尾承諾，見[壓測證據](../stress/summary.md)；因此不能把靜態核對說成七包完全通過。A4-08 的舊責任與規則已同步；A4-10 已補上誤用界線，不能說成修掉 KeyError。

## 契約核對

要求的 `grep -n 'ctl-seen\|ctl_id\|uid\|G2' proto7-2/notes/component-contracts.md` 是 **0 筆**；退出碼 1 是 grep 無匹配的正常結果，stderr 空。[機器結果](checks.json)與[重跑腳本](check_contracts.py)。

核心卡的保證拆成 **35 組**逐一對 spec：引用的節號都存在，責任與規則對得上；[逐組行號與原文](core-guarantees.json)。涵蓋 daemon、時間線、tick、tock、runner、控制檔、模組、任務、人／外部程式。卡 2.5 的環境傳遞引用 §5.3 較粗，明列環境的地方在 §5.5（spec 第 237 行）；runner 實作第 66 行原樣繼承環境並排除測試用 AOS7_TEST_*，未形成新的責任缺口。

七個包 README 均有契約卡內容及四欄用語，已對照公開入口與主要保證的程式分支；[逐包對照與實際行號](pack-review.json)。control README 第 22～23、47 行已寫明 pending once／目前 birth 的去重期限；subd 第 55～56 行已寫明 1 秒通用寬限與永久移除子空間的前置步驟；once_retry 第 22、33～34 行明確排除漏取樣和槽刪除；diag 第 66 行已同步 F47。step README 第 15 行的全套測試入口已改為預設包含 packs，spec 第 39、83、99 行分別寫清選項覆蓋、timeout 停點及手改缺 pc 的誤用界線。

結果包裝程式用原子 hard link 發布（`aos7_step_result.py` 第 28～45 行），README／spec 仍以 rename 描述原子發布。這是機制文字不精確，完整發布與不覆寫保證仍成立；依「不因理論上可以更穩列 bug」的判準，不新列 B／G。

## account 草稿意見（不算發現）

草稿維持單 node、通用任務包、核心零新增，方向對上 [r6](../../../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md) 第 9～26 行。`reserve→run→settle` 可以接到既有 step 的普通 run／wait 與槽外結果，但目前只是接法構想，還不能稱為介面已定稿或已能直接接上。

**四欄尚未齊全。** [account 草稿](../../../../packs/account/README.md) 的 grant（第 16～20 行）與 ledger（第 22～26 行）都有四欄；gateway（第 28～31 行）缺「前置條件」。至少要交代誰能提交 reserve／settle、請求 id 的作用域、同 id 是否必須同內容，以及核對的 grant／預留與放行對象要如何對上。這沿用 [r1](../../../../../proto7/notes/thinking/2026-10-04-r1-synthesis.md) 第 21、23、57 行對授權與入口的區分，沒有新增隔離方向。

**「明確失敗就退回」過寬。** ledger 第 25 行把 `never_started` 與明確失敗都當成退回理由；但 step `ok:false` 可以是命令已花資源後退出非零，也可能是命令成功但宣告產物沒出現（step spec 第 70 行、結果包裝第 64～77 行）。核心 `never_started` 也是 birth／pid／out.log 的保守跡象（核心 spec 第 233 行；once_retry README 第 22 行承認極小機率跑過），不能代替資源入口的未支用證明。依 r1 第 22～23 行，應由資源入口／效果回條證明沒支用才全退；有支用就結算，未知繼續預留。

**unknown 的處理要前後一致。** gateway 第 30 行要求同 id 拿同一結論，若把「不知道」也永久定住，後來證據補齊便無法自然轉成准／拒；ledger 第 25 行說未知不退，第 37 行卻把有期限自動退回列成待定。下一輪應區分終局回條去重與非終局 unknown，並明定期限能否只是觸發查證／通知；沒有未支用證明時，單憑逾時不能把預留當可再花餘額。這是 r1 第 22 行既有保守邊界。

**接 step 要分清 request 與 attempt。** step spec 第 56 行定義重送保留 request、新增 attempt，而 reserve 與 settle 是兩個動作；如果帳本只用同一 request id 做全域去重，settle 可能被 reserve 擋掉。需定義資源請求的業務 id、操作 id、attempt 與原預留的關係；step 子工作完成只表示命令／產物完成，不等於 settle 回條已落地。帳本及去重證據也應保存在 step close 不會刪掉的槽外位置，對應 r1 第 86 行帳本自己保留歷史、r6 第 20／43 行槽外結果與信箱不是可靠事件保存的界線。可用既有 run 包裝程式銜接，不必先往 step 或核心新增語意。

**grant 還需交代分拆與時鐘語意。** 草稿第 17 行承擔「可不可以再分」，第 19 行卻只承諾看單份 grant 與鐘值，尚無 r1 第 21 行的子不超父、切出的額度不能原地再花；這可以留給下一輪定哪些是純判斷、哪些必須由帳本保存。另草稿的 `[from, until)` 與核心 tasks `until_round` 的停止條件（核心 spec 第 139 行：回合數大於它才不起）端點不同；「同核心」只能比喻新准入，不可直接照抄數值。單 node v1 可用本地回合，但應標出採哪個回合邊界，不把 step 的相對耐性直接當 grant 的絕對效期。

草稿第 11 行把 edit_json 歸到工具包，實際定義在 `lib/aos7_fs.py`；這是可順手校正的依賴名稱，不影響上述分層方向。
