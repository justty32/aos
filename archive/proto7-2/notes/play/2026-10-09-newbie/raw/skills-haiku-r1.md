## 試用者
Claude Haiku（新手）
## 分鐘
0.1
## 有沒有跑成功
成功。照「第一次跑」四行指令跑通：`index` 印出三本目錄（aos-inbox、aos-test、wf-lint），`pick` 印出 `/tmp/skills-demo.O6Hv4j/skills/aos-inbox/SKILL.md` 並顯示「本機挑選（關鍵字比對）」提示。兩步退出碼皆為 0，repo 未被改動。
## 對外指令數
3：`aos7-skills index`、`aos7-skills pick`、`aos7-skills mount`（README 寫明只有這三個；首跑只用到 index 與 pick，mount 沒試）
## 新概念數
4：skill（說明書，一個資料夾加 SKILL.md）、目錄／索引行（`- 名字: 簡介`）、pick（挑一本）、node（裝 `skills/` 的資料夾）
## 卡點
1. 第一行 `git rev-parse --show-toplevel` 依賴目前位置在 repo 內。我從 repo 內執行所以沒卡住，但 README 沒提醒在 repo 外會失敗，只在前面一句帶過要改成手動設 `S=`。約 0 分鐘。
2. 「進階：讓 AI 挑」一節出現 budget、ledger（帳任務）、grant.json、llmcall 等詞。我不懂也沒讀，依規則未追查。不算首跑卡住，但對新手是負擔。約 0 分鐘。
3. 首跑之後 README 只說「跑到這裡就夠了」，沒說明如何確認 `skills/.pick/log.jsonl` 或清理 `/tmp/skills-demo.*`（清理指令其實有在文中提到，我只是沒做）。約 0 分鐘。
## 五條分數（0–10，10 最好）
- 容易上手：8，四行照抄就跑通，成功輸出與 README 所列一致。
- 容易理解：6，「skill／目錄／pick／node」有表格解釋，但「node」「空間根」「aos 空間」等詞在首跑段落外才出現，需要猜。
- 複雜的藏起來：7，AI 模式、帳、mount 都標成「進階」且首跑不需要，但進階段落詞彙密度高。
- 外層簡單但全面：7，首跑簡單，契約卡與退出碼表齊全；但全面性靠多個連到外部 README 的段落，我依規則沒追。
- 要背的少：9，只有三個指令、四個詞，首跑只需兩個指令。
- 平均：7.4
## ELI5
一個資料夾裡有個 skills 抽屜，每本說明書是一個子資料夾，裡面寫著它叫什麼、什麼時候用。index 會把每本書的名字和一句簡介抄成一份目錄。pick 讀你的題目，從目錄裡挑出最合適的一本，然後告訴你它放在哪裡。你只要照指令各打一次 index 和 pick 就能看到結果。
## ELI5 之後還複雜嗎
是，進階的 AI 挑選需要開帳、背景帳任務和 llmcall，ELI5 沒有提到這些，新手看到會卡住。
