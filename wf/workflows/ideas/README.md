# aos 構想：入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜舊構想全在 [archive/](archive/README.md)（2026-09-05），只留脈絡、不再維護。

## aos 是什麼

一個 agent loop（一顆 LLM、一組工具、一個反覆執行的迴圈）可以當成一顆 CPU。aos 是站在這顆 CPU 上面的作業系統。它的記憶體就是檔案系統：一個資料夾就是一支程式，也是這支程式正在跑的樣子。資料夾裡有一個 `.aos/`，那是機器的地盤；裡面有命令腳本，最底下是一次工具呼叫或 LLM 請求。`aos exec` 讓一個資料夾走一步，`aos run` 反覆走到沒有新事可做，daemon 管所有正在走的資料夾。子資料夾預設躺著不動，父資料夾點名才開。時間不進世界的語意，一切以格數算。最先優化可預測性，再看花的錢與人看不看得懂。

## 大綱

| 章 | 這章一句話 | 檔 |
|---|---|---|
| 01 | aos 是什麼、為什麼要有它、拿什麼尺量 | [01-what-and-goals.md](01-what-and-goals.md) |
| 02 | 資料夾是 list，`.aos` 是第一個元素，子資料夾父點名才開 | [02-folders-as-lists.md](02-folders-as-lists.md) |
| 03 | 一塊地看得到哪、怎麼生死、什麼進 git | [03-land-and-life.md](03-land-and-life.md) |
| 04 | `.aos` 裡的命令腳本、原子指令與兩層之間的橋 | [04-inside-aos.md](04-inside-aos.md) |
| 05 | 寫→編譯→執行、接力棒、兩種壽命、什麼叫跑完 | [05-write-compile-run.md](05-write-compile-run.md) |
| 06 | 一格、時鐘、同步借鐘、脫節自走、時間有界 | [06-time-and-clocks.md](06-time-and-clocks.md) |
| 07 | daemon：時鐘總管、REPL 桌子、LLM 管家 | [07-daemon.md](07-daemon.md) |
| 08 | 一個 agent 就是一塊地，逐格走，停不是死 | [08-agent.md](08-agent.md) |
| 09 | 呼叫、交接、開子地與失敗怎麼回來 | [09-call-and-failure.md](09-call-and-failure.md) |
| 10 | 門房：先 tmpfs、再 inotify、真要擋才 FUSE | [10-doorman.md](10-doorman.md) |
| 11 | 工具登記表、模型表述、錯誤封套、通訊錄 | [11-tools-and-contacts.md](11-tools-and-contacts.md) |
| 12 | 指令面、核心分圈、名冊、正本、版面歸屬 | [12-cli-and-layering.md](12-cli-and-layering.md) |
| 13 | 已知的洞、升格傾向、作廢項、先玩清單 | [13-holes-and-play.md](13-holes-and-play.md) |

前五章是空間，06～08 是時間，09～12 是介面，13 收尾。每章末尾有該章逐題的「待決定」表；入口只留總狀態，不重抄細節。

> 使用者的反思與心得（不是構想、不編號）在 [reflections.md](reflections.md)。

## 待決定總表

共 71 條，前綴 A＝01 … M＝13。2026-09-05 已拍板最先的 8 條、A～D 章 18 條與晚上 12 條再審建議；還有 33 條先沿用 spec 的建議預設。逐題原文與理由看各章，正式裁決看 [裁決記錄](../spec/notes/rulings-2026-09-05.md)。

| 章 | 編號 | 已拍板 | 尚待拍板 |
|---|---|---|---|
| [01](01-what-and-goals.md) | A-01～A-04 | A-01～A-04 | — |
| [02](02-folders-as-lists.md) | B-01～B-05 | B-01～B-05 | — |
| [03](03-land-and-life.md) | C-01～C-05 | C-01～C-05 | — |
| [04](04-inside-aos.md) | D-01～D-04 | D-01～D-04 | — |
| [05](05-write-compile-run.md) | E-01～E-06 | E-01、E-04 | E-02、E-03、E-05、E-06 |
| [06](06-time-and-clocks.md) | F-01～F-07 | F-02、F-03、F-04、F-07 | F-01、F-05、F-06 |
| [07](07-daemon.md) | G-01～G-06 | G-01、G-06 | G-02～G-05 |
| [08](08-agent.md) | H-01～H-05 | H-03 | H-01、H-02、H-04、H-05 |
| [09](09-call-and-failure.md) | I-01～I-08 | I-01～I-04、I-07、I-08 | I-05、I-06 |
| [10](10-doorman.md) | J-01～J-06 | J-05 | J-01～J-04、J-06 |
| [11](11-tools-and-contacts.md) | K-01～K-06 | K-02、K-04 | K-01、K-03、K-05、K-06 |
| [12](12-cli-and-layering.md) | L-01～L-06 | L-03 | L-01、L-02、L-04～L-06 |
| [13](13-holes-and-play.md) | M-01～M-03 | M-01 | M-02、M-03 |

M-01 又把 2026-09-04 那批傾向整批升格；H-05 等被其他裁決連帶反轉的細節，照各章與裁決記錄，不在這張「直接回答哪一題」的表重算。

## 第三批：晚上 12 條

| 編號 | 已拍板的再審建議 |
|---|---|
| E-04 | `_comment` 不當程式解讀，但原樣抄進中間表示 |
| F-03 | 加 `--until never`；門鈴收件人改成 daemon |
| F-04 | 工具登記表 `slow` 由登記者自標，第一版就讀 |
| F-07 | LLM 請求不是地，要另查請求狀態 |
| G-06 | LLM 併發由 LLM 世界自己數；daemon 不數 |
| H-03 | 總時限改成格數；token 對自己的 `.aos/usage.json` 判 |
| I-07 | 環境變數預設不繼承；PATH 保底 `/usr/bin:/bin` |
| I-08 | 同格兩筆 `footprint.writes` 相交就整格拒跑、退出 3 |
| J-05 | 脫節回寫可落地，但父每格只在格頭取樣一次 |
| K-02 | 第一版只讀 `slow`，其餘保留、無消費者 |
| K-04 | 退出碼全歸「跑沒跑起來」；可否重試寫封套／狀態檔 |
| L-03 | 這疊完整 spec 與 schemas 就是正本 |

## 怎麼讀

- 規定版在 [../spec/README.md](../spec/README.md)，要寫程式看那邊，這裡只留想法。
- 第一次讀：01 → 02 → 04 → 06 → 08，這五章是骨幹。
- 要寫 spec：全部都讀；09 與 05 是格式空位最多的兩章。
- 只想知道還缺什麼：看 13，再回各章末尾的待決定表。
- 10（門房）、11（工具）相對獨立；12（指令面）給要動手的人。
- 〔裁決〕是使用者拍板；〔傾向〕是使用者說了偏好但未拍板；〔AI 觀察〕是 AI 提議，尚未採用。
