# 第 1 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[下一份 →](round-2.md)

## 1. 這一輪到底發生了什麼

用現成的 aos 把「想一步、做一步、把結果交回去」連跑三次，正常時跑得完；半路被停掉後要人查現場、搬檔或重排剩下的事。有一種情況光看這台電腦永遠無法知道外面到底做了沒。沒有出現需要同時照看的第二件工作。

## 2. 冒出來的新詞

- **`.runi`**：`aos exec <world>` 取走 `.aos/inst.json` 後改成的 `.aos/inst.json.runi`；只能說「這整包沒正常收尾」。其餘詞（Publish、Deliver、Effect、`unknown`、receipt）見 [BACKGROUND](../../../../workshop/BACKGROUND.md)，現況見 [第 3 輪](round-3.md)。

## 3. 看到的錯誤訊息各是什麼意思

- `aos exec: refusing ... .aos/inst.json.runi already exists`、`restart_exit=3`：aos 看到上次沒收好的整包現場，不知哪些已做過，刻意拒絕自動再跑、等人處理。
- `...=present` 與 `...=missing` 同時出現：有做過的跡象，但收尾不全。
- exit `137`／`Killed`：被 `kill -9` 強制砍掉（128＋9）。exit `130`：Ctrl-C 中止（128＋2）。
- `rejected_exit=70` 與 `accepted_exit=70`：本機沒收到可信的答案，外部收了或沒收，本機看起來都一樣。
- 重開回 `0` 但 `result=missing`／`final_exists=no`：命令沒找到可執行的東西並正常結束，不代表整條工作完成。
- `temp=yes ready=no`：內容停在草稿名，aos 故意不讀；要人檢查後手動改名才救回來。
- `ledger_lines=1`／`0` 但兩份本機現場比對無差異：外面一份收到、一份沒收到，本機分不出來。
- `provider_ledger_lines=2`：原本那次其實已被外面收到，不查就盲目重試又做了一次。
- `aos_after_tool_group_kill_exit=0` 但 `tool.exit=137`、`schedule.exit=66`：aos 只報「這包處理完了」，包裡工具被砍、下一步失敗不會讓它改報失敗。
- 錯名的 `delivery-turn1.timestamp.pid.json` 原封不動、`aos exec` 連續回 0：檔名多了點就不符取件規則，現行實作安靜略過，沒有錯誤訊息。

## 4. 所以呢

三個選項（只留最小 Deliver／Publish、Deliver、Effect 三項／完整控制平面）各自的代價，以三輪跑完的版本為準，見 [第 3 輪〈所以呢〉](round-3.md)。
