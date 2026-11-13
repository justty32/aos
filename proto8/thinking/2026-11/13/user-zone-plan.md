# 使用者專區（線人 11-13 晚規劃；線專同晚施工段 1＋網頁）：專區放 `~/.aos/user/`、它本身就是你的 stack，agent 把要你裁／驗／做／知道的事寄進它的 `mailbox/`，你用 `aos-user` 列、看、回，回了才消；桌面網頁 8766 只綁本機；手機先不做

← [11-13 日索引](README.md)｜分檔夾 [user-zone-plan/](user-zone-plan/README.md)｜相關：[agents-feedback-1113-題目](agents-feedback-1113-題目.md) 裁-5、裁-2、T08／T09；[12/wf-to-aos/02](../12/wf-to-aos/02-寄信給人與主session.md)；[12/linux-user](../12/linux-user.md)

> 流程照使用者 11-13 晚定的：opus 帶隊（線人）→ 四隻 sonnet 唯讀搜集 → opus 匯總成備料 → fable 只讀備料做設計 → opus 細化對到檔案 → **到此停**。沒起 aos 行程、沒寄信、沒寫 `~/.aos`、`~/aos-home`。

## 使用者原話（逐字）

- 今晚：「好，規劃好了來聊聊...啊不對，可以先去規劃我這個使用者的專區，寄信寄到我那裏的」
- 今晚補：「還有順便連同網頁一起規劃」「專區放哪都可，~/aos-home/user, ~/.aos/user, ...」「~/.aos也可以」
- 裁-5：「目前是我會挑一個agent(通常是eca_main)，跟他說，由他作爲中轉和中央保管者，後面會弄一個~/.aos/user/，讓大家寄信到那邊，然後可能弄個aos agent搭配網頁和通知，讓我去做決策。共通的東西，那就是要找個共通的地方放，或許可以用~/aos-home/ws/public，」
- 裁-2：「信件格式是json，好處是多的key，程式可以忽略。所以我們的aos-post和相關工具不用改。……更好的方法是弄個新工具或新程式。這麼多agent抱怨，我們可以做一套通用新程式，放在~/aos-home/ws/tools，大家一起用。」；「如果有agent不堪其擾……可以設兩層hook……第二層就是看這封信是否是重要的(有無特定key之類)」；「agent是否可以在自己的門上貼個公告……信件種類這塊，agent還可以指定用哪種工具，或指定某種格式(json schema)。」
- 今晚定的流程：「先派opus帶隊，指揮sonnet搜集訊息，然後opus整理匯總，交給fable規劃與設計架構，然後opus深化細化架構，最後再來實作。」
- 更早：11-12 D4「把人類這個linux user作爲agent，寄信過去就是了」；「user是哪個proc...對，就是aos眼中一個能收信的對象。」「一個帳號一整棵樹。」

## 使用者裁定（11-13 晚）

原話（逐字）：「照推薦，第12題就放ws/tools。舊的信箱沒在用，刪掉。先不考慮手機。push/刪檔這塊也算。網頁和看板...先做網頁就好。就先只考慮家裏這臺。」

- 照推薦：U1（`~/.aos/user/`）、U5（驗過的專區回信＝你本人的話）、U7、U8（先不要專區 agent）、U11（段 2 做完才讓位）。
- 不照推薦：U2 舊信箱**刪掉**（已刪，原本只剩空骨架）；U6 push、刪檔**也算**；U9 **先只做專區網頁**、不碰看板；U10 **只做家機**；U12 程式**放 `~/aos-home/ws/tools/aos-user/`**、不在 repo、不進 git；U3、U4 手機先不考慮。
- 施工（線專）：段 1 與網頁做完，用法 `~/aos-home/ws/tools/aos-user/aos-user ls|show|answer|reply|ok|door|serve`；鐵律 2 已加一句。「驗過」＝`aos-user verify`（寄件人是專區、跟 `done/` 副本逐欄一樣、流水帳有同一筆）；同一個 Linux 帳號下擋不住會開 shell 刻意造假的 agent。
- 逐題結果、施工紀錄、代定、沒做的、試驗紀錄 T1～T7：[07 使用者裁定與施工](user-zone-plan/07-使用者裁定與施工.md)。

## 一句話設計

人在 aos 眼裡本來就是「一個能收信的對象」（11-12）。專區就是把這個對象做完整：一個帳號一個專區 `~/.aos/user/`，裡面的 `mailbox/` 是標準 aos 信箱（底層不改），信的額外 key（`kind`、題目、選項、推薦、期限、急不急）放 body；`aos-user` 這支新程式負責寄前驗格式、列、看、回、搬存檔；網頁、通知、手機都只是同一份資料的另一張臉。

