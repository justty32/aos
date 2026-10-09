## 試用者
Claude Haiku（新手）
## 分鐘
0.4
## 有沒有跑成功
成功，一句話：照 skills README「第一次跑」整段執行後，印出三行索引（aos-inbox、aos-test、wf-lint）、`{"ok": true, "why": null}` 開帳回條、`aos-inbox/SKILL.md` 路徑，以及必用表（任務類型：改完程式 → aos-test）。背景 ledger 已被腳本結束，無殘留程序；repo 的 git status 沒有新變動。
## 對外指令數
5：`aos7-skills index`、`aos7-skills pick`、`aos7-skills mount`（三個對外指令），另加 `aos7-budget init`、`aos7-budget ledger`（pick 前置必跑的開帳與帳任務，第一次跑就要用到）。
## 新概念數
10：node（資料夾形式的工作空間）、帳（budget）與 grant、帳任務（ledger）、回合（round.json／tock）、llmcall 閘道、llm.fake 與 llm.litellm 兩種 gateway、索引行與 index.json、pick、掛載（mount／tasks.json）、必用表（must.json／MUST.md）。
## 卡點
1. 第一次跑整段指令：照抄可以跑，但我不懂為什麼 pick 前要開「帳」與起「帳任務」；README 只說「一律經 llmcall 記帳」，沒解釋帳是什麼。我只能先接受它是前置步驟，沒有深究。
2. `sed -e 's/"author"/"skills"/' -e 's/: 1000,/: 100000,/' …grant.json`：README 說 grant「從 llmcall 範例抄、把使用者改成 skills、額度調大」，但我不能讀範例檔，所以只能照抄 sed，不知道 grant 裡還有哪些欄位、100000 是什麼單位。
3. README 寫「空間根（有 `.aosd/` 的那層）」，我不懂 `.aosd/` 是什麼，也沒有讀到說明。這只影響 mount，我沒有實際跑 mount。只記下來，沒深究。
4. README 指向的 llm2 藍圖（notes/blueprint-llm2.md）、spec 連結與 `~/repo/workflows/skills/README.md`（格式來源）依規則沒有讀，所以 grant 格式與 skill 格式的細節都停在「照抄」。
5. 只跑了 README 的第一次跑與兩個 `--help`，沒有跑 bank.py、真 AI、mount 或 llmcall 的第一次跑（不在我的任務範圍）。
## 五條分數（0–10，10 最好）
- 容易上手：6 整段照抄就跑通，但要先信任前置的帳與 grant，才敢動 sed 參數。
- 容易理解：5 五個概念表與三個指令的白話說明清楚，但帳、grant、回合、llmcall 要跳到別的 README 才懂。
- 複雜的藏起來：4 pick 背後其實要開帳、起帳任務、走 llmcall 記帳，新手在第一次跑就被迫看到這些，沒有藏起來。
- 外層簡單但全面：7 對外只有三個指令，退出碼表與契約卡很完整，分層清楚。
- 要背的少：5 三個主指令很少，但前置的 budget init／ledger、grant、round.json 要照抄，實際要記的比三個多。
- 平均：5.4
## ELI5
資料夾裡放了很多「說明書」，每本說明書是一個資料夾，裡面寫了它叫什麼、什麼時候用。`index` 把每本說明書的名字和一句話抄成目錄，`pick` 讓 AI 看題目和目錄挑出一本，`mount` 把挑中的說明書借給某個任務用。用 AI 挑之前要先開一個記帳本，所以要先跑幾行準備指令。
## ELI5 之後還複雜嗎
是，因為「記帳本、grant、帳任務」這些前置步驟仍然要先懂一點，一句話說不完。
