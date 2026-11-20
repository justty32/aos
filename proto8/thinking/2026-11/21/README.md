# proto8 討論紀錄：2026-11-21

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [session_key 實測（session-key-實測-1121）](session-key-實測-1121.md) | 暫存樹實測 sol 加 "session_key": "litellm_session_id" 前後：不加 4 輪快取都是 0，加了第 2 輪起每輪 12,416 token 命中（約 99%）；續量 luna、terra、astra（astra 在暫存樹新加一包）結果一樣；命中停在 12,416 是 128 一格、短句長不過下一格；範本沒改，建議四包都加、新增 astra，等使用者定 |
| [hook 第 5 刀後半（aos-hook-k5b-1121）](aos-hook-k5b-1121.md) | 範本 loop.json 接上 before_run／after_run、編譯寫四鍵、旗標檔由改清單的指令與 after_start 對、procs-kernel 接 loop 的四個點（清單 loop_hooks.json，kernel 程式沒改）；hook_fire 沒動；全套 79 夾跟基準相同另加 12 支；未決：起來時對旗標要等 hook_fire 換掉 |
| [llm kernel 思考程度（llm-effort-1121）](llm-effort-1121.md) | 實測 LiteLLM 帶尾碼的模型名與 reasoning_effort 都送得到上游（sol 帶 none 被擋 400、nothink 推理歸 0），max／none 只能走尾碼；不帶尾碼＝上游預設；換程度那一輪多半不中快取、之後照中。使用者選乙：信的 body 多 effort，llm kernel 照包的 efforts 表接尾碼；範本 sol、luna、terra、astra 用 $ref 共用兩張尾碼表，agent-fsm 的 llm.json 認 effort。LLM_KEYS（hook5 的檔）、隊 kernel 轉 effort、~/aos-home 還沒動 |
| [tool-desc-瘦身-1121](tool-desc-瘦身-1121/README.md) | ann 每輪送的 50.8 KB 工具說明拆帳（一半 description、一半參數 schema）；原型把 description 縮成一兩句＋指知識庫，sol 每輪 prompt 12,553 → 6,185（−51%）、小任務照樣做對；推薦做這個、預設包不動，系統文字補知識庫在哪；預設包要不要縮、說明要不要自足兩題等使用者定；施工檔單已備 |
| [shell-指令的比喻-1121](shell-指令的比喻-1121/README.md) | 使用者問「在 shell 裡下 aos 指令可以比喻為啥」（他的直覺：強行觸發另一個 cpu 跑一個 Linux 行程、再往別人的 stack 塞指令）；讀程式分七型（沒有一條走 socket，全是放信、改檔、一處送訊號），直覺貼在「不歸 daemon 管、直接寫別人的 stack、沒東西擋」，不貼在「多半放下就走、塞的常是請求、agent 的工具是同一支程式」；攤七個候選比喻與十四個邊緣狀況，不選定；等使用者答三題（cpu 指哪個、照來源還是照碰法切、直接改檔算不算正門） |
| [aos-daemon-env-1121](aos-daemon-env-1121.md) | agent 這塊讀 AOS_DAEMON 共 36 列：非 daemon 不可 12、只要自己的 stack／定義 14（工具先 ctl who 查表認自己）、路標顯示照傳 10；沒設時工具 DaemonMissing，工作區＝樹根被 ./.stack 退路蓋掉；搬到另一個 daemon 實測四種都跑得起來、歷史接上，差一點三處（覆蓋檔相對路徑、信 reply_to、等腦回信中搬），綁 daemon 三樣（表上那列、時鐘登記、子 agent）；照 11-20 方向要改的集中在 aos-agent common.target／find |
