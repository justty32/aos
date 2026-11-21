# proto8 討論紀錄：2026-11-21

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [session_key 實測（session-key-實測-1121）](session-key-實測-1121.md) | 暫存樹實測 sol 加 "session_key": "litellm_session_id" 前後：不加 4 輪快取都是 0，加了第 2 輪起每輪 12,416 token 命中（約 99%）；續量 luna、terra、astra（astra 在暫存樹新加一包）結果一樣；命中停在 12,416 是 128 一格、短句長不過下一格；範本沒改，建議四包都加、新增 astra，等使用者定 |
| [hook 第 5 刀後半（aos-hook-k5b-1121）](aos-hook-k5b-1121.md) | 範本 loop.json 接上 before_run／after_run、編譯寫四鍵、旗標檔由改清單的指令與 after_start 對、procs-kernel 接 loop 的四個點（清單 loop_hooks.json，kernel 程式沒改）；hook_fire 沒動；全套 79 夾跟基準相同另加 12 支；未決：起來時對旗標要等 hook_fire 換掉 |
| [llm kernel 思考程度（llm-effort-1121）](llm-effort-1121.md) | 信的 body 帶 reasoning_effort（跟 endpoint 並排、給 kernel 看），llm kernel 照包的 reasoning_efforts 清單查收不收；換程度斷快取是上游頂層 reasoning.effort 換了就重算，改走 Responses API 在 input 最後接 configuration_update，暫存樹實測換程度後照中；llm_http 加 api responses，範本 sol、luna、terra、astra 改走它；隊 kernel 包寫 forward 照轉。LLM_KEYS 歸線 hookfire、~/aos-home 沒動 |
| [tool-desc-瘦身-1121](tool-desc-瘦身-1121/README.md) | ann 每輪送的 50.8 KB 工具說明拆帳與原型；使用者選「只留一兩句＋指去知識庫」「self 只留兩支」（取代 11-14 tools40: a），已施工：39 支說明改短、系統提示寫明知識庫路徑、預設 36 支，sol 每輪 12,553 → 5,837 token（−53%）、七題小任務都對，luna 都答對但查知識庫繞 10 次；self_llm 說明與三份範本文件等別線交了再補 |
| [shell-指令的比喻-1121](shell-指令的比喻-1121/README.md) | 使用者問「在 shell 裡下 aos 指令可以比喻為啥」（他的直覺：強行觸發另一個 cpu 跑一個 Linux 行程、再往別人的 stack 塞指令）；讀程式分七型（沒有一條走 socket，全是放信、改檔、一處送訊號），直覺貼在「不歸 daemon 管、直接寫別人的 stack、沒東西擋」，不貼在「多半放下就走、塞的常是請求、agent 的工具是同一支程式」；攤七個候選比喻與十四個邊緣狀況，不選定；等使用者答三題（cpu 指哪個、照來源還是照碰法切、直接改檔算不算正門） |
| [aos-daemon-env-1121](aos-daemon-env-1121.md) | agent 這塊讀 AOS_DAEMON 共 36 列：非 daemon 不可 12、只要自己的 stack／定義 14（工具先 ctl who 查表認自己）、路標顯示照傳 10；沒設時工具 DaemonMissing，工作區＝樹根被 ./.stack 退路蓋掉；搬到另一個 daemon 實測四種都跑得起來、歷史接上，差一點三處（覆蓋檔相對路徑、信 reply_to、等腦回信中搬），綁 daemon 三樣（表上那列、時鐘登記、子 agent）；照 11-20 方向要改的集中在 aos-agent common.target／find |
| [aos-agent 預設目標（aos-agent-預設目標-1121）](aos-agent-預設目標-1121.md) | 使用者說 -t 可以省、-d 不能省：aos-agent 沒給 -t、AOS_AGENT 沒設時先看 ./.stack 再看 ./，夾裡有 stderr.txt（daemon 在每隻 proc 的 stack 建的）且是 -d 那台表上某列的 stack 就是那隻；daemon 只從 -d／AOS_DAEMON 來，拿掉 cwd 的 ./.stack 退路（aos-daemon-ctl 等照舊）；丁不做。特徵檔不用 interfaces.json 的理由、邊緣狀況、要給 N-63 加的註在紀錄 |
| [hook_fire 換 aos-hook fire（aos-hook-fire換-1121）](aos-hook-fire換-1121.md) | 範本與編譯的 on_start／on_stop 改叫 aos-hook fire -q --agent、刪掉 hook_fire（使用者「可以」）；起來就對旗標；行為差別逐項（設計都寫了）；舊 loop.json 裝新版後起不來，~/aos-home 的 ann 要抄範本或重新編譯；條文要補的字列在紀錄 |
| [self-history-range-1121](self-history-range-1121.md) | self_history 的 range "-3" 報 FlagUnknown：根因是只有 ls 沒把值放 -- 後；修好；最後 K 則第二輪照使用者改成旗標 -n K（ls -n 3＝ls -n -3，rm、summarize 也有），工具 JSON 的 "-3" 不變；盤點三十多支包命令列的工具，同病另 5 組一起加 --；set 收不收 -n 只評估、等使用者 |
| [aos-home 更新（aos-home-更新-1121）](aos-home-更新-1121.md) | 家機 ~/aos-home 更新到 88ea321f4：install.py、kernel.json 補思考程度、ann 照範本換（保留 model=sol、loop.json 改 aos-hook fire），備份 .bak-1121b；sol 驗四題 prompt 12,646→5,962、快取 5,888、high 程度帳本有記；關回原狀；過程頁在桌面 |
| [compact-改進規劃-1121](compact-改進規劃-1121/README.md) | agent-fsm /compact 改進規劃（只出稿）：真模型 history 工具輸出占 64%～76%，留最後 3 則其餘換佔位 history 少 27%～78%（skyrim prompt 約 68k→30k）；預設清法已定；hook 開 before_compact／after_compact（補回寫在摘要後一則 user）；施工五刀、第 1、3 刀不依賴待裁；待使用者答三題（清完夠低省不省摘要、hook 開到多深、新點現在加還是等格式審完） |
| [hook_points 格式・使用者審（hook-points-格式-使用者審-1121）](hook-points-格式-使用者審-1121.md) | 使用者審 hook_points.json 宣告格式的原話：硬性只要 id 與 input schema，change 改 output schema，其餘鍵想放啥放啥；一份只有一個 provider 妥不妥未定；還沒派線 |
| [編譯的 kernel 入口（aos-pylib-kernel入口-1121）](aos-pylib-kernel入口-1121.md) | from aos.py.kernel import defs：defs.Kernel(說明, knobs=, hooks=, program=, body=) 編出跟 templates/kernel 手寫夾同樣的夾（三份逐鍵對得上），@fn.hook 抽成 fn/<名>.py、loop 的四個點分到 loop_hooks.json；骨架 kernel-python；真站與真 daemon 驗過，全套跟基準無新紅；替使用者做的九個選擇等他看 |
