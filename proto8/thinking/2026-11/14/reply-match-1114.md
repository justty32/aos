# 回答配對（reply-match-1114）：agent 的回答對得到是回哪封信，ask／listen 不再只能拿最新那則

← [2026-11-14](README.md)｜[thinking](../../README.md)｜線工具 ok-pilot（部長 head-tools；第 1 階段只設計，施工等 head-tools 核准）

## 由來

- wf/advices〈信件與溝通〉「aos-agent 沒有 ask」：11-14 ok-pilot 只做了跟 subagent 工具 op ask 同語意的 `aos-agent ask`（2ef627f1b），沒有配對信名。
- 同日投稿 `wf/temp/ok-pilot/aos-advice/回答對不到是哪封信.md`。
- head-tools 11-14 交辦本題。設計要寫清楚五件事：history 多記什麼、ask／listen 怎麼配、eca 做不做、對現有 history 讀者的影響、換樹要帶哪些檔。proto8 不留舊格式相容。

## 檔案

| 檔 | 內容 |
|---|---|
| [01-備料](reply-match-1114/01-備料.md) | 寫 history 和讀 history 兩方的現況（gpt-6.1-sol 兩隻唯讀查原始碼），加上別線的定案與前置依賴 |
| [02-fable稿](reply-match-1114/02-fable稿.md) | fable 的獨立設計，原文 |
| [03-計劃](reply-match-1114/03-計劃.md) | ok-pilot 的計劃 v2（v1 經 Argon 審後修改），含方向問題 |
| [04-Argon原文](reply-match-1114/04-Argon原文.md) | Argon 審 v1 的原文 |
| [05-採納表](reply-match-1114/05-採納表.md) | Argon 意見逐條採不採 |

## 進度

- 11-14 14:00 備料交齊；fable 稿到；03 v1 寫好，送 Argon 審。
- 11-14 14:19 Argon 審完。採納 A1～A3、A6～A15，改回 02 的 `letters.json`，落地改成「寫的一方先進」。03 v2 送 head-tools，第 6 節方向問題請轉專區。
- 11-14 14:22 使用者專區答 go: yes、land: one（一個 commit，不是推薦的分兩次）；head-tools 裁的 2a、3a、5a 照舊。03 改成 v3：§5 改成「一個 commit、換樹當晚最後 submit」，保留舊身體退路，附換樹當晚清單。送 head-tools 看 §5。
- 11-14 14:26 head-tools 同意 §5 v3、准開工。§5 補兩點：commit 要在 ok-kf pin 的收件截止前進 main、排最後一個，空窗內退路是主路；「新 eca 寫、舊 lib 讀」放進測試矩陣。§2 補上 ok-kmsg 在 listen.py 的保留點。
- 11-14 15:10 施工（暫存樹，Claude 子 agent 四隻：fsm、讀的一方、eca、文件）做完，受影響五套全綠；§1 的寫入順序照施工結果改成「先 pending、再 history、再 done」，回答只清自己那幾封（eca）、重交時從 dropped 拿掉。全套對照進行中，交件先寄 head-tools。
- 11-15 Claude 線 claude-rm 接手（ok-pilot 收樹退場，使用者 11-15「能做的先做」）：patch 重套到 086a7cafe，subagent 兩個 JSON 跟 398f71711 的 BookOld 手合；test_daily 抓到 letters.json 沒有 gitignore 分類，補 G101（carry、進 git）與 05-gitignore 指南一格；aos-agent 的「回答被移出 history」那條測試有時序競爭，改成移完再 listen 時斷言。全套對照沒有新紅，一個 commit 進 main；templates／lib 要等下次換樹。
