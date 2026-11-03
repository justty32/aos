# workflows on aos — 要拿去問使用者的問題

← [本場索引](README.md)｜[workshop](../../README.md)

**本場最主要的產出。** 去重成八題，可以逐條回答；第一題是四位都問到的核心。在這些答案回來之前，任何一條推論都不該排進 roadmap。

---

## 要拿去問使用者的問題

第一題是核心；後面用來決定該先機械化哪一層。

1. **最近一次你覺得 workflows「不是很好用」，當時具體在做什麼、卡在哪一步？**
   先確認實際痛點，不把檔案 drift 當答案。

2. **下面哪一類最常痛？如果只能消掉一步，你選哪個？**

   - 初次安裝、填 placeholder，或把 template 新版升進既有專案；
   - 找不到／派錯該走的 workflow；
   - 跨 session 保存進度、WAIT_USER，或記得完成後清掉 open；
   - 記得跑 tick／處理到期項；
   - 文件寫了，但 agent 沒照流程做。

3. **`SESSION-LOG`／`WAIT_USER` 裡現在保留完成歷史，是你故意要的，還是因為常忘記清？**
   要確認，才知道 open-only 是否真是需求。

4. **open 狀態需要隨 Git 跨機、讓另一台機器／另一個人接手嗎？**
   若要，`.aos/wf/*.json` 不能在不版控時成為唯一真源；若不要，本機 machine state 才比較自然。

5. **你希望人直接編輯活狀態檔，還是只透過 `aos wf wait／resume／done` 改？**
   候選：直接改 JSON、可編輯 markdown、命令＋generated view。

6. **inbox 現在最麻煩的是寄信撞名、忘記看、忘記歸檔，還是根本不麻煩？**
   inbox 原本就是可忽略信件，不能未問先改成 queue。

7. **template 更新真的需要帶進既有專案嗎？還是安裝後各專案就各自分叉，不再追上游？**
   三方合併建立在「你想升級」的假設上；若本來就不追新版，source lock 的價值只剩追溯，不是 upgrade。

8. **哪些 workflow 真的需要自動喚醒？schedule／tick 是常用能力，還是這個 repo 後來長出的少數
   特例？**目前沒有使用頻率證據。
