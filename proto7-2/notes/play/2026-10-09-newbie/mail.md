# 新手試用：mail（信箱，X1）

← [總表](README.md)｜受測：`proto7-2/modules/mail/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/mail-haiku.md](raw/mail-haiku.md)、[raw/mail-luna.md](raw/mail-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 10 | ≤10 | 是 |
| 對外指令 | 6（日常 send／read／done＋進階 audit／roster／team） | ≤3 | 否 |
| 新概念（兩位取多） | 10 | ≤5 | 否 |
| 分數（兩位取差） | 5.6 | ≥7 | 否 |
| **總判** | **不過**（指令、概念、分數） | | |

跑通情況：兩位都跑通：alice→bob REQUEST、bob 回 DONE、audit 0。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 7 | 9 |
| 容易理解 | 5 | 7 |
| 複雜的藏起來 | 5 | 8 |
| 外層簡單但全面 | 6 | 8 |
| 要背的少 | 5 | 8 |
| 平均 | 5.6 | 8.0 |

## 卡點（新手視角，依嚴重度）

1. `aos7-mail --help`、`send --help` 沒有用法，直接印「請設定 --root 或 AOS_MAIL_ROOT」退出 2（Haiku；組長已複現）
2. 契約卡、已知限制出現 D1、D2、F4、F5、W0、「審查 1–7」等代號，沒定義（Haiku）
3. done 的序號必須來自最近一次 read，否則「請先 read」退出 2，README 沒說為什麼（Haiku）
4. `--up`、ROSTER 從哪來、團隊信箱只收廣播，看不懂（Haiku）
5. README 全文 10.6k 字、是十個包裡最長的；日常三指令之後的進階、復原、契約卡同一頁（兩位都提後半規則多）

## ELI5

這是放在電腦裡的小郵局。寫一句話、指定寄給誰，信就放進對方信箱。對方用 read 看信，做完用 done 歸檔並自動回一封 DONE。最後 audit 查還有沒有沒結案的請求。

## ELI5 之後還複雜嗎

是。**頂層問的「日常 3＋進階 3 算不算仍複雜」：兩位新手都答「是」。** 日常三個（send／read／done）照抄就會，ELI5 講得完；但光日常就要懂 6 種 STATUS 與「done 要先 read」，roster／team 再加 ROSTER、團隊、上游三個詞——新手看到的是六個指令、十個概念。只看日常三個、把進階整段當「之後再說」的話，luna 給 8 分、Haiku 仍給 5.6。

## 回改

狀態：回改隊已改（分支 `loop9/mail`），重試結果見下段「重試」。

- [x] 補 `--help`（沒設 root 也能看用法）
- [x] README 只留日常三指令＋audit；roster／team、復原、契約卡、已知限制移到另一份檔（如 ADVANCED.md）
- [x] D1／F5／W0／審查 1–7 等內部代號從 README 拿掉或換白話
- [x] STATUS 第一次只教 REQUEST／DONE 兩種，其他四種列在進階
- [x] 「done 要先 read」寫一句理由（防止辦結到你沒看過的信）

## 重試

回改隊（mail）2026-10-09，同樣兩位新手（Haiku、gpt-6-luna effort low），同樣任務模板，只准讀 README 與 `--help`；題目＝第一次跑＋自己另寄一封請求辦完。原始回報：`raw/mail-retry<輪>-<試用者>.md`。

| 輪 | 改了什麼 | 指令 | 概念（Haiku／luna） | 分數（Haiku／luna，取差） | 判 |
|---|---|---|---|---|---|
| 1 | `--help` 不需 root；send 省略 STATUS＝REQUEST、done 只給一句話＝DONE；錯誤訊息白話附例；README 只留 send／read／done／audit 與四概念，其餘移 [ADVANCED.md](../../../modules/mail/ADVANCED.md)，內部代號換白話 | 4 | 6／4 | 7.6／9.4 → **7.6** | 不過：指令 4、概念 6 |
| 2 | 第一次跑先 `cd` 到 repo 根；概念編號、信箱併進郵局資料夾；序號理由改白話；列出進階有什麼；不留 `__pycache__` | 4 | 4／4 | 8.2／8.6 → **8.2** | 不過：指令 4 |
| 3 | audit 移進階，日常只剩 send／read／done（第一次跑以 `read alice` 顯示「（沒有新信）」收尾）；補「`<我>`＝自己名字」「export 只在本終端有效」 | 3 | 6／4 | 7.6／8.8 → **7.6** | 分鐘、指令、分數過；概念照「取多」是 6，不過 |

第三輪 Haiku 的 6 個概念是把「請求」「完成」拆成兩個、另算「信箱」與「歸檔」；README 本身只列四個（第二輪同一位數成 4）。Haiku 第三輪剩下的卡點：「已辦結／已歸檔／完成」三種字眼分不清、「中間來新信也不改號」看不懂、`--help` 提到 audit／roster／team 但不能讀 ADVANCED。已用完三輪，未再改；是否以四概念（README 實際列數）判過，交頂層。

