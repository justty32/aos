# proto8 討論紀錄：2026-11-22

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [工作區與 _stack 規劃（工作區與stack-1122）](工作區與stack-1122/README.md) | 使用者定 A～D：_stack 放 repo 裡並被根 .gitignore 忽略、換機才 commit；cwd 不變、私有地盤 wf/ws/<agent>/ 照掛的層級嵌套；任何一層 temp/ 不進 git、交件查單檔大小；_stack 取代 ~/aos-home。第二版再定 E：llm kernel、權限站各台自己跑、放 repo 外，用 AOS_LLM_KERNEL、AOS_KERNEL 指定（不新造變數名）；舊樹 eca-claude、ann 不搬；公司現有的樹別管；用量預算不處理。規劃分九條線（含換機說明書，只規劃、沒施工）；未決一題：根那份小定義放哪 |
| [公司體制發想（公司體制-1122）](公司體制-1122/README.md) | 使用者要規劃很多 agent 分成幾台 daemon、用公司體制（部門、座位、資產、經費）組織；只發想：現況盤點（零件大半已有，缺部門紀錄、跨 daemon 上下級、通訊錄、牆）、四種樣子（甲一台 daemon 加名冊／乙一部門一台子 daemon 同一個根／丙各自獨立 daemon／丁名冊當正本），規劃員傾向乙；未決：要使用者回答七題（為什麼要分、選哪種樣子、部門寫在哪、直接說話是哪種、部門資產指什麼、經費做到哪、整間搬還是分開搬） |
