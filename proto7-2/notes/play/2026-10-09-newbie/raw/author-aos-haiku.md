## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，brief 退出 0；bad-link 退出 2、failed_gate=1、rule=lint；valid 退出 0 三關全過；publish 退出 0、dup=false，臨時 clone 多出分支 `apprentice/usage1_9ebf9840`。
## 對外指令數
3：`brief`、`check`、`publish`
## 新概念數
6：三關、需求單（request.json）、候選（candidate JSON）、apprentice 分支、退出碼 0/2/3/4、reviewer（rules／astra，預設 astra）
## 卡點
1. [publish] README 沒說預設寫進哪個 git repo（看起來是檢查器所在的 repo 根）；不敢直接跑，改 `--repo` 指到臨時 clone。約 2 分鐘。
2. [check 的 JSON] gate 2、3 是 `"ok": null`，README 沒解釋 null（猜是前關失敗未執行）。約 1 分鐘。
3. [預設 reviewer 是 astra] 不知道 astra 需要什麼環境，改用 `--reviewer rules`，沒試預設。
4. [README「約 5 分鐘」] 範例指令是 bash 寫法，預設 shell zsh，改 `bash -c` 才照抄得過；README 沒說要 bash。
## 五條分數（0–10，10 最好）
- 容易上手：7 三行照抄就跑，預期輸出寫在 README。
- 容易理解：5 三關、需求單、gate null 要自己猜。
- 複雜的藏起來：6 沙箱、astra、白名單收在後段，但預設值（寫哪個 repo、reviewer）藏得不夠明顯。
- 外層簡單但全面：7 三指令覆蓋需求到分支整條流程。
- 要背的少：7 主要記退出碼與 reviewer 兩選項。
- 平均：6.4
## ELI5
這是檢查學徒交來新工具的關卡。先給它需求單，再交學徒的候選檔，它依序檢查格式、跑測試對答案、再審查，三關都過才開新分支讓人決定要不要合併。照三行指令跑，看退出碼 0 還是 2 就知道過不過。
## ELI5 之後還複雜嗎
是，退出碼 0/2/3/4、reviewer 選哪個、gate 為 null 的意思，ELI5 說不清。
