# 第 1 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[下一份 →](round-2.md)

## 1. 這一輪到底發生了什麼

四個人都用現成的 aos 把「想一步、做一步、把結果交回去」連跑三次。正常時都跑得完，但半路被停掉後都要人查現場、搬檔或重排剩下的事，而且有一種情況光看這台電腦永遠無法知道外面到底做了沒。實驗中沒有出現需要同時照看的第二件工作，所以這輪沒有替最大套方案提供實際理由。

## 2. 冒出來的新詞

- **`.runi`**
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：`aos exec <world>` 取走 `.aos/inst.json` 後改成的 `.aos/inst.json.runi`；目前只能說「這整包沒正常收尾」。

- **Publish**
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前還不是公開命令，是把檔案先寫好再一次換成正式名稱的提案；本輪的私有 `atomic-publish.sh` 是試作。

- **Deliver**
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：現在是投件者手寫 `.temp` 再 `mv` 成 `<name>.json`，交給 `aos exec <world>` 取件；`aos deliver` 還是提案。

- **Effect 與 `unknown`**
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：指呼叫外部服務及「可能已做、可能沒做」的結果；目前沒有 aos 命令處理，`Effect＋resolve` 仍是提案。

- **receipt**
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前 `aos exec` 沒有這種可重開後查驗的收據；Publish 與 Effect 要不要留它仍是提案。

## 3. 看到的錯誤訊息各是什麼意思

- `aos exec: refusing ... .aos/inst.json.runi already exists`：aos 看到上次沒收好的整包現場，因為不知哪些已做過，所以拒絕自動再跑。
- `restart_exit=3` 或 `immediate_restart_exit=3`：重開命令不是自己壞掉，而是因上面那份 `.runi` 刻意停下來等人處理。
- `...=present` 與 `...=missing`：前者是檔案還在，後者是應有的結果或退出紀錄沒寫下來；兩者同時出現就是「有做過的跡象，但收尾不全」。
- `deliver_exit=137`、`schedule.exit=137`、`tool.exit=137` 或 `kill9_exit=137`：該行程是被 `kill -9` 強制砍掉的，137 就是 128＋第 9 號訊號。
- `Killed`：這是 shell 把「行程已被強制殺掉」直接印出來，不是另一個新錯誤。
- `ctrl_c_exec_exit=130`：這次 `aos` 是因 Ctrl-C 中止的，130 就是 128＋第 2 號訊號。
- `schedule.exit=66`：負責排下一步的測試腳本自己回報失敗，所以後面沒有新工作可跑；66 不是 `aos exec` 本身的總結果。
- `rejected_exit=70` 與 `accepted_exit=70`：這個 70 是測試腳本用來表示「本機沒收到可信的答案」，所以外部其實收了或沒收，本機看起來都一樣。
- `restart_exit=0`、`blind_restart_exit=0`、`plain_restart_exit=0` 但 `result=missing` 或 `final_exists=no`：命令本身沒找到可執行的東西並正常結束，不代表整條工作真的完成。
- `temp=yes ready=no`：內容還停在草稿名稱，aos 故意不讀；`manual_fix=rename_temp` 表示這次是人檢查後手動改名才救回來。
- `ledger_lines=1`、`ledger_lines=0` 但 `local_snapshot_diff_exit=0` 或 `client_worlds_diff_exit=0`：外面一份已收到、一份沒收到，但兩份本機現場比對完全沒差異。
- `provider_ledger_lines=2` 或 `oracle_ledger_lines_after_retry=2`：原本那次其實已被外面收到，不查就盲目重試後又做了一次。
- `aos_after_tool_group_kill_exit=0` 但 `tool.exit=137` 與 `schedule.exit=66`：aos 只報「這包命令處理完了」，包裡的工具被砍掉、下一步失敗並不會讓它改報失敗。
- `orphan_alive_after_manual_kill=1`：這裡的 1 是 `kill -0` 查無此行程，意思反而是人工殺掉後孤兒已不存在。
- `od` 印出 `65 66 66 65 63 74 6e`：檔案確實有 `effectn` 這 7 個字元，先前 `wc -l` 報 0 只是因為它數的是換行符。
- `aos exec` 連續回 0 但錯名的 `delivery-turn1.timestamp.pid.json` 原封不動：檔名多了點就不符取件規則，現行實作會安靜略過，所以它沒有可翻的錯誤訊息。

## 4. 所以呢

這輪直接對到 [OPEN-QUESTIONS 第 2 題](../../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)「近期 core 要回撤到哪裡」。現在仍是三個選項：

- **只留最小 Deliver**：得到最小的 core；賠掉的是這輪已實際出現的多處通用安全寫檔仍要由各人自備，外部到底做了沒也繼續交給上層或人處理。
- **先做 Publish、Deliver、Effect 三項**：得到一套共用的寫檔、投遞與外部結果記錄邊界；賠掉的是必須現在就定義命名、碰撞、收據、重開與耐久範圍，而無法查詢的外部服務仍只能留給人判斷。
- **保留完整控制平面**：得到日後可同時管多件工作、等待與收拾子工作的容量；賠掉的是要先背負一整套本輪尚未出現實際需求的設計與驗證成本。
