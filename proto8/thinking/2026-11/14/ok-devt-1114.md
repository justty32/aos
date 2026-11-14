# ok-devt（11-14）：daemon 給 agent 的「身分」與「事件」模型——設計過 Argon 一輪已定稿；ok-limits 三條小修已審（nofile 已同意先交，B7 要改名 cause，who 再加 parent）；第 1 期交 ok-limits 施工

← [11-14 日索引](README.md)｜材料夾 [ok-devt-1114/](ok-devt-1114/)｜任務書 `wf/temp/ok-devt/任務書.md`｜部長 head-core

## 這條線做什麼

使用者 11-14 專區回信開的線（wf/advices「daemon與行程」三條）。頂層分工：三條小修由 ok-limits 做；這條線設計整套模型並審那三條。不寫碼。

## 結論（定稿，細節在 05）

- 三件事分開、互不推導：`AOS_KERNEL`＝控制請求往哪送；`parent`＝誰要求掛了我；`notify_box`＝回報寄到哪。
- `parent`：發 add 請求那一隻的根 stack 絕對路徑，組 add 信時自動填。`notify_box`：明給才有，只有 subagent add 保留現在的預設。兩格是登記、不是證明。
- parent 鏈不存，要看就拿 parent 再查一次 who；不做查整條鏈的指令。
- hook 事件的共同欄維持 event、hook、stack。`reason` 一律是給人看的句子；「為什麼結束」的代號叫 `cause`，九個值照 ok-limits B7。
- 分兩期，兩期都查得到別隻：第 1 期只動 Python（值放啟動單子的 envs）；第 2 期搬到 daemon 表的列上，等換樹。

## 檔

| 檔 | 內容 |
|---|---|
| [01-現況](ok-devt-1114/01-現況.md) | 蒐集摘要：身分與事件的現況事實、別線已定的規則 |
| [02-設計](ok-devt-1114/02-設計.md) | 初稿（送 Argon 前；跟 05 不同處以 05 為準） |
| [03-Argon原文](ok-devt-1114/03-Argon原文.md) | Argon 審查原文 |
| [04-採納表](ok-devt-1114/04-採納表.md) | 逐條採納與理由 |
| [05-定稿](ok-devt-1114/05-定稿.md) | 定稿：欄位名以這份為準；第三節是施工清單，第四節是審 ok-limits 的結果 |

## 經過

- 13:13 開工。必讀、開工核對（沒起任何 daemon）。
- 13:15 收到 ok-limits 三條的進度、diff、欄位名。
- 13:22 起分層：回報改寄 head-core。
- 13:27 正式同意 ok-limits「nofile 不收別名」，那件拆出去先交。
- 13:32 兩隻 sol（ok-devt-sol-1、-2）19 分鐘沒有產出，改派 claude Explore 蒐集。
- 13:47 把 B7 命名的初步傾向寄 ok-limits（欄位名傾向 `cause`、值不動）。
- 13:4x 設計稿寫好，送 Argon；兩隻 sol 收掉（subagent rm）。
- 13:5x Argon 回 7 點問題、5 題、4 個提案；寫採納表、定稿。正式審查意見寄 ok-limits，對齊信寄 ok-sec、ok-board。

- 13:59 頂層看過定稿，同意第 1 期交 ok-limits；head-core 放行六個紀錄檔 commit。ok-board 回：它的 own_root() 確實漏了 hooks/<名>，批 2 補；「為什麼算 gone」的欄照用字規則改叫 gone_cause。ok-limits 回：rm 該蓋過 sleep、envs 落在表上那列的 launch.exec.envs、沒有不同意；who 已照 1.3／1.4 改完待審。

- 14:12 ok-limits 實測查核 A：帶 envs 的 add 跟不帶的不等價（exec 欄變 null 致 set-def 拒收、as_written.exec 不記、--path-json 指示詞被改寫、多一層 aos-exec）；另更正：envs 不在表上的 launch.exec.envs，在小格檔裡，launch.exec 是指標。定稿 1.3 改成「第 1 期不改任何一個 add 走哪條路，只有本來就帶 envs 的才記 parent」，who 改成順著指標讀。

## 還沒做

- 審 ok-limits 的 diff（who 已到；add_letter、B7 改名還沒到）。
- ok-sec 還沒回（notify_box 跨 uid 的規則）。
- 第 2 期（daemon C++）排進哪一次換樹；adopt.cpp 排在 ok-limits B7、ok-sec 1d 之後。
- 投 wf/advices：brain_failed 兩種身不一致等蒐集時看到的不一致。
