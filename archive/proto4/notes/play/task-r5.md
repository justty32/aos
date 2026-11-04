# 試玩任務 r5：你是今晚第一次打開遊樂場的人（六站，只准看 playground/README.md）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**你的角色是回家想玩一下的使用者**，不是開發者。**只准讀 `playground/README.md`**，它連出去的四份 proto README 只有在卡住時才准翻，翻了就算一條「遊樂場指南沒講清楚」的發現。**不准讀 `proto4/notes/`、不准讀原始碼。**

**不要改 repo 裡任何檔案、不要 git commit／push、不要開其他 agent。** 遊樂場會把東西放在 `$AOS_PLAY`，你**一定要先** `export AOS_PLAY=/tmp/play5-<你的名字>` **再** `source playground/env.sh`，不然會跟別人撞同一個資料夾。玩完 `playground/down.sh`。LM Studio 已開著、模型已載（gemma-4-e4b）；**不要碰 DeepSeek 或任何 API key**。

## 要玩什麼

照 README 從「開場」走到第 6 站，每站記：**照抄指令能不能一次過**（能／不能＋卡在哪一行）、**花幾分鐘**、**畫面上有沒有讓你停下來想的東西**。「故意弄壞」那節至少玩三樣。第 6 站多玩兩句：一句要它用工具做事、一句閒聊；再 `--reset`／改問題玩一次看會不會撞名。

## 交出來

markdown 直接回我（不要寫進 repo），繁體中文、大白話、100 行以內：

- 開頭一句總評＋一個分數（1–5：「一個晚上回家能不能自己玩得開心」）。
- 六站各一行：過／沒過、幾分鐘、一句話。
- 發現清單，每條「現象 → 我期待 → 建議」一行，按「改了對今晚的人幫助最大」排。
- 附你實際跑過的指令（精簡）。