## 專區長這樣

```
~/.aos/user/                 你的 stack＝專區（AOS_LINUX_USER_STACK 指這裡）
├── mailbox/                 ★ agent 只准寄這裡（tmp/ new/ cur/；new＝沒看、cur＝看過沒回）
├── done/2026-11/<信名>/     回完的：原信＋你的回信副本
├── rejected/<信名>/          不合門上公告的信（留著、已退信）
├── drafts/<信名>.json        答到一半
├── door.json                 門上公告：收哪五種信、題目必帶選項＋推薦、急件規則、出門模式
├── schema/letter.json        信的 JSON schema
├── config.json               通知、安靜時段、網頁埠
├── web/token                 網頁送出用的記號
├── keys/                     （段 5）簽名金鑰
└── log.jsonl                 流水帳
配套：~/aos-home/ws/public/user.json（名片）、~/aos-home/ws/tools/aos-user（連結到 repo 的程式）
      ~/.aos/stack/mailbox → 捷徑到 ~/.aos/user/mailbox（舊指令寄的信不丟）
```

信分五種（`kind`）：`decide` 要你裁、`verify` 要你真機驗、`trial` 請你試玩、`chore` 只有你能做的雜事、`fyi` 純告知。前四種就是 wait-user 的四類。PROGRESS 不寄來（去看板）。

## 你會怎麼用（第一段）

```sh
aos-user ls                    # 所有在等你的，急件在上
aos-user show 3                # 看第 3 封：題目、ELI5、選項、推薦
aos-user answer 3 q1:a q2:c* --note "…"   # 裁（* 跟推薦不同，寫法照 decide-page）
aos-user ok 5                  # 純告知的「知道了」
```

回信直接寄回原寄件 agent 的信箱（帶 `in_reply_to`），它一分鐘內被叫醒；那封從待辦搬到 `done/`。

## 分檔

| 檔 | 內容 |
|---|---|
| [01 備料](user-zone-plan/01-備料.md) | 四隻 sonnet 搜集的事實＋出處：信箱底層、人在 aos 眼中、wait-user／decide-page／看板／手機看板、鐵律 2、eca_main、位置現況 |
| [02 fable 設計](user-zone-plan/02-fable設計.md) | fable 只讀備料的設計，原樣保留：位置比較、結構、五種信與額外 key、門上公告、指令、網頁與手機、授權五級、跨機、六段、15 條邊緣狀況 |
| [03 opus 細化](user-zone-plan/03-opus細化.md) | 對 fable 改的六處、每個動作對到的指令、網頁、授權、跨機的細化 |
| [04 施工與驗收](user-zone-plan/04-施工與驗收.md) | 六段：1 指令列最小可用、2 通知＋收件檢查＋過渡、3 桌面網頁、4 手機、5 簽名＋decide-page 併入＋專區 agent、6 分帳號／沙箱；每段怎麼用、做哪些檔、驗收 |
| [05 待裁與衝突](user-zone-plan/05-待裁與衝突.md) | 要你裁的 12 題（選項＋推薦）、跟現行規矩衝突 10 條 |
| [06 試驗紀錄](user-zone-plan/06-試驗紀錄.md) | 規劃時撞到的 aos 問題 18 條（只記不改） |
| [07 使用者裁定與施工](user-zone-plan/07-使用者裁定與施工.md) | 11-13 晚裁定逐題、段 1＋網頁施工與驗收、代定、沒做的、試驗紀錄 T1～T7 |
| [08 段 2 施工](user-zone-plan/08-段2施工.md) | 段 2：`aos-user tick`（收件檢查、退信、每小時上限、桌面通知、到期提醒）、aos 工具 `user_send`、守門 hook `user_zone_guard`；代定 11 條、換樹後要做的 6 步、試驗紀錄 T8～T11 |

## 授權一句話

全部 agent 跟你是同一個 linux 帳號，檔案權限擋不住 agent 冒你回信。所以分級：普通裁定靠「專區留底、收信方可用 `aos-user verify` 查」（L1）；手機經 Claude 中轉的答案最高 L1；push、刪檔現在仍要你當場說（L4），密語簽名（L2）做好後再裁要不要放寬。鐵律 2 要不要加一句見 05 的 U5、U6。**11-13 晚已裁**：U5 照推薦、U6 改成 push／刪檔也算，鐵律 2 已加（見上面「使用者裁定」）。

## 給線遷的介面

WAIT_USER 被專區取代的時機與搬法屬線遷；這邊交出的介面是 `aos-user ls --json`（每列 `kind`、`from`、`title`、題數、`deadline`、`urgent`、`host`），`kind` 的四種對上 wait-user 的 01～04。
