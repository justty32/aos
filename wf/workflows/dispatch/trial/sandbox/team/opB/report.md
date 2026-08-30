# aos 試用隊 L2：操作者 B 實測成品

執行時間：2026-08-30 19:00–19:03（Asia/Taipei）。全程使用既有 `build/bin/aos`，未重編、未碰 `core/`、未建立真實 `/home/lorkhan/.aos`，也未啟動子代理。

1. 步驟 1／期待：boss 已把 w1 加進通訊錄後，w1 應有可直接回報 boss 的回程位址，或收到任務時自動知道寄件者。／實際：w1 的 `aos contact ls` 並非字面上的全空，而是只有內建的 `~  /home/lorkhan  使用者`，沒有 boss；必須由進入 w1 世界的操作者手動跑 `aos contact add boss ../boss`，系統沒有因 boss 單向加入 w1 而自動互加。之後 `aos say --to boss "回報：README 翻好了"` 才成功。／缺哪個原語：自動回程位址、雙向 team membership，或不必先建 contact 的 `reply`。／跟 Claude Code 開隊的對照：開隊後隊員與 team lead 的關係應由 team 結構承載；操作者不應切進隊員目錄再補一次 leader 聯絡人。

2. 步驟 1／期待：boss 收到 worker 回報時，至少能辨認 sender=w1，並和使用者輸入區分。／實際：看不出來。w1 回報與 boss 原本收到的使用者訊息在 `history.json` 都只有 `content`、`role`，兩者都是 `role: "user"`，沒有 sender、來源世界或訊息 ID；schema 長得完全一樣。兩則原始 JSON 如下。／缺哪個原語：帶 sender／來源 world／message-id 的 message envelope。／跟 Claude Code 開隊的對照：隊員回報應帶隊員身份，team lead 才能把結果歸因給正確 worker；目前 aos history 把 worker 和真人使用者壓成同一種 user 訊息。

```json
{
  "content": "回報：README 翻好了",
  "role": "user"
}
```

```json
{
  "content": "請你用 aos 工具，把『把 README.md 翻成英文』這件事派給通訊錄裡的 w1。指令是 aos say --to w1 <訊息>",
  "role": "user"
}
```

3. 步驟 2／期待：`aos say --to ~ "回報"` 應穩定表示「寄給使用者」，或錯誤直接教操作者如何寫。／實際：未加引號時，zsh 先把參數展開，trace 是 `aos say --to /home/lorkhan 回報`；aos 實際收到 `/home/lorkhan`，報 `aos say: 通訊錄裡沒有 /home/lorkhan`（exit 1）。加引號後的 `aos say --to '~' "回報"` 才命中內建聯絡人，但因真實 home 沒有 agent 而報 `aos say: 這個資料夾還沒有 agent；請先跑 aos agent init`（exit 1）。第二個錯誤有指出 init，第一個沒有提醒 `~` 要加引號。／缺哪個原語：不受 shell tilde expansion 影響的固定 user address，或在收到 home 絕對路徑時給出 `--to '~'` 的針對性提示。／跟 Claude Code 開隊的對照：真人使用者是主對話的既有端點，不需要記 shell quoting 規則才能成為收件人。

4. 步驟 2／期待：使用者只作收件人時，不應為收信而啟動 LLM。／實際：fakehome 必須先有 `.aos` 並跑 `aos agent init --name user`，之後 w1 才能 add contact 並投遞；訊息確實出現在 `.aos/agents/user/say/1788087747649536533-3158859-0.md`。整段沒有開 loop、沒有呼叫 LLM，所以「已初始化但永不 run 的 agent」實際上可以只當信箱、不燒 CPU；但沒有明確的 mailbox-only 身份。／缺哪個原語：第一級的 user/mailbox-only endpoint，建立時不必宣稱它是 agent。／跟 Claude Code 開隊的對照：真人主 session 本身就是回報端點，不必另外假造一隻休眠 agent。

5. 步驟 2／期待：使用者在 `~` 下應有一個只讀信的 CLI，讀完也能知道寄件者。／實際：`aos listen --once` exit 0 但沒有輸出，訊息檔仍留在 `say/`；本次劇本能用的讀法只有列出並直接讀 `.aos/agents/user/say/*.md`。檔案內容只有 `回報：翻好了`，檔名也只有數字，沒有 w1，因此讀完仍不知道誰寄的。`aos run --step N` 雖可能消費訊息，但會叫 LLM，不符合「只有信箱、沒有 CPU」。／缺哪個原語：不叫 LLM 的 `aos inbox/list/read`，以及保留 sender 的郵件格式與 read/ack 狀態。／跟 Claude Code 開隊的對照：隊員回報應直接出現在主 session 並標示隊員，不應要求真人翻內部 `say/` 檔案。

6. 步驟 3／期待：三隻 agent 共用一顆 LM Studio 時，三個 `aos run --step 3` 至少都能完成；若後端序列化或排隊，CLI 應讓操作者看出正在等什麼。／實際：三個 run 在 0.2 ms 內啟動，三封短問題也並行成功投遞；三個 history 都收到 `短問題：2+2 是多少？`，沒有卡死、錯誤或逾時。實際 wall-clock 為 boss 2.377 秒、w1 9.034 秒、w2 1.826 秒，整批由 19:03:26.520658733 到 19:03:35.556156310，共約 9.036 秒。各自有 LLM 工作的回合耗時是 boss 2166 ms、w1 8824 ms、w2 1616 ms，其餘空回合約 3 ms。輸出沒有排隊提示，也沒有「在等別人」；因此只能看到完成時間差，不能判斷 w1 較慢是排隊、模型生成較久，還是其他原因。／缺哪個原語：共享模型的 queued/running 狀態、排隊位置、等待原因與每次 request 的計時分解。／跟 Claude Code 開隊的對照：Claude Code 開隊至少需要逐隊員身份與任務狀態可見；至於模型供應端排隊也未必會透明，但 aos 現在連三者是在跑、在等或已空轉都只能靠零散的 turn 時間反推。

原始並行紀錄保存在同目錄的 `step3-boss.log`、`step3-w1.log`、`step3-w2.log` 與三個 `step3-send-*.log`。
