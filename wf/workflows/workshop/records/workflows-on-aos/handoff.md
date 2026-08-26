# workflows on aos — 轉交提案

← [本場索引](README.md)｜[workshop](../../README.md)

六條要交出去的提案，全部未拍板；每一條都以〈要拿去問使用者的問題〉的答案為前提。

---

## 轉交提案（未拍板，不自行改規格／roadmap）

1. **先拿上一節的問題問使用者，不先把任一推論排進 roadmap。**最少要知道最近一次具體事故、
   只能消掉哪一步，以及 open 狀態是否需隨 Git 跨機；這三個答案會改變第一個功能與磁碟真源。

2. **若使用者確認「活狀態靠記憶」是痛點，再拍板真源版面。**候選是三位的
   `.aos/wf/tasks/*.json`／位置即狀態，加 `status --format md` 產生 view；或研究人員的
   `wf/open/{agent,user,peer}/*.md` 真源，`.aos` 只負責 Deliver／`.runi`。兩者不能同時不分主次。

3. **若走 machine-state 版本，先做最小垂直切片。**`wf start → wait → resume → done` 加 status，
   只覆蓋 SESSION-LOG／WAIT_USER；`WORKFLOWS.md` 仍由模型讀，所有理由與判準仍在 markdown。四位
   都認為不需要先把 workflow 編成 lane。

4. **inbox 只共用原子信封，不共用 instruction queue。**若要機械化，先拍板 `wf accept MAIL`
   的語意：只有明示接受才轉 open task／Deliver；未接受仍可忽略，保留 inbox 原本的寬鬆契約。

5. **若使用者確認安裝／升級才是痛點，另開 module/install 工作。**保存 source version／base hash，
   upgrade 產三方 diff，只自動替換未修改檔；客製 workflow 不覆蓋。`doctor` 可先做只讀檢查，是否
   需要由使用者拍板。

6. **tick／schedule 等使用頻率確認後再收。**候選最小狀態是 `next_at`；喚醒時先成功 Deliver，
   再更新 cursor。不要因為現有 repo 有定期工作流，就推論每個匯入 workflows 的專案都需要 scheduler。
