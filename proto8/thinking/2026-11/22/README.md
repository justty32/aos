# proto8 討論紀錄：2026-11-22

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [工作區與 _stack 規劃（工作區與stack-1122）](工作區與stack-1122/README.md) | 使用者定 A～D：_stack 放 repo 裡並被根 .gitignore 忽略、換機才 commit；cwd 不變、私有地盤 wf/ws/<agent>/ 照掛的層級嵌套；任何一層 temp/ 不進 git、交件查單檔大小；_stack 取代 ~/aos-home。第二版再定 E：llm kernel、權限站各台自己跑、放 repo 外，用 AOS_LLM_KERNEL、AOS_KERNEL 指定（不新造變數名）；舊樹 eca-claude、ann 不搬；公司現有的樹別管；用量預算不處理。規劃分九條線（含換機說明書，只規劃、沒施工）；未決一題：根那份小定義放哪 |
| [公司體制發想（公司體制-1122）](公司體制-1122/README.md) | 使用者要規劃很多 agent 分成幾台 daemon、用公司體制（部門、座位、資產、經費）組織；只發想：現況盤點（零件大半已有，缺部門紀錄、跨 daemon 上下級、通訊錄、牆）、四種樣子（甲一台 daemon 加名冊／乙一部門一台子 daemon 同一個根／丙各自獨立 daemon／丁名冊當正本），規劃員傾向乙；未決：要使用者回答七題（為什麼要分、選哪種樣子、部門寫在哪、直接說話是哪種、部門資產指什麼、經費做到哪、整間搬還是分開搬） |
| [小工作室的個人筆記調查（筆記調查-1122）](筆記調查-1122/README.md) | 使用者要 agent 有自己的筆記（例：eca-aos-kb 記「知識庫不寫日期、原話例外」），將來當部門主管時分給底下的人；調查結論：筆記放地盤 wf/ws/<上層>/<名>/notes.md 可行、會跟著換機，但 system.txt 沒指路；四種做法（推薦先在 system.txt 加一句指路）、分給底下的人的三條路與衝突裁法、12 條邊緣狀況；未決：要使用者回答五題；使用者體驗那一輪（怎麼聯絡特定 agent、看它的筆記與資產）還沒做 |
| [progress.json 整理（progress整理-1122）](progress整理-1122/README.md) | open 段 42 條逐條歸類：被 11-21 活樹七次更新與今天 _stack 線 1～5、9 蓋過的 13 條建議關或改寫（附 commit）、8 組可合併、約 30 題濃縮成一句加選項、發想表標出跟公司體制與私有地盤的接點、小尾巴附大小與模型；progress 缺 _stack 線 6～8、公司體制、筆記調查三樣；下一步三件事：搬家、小工作室試營運、用編譯寫小工作室。只建議，沒改 progress |
| [agent-fsm 每輪輸入成本與快取（prompt-cost-1122）](prompt-cost-1122/README.md) | 重量 HEAD 起手 ann：每輪 6,225 token（工具 4,199、LiteLLM 自加 codex 指示約 1,620）；aos 送出的前綴每輪逐字穩定，沒有 aos 這側能不改行為就修的快取問題；沒中快取的 token 八成來自上游偶發整段沒中（約 18% 的後續輪）；未決：五個選項要使用者定（A 代理放行 prompt_cache_key 最有效但沒驗證） |
| [wf/user 使用者專屬區規劃（使用者專區-1122）](使用者專區-1122/README.md) | 使用者要開 wf/user 當這個 repo 的使用者專屬區並規劃用法；規劃：當成人的地盤，agent 預設只讀、叫了才寫，跟 ~/.aos/user 使用者專區方向相反、不合併；盤點查到 repo 在 GitHub 上公開（私人素材要有不進 git 的位置）、index_gen 會往裡生 _index.json；六題待裁。使用者 11-22 答：「wf/user是我的地盤，裡面的東西無法保證穩定性。user advice可以搬進去。剩下都按照推薦」，施工交給另一條線 |
| [aos-user 找新家（aos-user新家-1122）](aos-user新家-1122/README.md) | aos-user 本體 11-18 隨舊樹刪掉，只剩 ~/.aos/scratch 的 11-14 抄本；規劃三案，推薦放 proto8/frontend/aos-user/、frontend/bin 放連結（env.sh 本來就放上 PATH，換台零步驟、前端不改、不用 install.py）。使用者四題都照推薦（放全景頁的夾、tick 先不裝、專區每台一份、不跟 wf/user 對接），當天裝回：乾淨複本上 aos-user 20 支、全景頁 52 支全過，假題目 /api/asks 讀得到。未決：user_send／user_verify 的舊找法等下次跑 install.py 一起拿掉；活的全景頁要使用者重起才用得上 |
| [知識庫中文版跟上正本（知識庫中文版同步-1122）](知識庫中文版同步-1122.md) | 使用者「希望knowledge zh md能夠跟上最新的」：中文映照版 158 頁全部過期（還是 json 時的樣子；2 頁缺、0 頁多出來，13 份子夾 README 是映照版自己的），照現在的 md 知識庫整份重做：81 頁用 11-21 譯文機器轉、26 頁照 diff 改譯、2 頁新譯、wf 46 頁照抄，每份記跟到正本哪個 commit、README 附查過期的查法；以後怎麼跟，使用者「都先按照推薦」：每天收工 eca-aos 跑查法、有過期就派線補齊（寫進 wf user/02「收工」）；stock template 統一譯「內建範本」 |
