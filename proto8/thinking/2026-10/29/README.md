# proto8 討論紀錄：2026-10-29

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-29 介質後續規劃：投遞、有順序的投遞、daemon 兩個手把、鎖的用法、父子交代、窗的改口](medium-plan/README.md) | fable 照 medium 決定 1～29 做的細節設計（只寫文件、條文只是草稿）：信箱四格 tmp／new／cur（done 選用）、一封信＝資料夾＋`letter.json`（`kind`、`sender`＝身分路徑、`sent_at`、選填 `reply_to`／`in_reply_to`、`body` 由收信程式定）、寄＝mkdir tmp→rename 進 new、認領＝rename 進 cur、撤回只到認領前、壞信丟掉記 `letter_warning` 不通知；有順序的投遞＝信箱多 `order.lock/`＋`order.json`、鎖握到 rename 完；aos-daemon 拆成 `ctl`／`state` 與 `loops_ctl`／`loops_state` 兩對、`loops_mailbox` 開信箱模式二選一、paused 整圈暫停；鎖採頂層四點、名牌多 `holder` 路徑；父子交代現有的夠、補 N-64 集中說；條文草稿 C-75、N-14／N-16 改口、N-15／N-28／N-54／N-07 補、N-64 新、P-11 加註；實作八步；**衝突六條、方向題三條等使用者看** |
| [2026-10-29 playground：agent 的輸入是對話簿、看信箱是一個 tool](playground-queue/README.md) | 使用者「那就A。直接叫queue不太好吧...再想想」「那就1」：檔名沿用 `history.jsonl`；試驗場 `~/code/playground` 做最小版：命令列一句接進 `$AOS_WS/history.jsonl`、整本交給 `claude -p`、回答接回去，看信箱是經 aos-mcp 的 inbox tool（N-16 信箱、aos-post 認領），prompt 只給一句習慣；haiku 16 次看信 9 次、算術信照做、天氣信不做；帶給使用者：誰叫它看信箱（建議先換 sonnet 再試）、看 N-16（建議）、四處衝突（history 放哪、信箱放哪、信的內容進了對話、認領了沒人收掉）；**看完後方向改了**：使用者講兩個使用場景（射後不理、射後有理），兩個都用不到 agent 自己看信箱，inbox tool 解錯題、上面的題先擱著；跑完結不結束寫死在定義裡、由腦的性子決定（`claude -p` 答完退，互動式 `claude` 停著、才在外面包一層管生命週期） |
| [2026-10-29 agent-bob：射後不理、射後有理兩隻實跑](agent-bob/README.md) | 使用者補「給予stdin/偷看stdout的動作，我希望有一個通用接口，也就是aos-say/listen」；試驗場做 agent-bob-1（`claude -p` 讀 task.md、寫 result.md，4 回合退 0）與 agent-bob-2（自己的循環永不退，照 P-11 收 aos-say 的題，`ctl.json` 的 paused／stopped 有效，say 到答出 3～6 秒、記憶對）；say／listen 不改就接上，偷看與暫停不共用；aos-hub＋一題一答工具也做得到 bob-2，但包不了自己循環的程式、hub 的 pause 照收題；帶給使用者：對話簿放 stack、停著等的 agent 開 ctl、hub pause 改名、契約定在 CONVENTION、外層用 hub；使用者「幫我多想想」後頂層再想成三題；10-30 早使用者照直覺答（決定 33～35）：agent 這層是訊息的 queue、不叫信箱，aos-loop 是 aos agent 的內部組件，外部 coding agent 的生命週期在外面包（aos-daemon、包成 `max: 1` 也可以，或擴充，沒有也可 `ps aux`＋`kill`），其餘照隊長，claude code 這類的 session 資訊 symlink 或複製一份進 aos |
