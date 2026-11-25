直接叫 API 的 agent（agent-fsm）也認 `/status`、`/usage`、`/exit` 了：在 idle 收信時認，不叫模型，回一則 `[aos] slash: …`（線 eca-aos-templates-1125b，範本位子做；格程式在 py/aos/apps/agent_fsm/，eca-aos 放行跨範圍）。

# API agent 也認 /status、/usage、/exit（11-25）

← [2026-11-25](README.md)｜前一件：[API agent 也認 /clear（11-21）](../21/api-agent-clear-1121.md)

## 使用者原話

11-25 早答舊題（eca-aos 轉）：「18.要認」——API agent 也認 /status、/usage、/exit。使用者沒空定細節，eca-aos 給了推薦、叫範本位子照做、寫進「替使用者定的」。

## 做了什麼

- `py/aos/apps/agent_fsm/slash.py`（新）：`which()` 認字、`status()`、`usage()`、`exit_note()` 拼回答字。
- `py/aos/apps/agent_fsm/idle.py`：收信時跟 `/clear` 同一個分支認這三個字（一定自己一批）；`slash_letter()` 寫一問一答、收信；`exit_self()` 叫 `aos-agent ctl who` 與 `ctl stop --target 自己 --no-wait`。檔頭與 `--help` 補說明。
- 測試 `templates/tests/agent-fsm/test_slash_cmds.py`（8 條）。
- 文件：`templates/docs/02-agent-fsm.md` 新一節「寄 /status、/usage、/exit」、格表加 `slash.py`；`templates/agents/agent-fsm/README.md` 一段（`starts/start-api/agents/ann/README.md` 開頭是它的原樣，一起改）。知識庫那半由 kb 位子跟（句子在回 eca-aos 的信裡）。
- 要 `install.py` 才生效（格程式在 lib/）：eca-aos 跑。

## 替使用者定的

1. **放哪、怎麼認**：照 `/clear`——內容去頭尾空白剛好是這個字、一定自己一批（前面的信先答）、在 idle 做、不叫腦、不跑 `before_queue`／`after_queue`。後面帶字＝普通的信。eca 那邊也是「一封剛好是這個字的信自己一批」。
2. **記不記這一問一答**：記（user 那封帶 `aos.letter`，assistant 帶 `aos.answer_to` 與 `aos.slash: "/status"` 等），理由同 /clear：`listen` 照信名配回答。代價是模型之後看得到這兩則。
3. **/status 報什麼**：eca-aos 推薦的五樣（model、history 則數、goal、compact phase、冷卻）加 queue 裡還有幾封等著（API 這邊沒有 eca 的對話 id、畫面、transcript，換成這個）。model＝定義的 `llm.json` 疊 stack 那份（同 brain）；沒設 model 寫「not set: the llm kernel's default pack」。
4. **/usage 報什麼**：只報手上有的，不發明介面——`observed.jsonl` 裡 kind think／compact、有 usage 的列：次數、最上層整數欄各自加總、最後一次（欄名照端點原樣，不換算）；context 讀數用 `aos.agentlib.context_use`（`context_wrap` 同一套）。llm kernel 沒有額度或速率限制介面，回答明說沒有，並說包的 `budget` 用完只會以 `BudgetMissing` 出現。
5. **/exit＝stop，不是 sleep**：查了語意——睡著＝daemon 收掉行程，信箱不會叫醒它（`aos/mailbox.md`：信不會自己叫醒 agent），只有 `wake` 或 daemon 重啟；停下＝這一輪做完停，只有 `start`，daemon 重啟也不叫醒。兩種都不會因為來信自己起來，照 eca-aos 的條件（sleep 收信不醒就改 stop）選 stop；「離開」也比較像不會被重啟叫回來。回答說怎麼再起（`aos-agent ctl start <名>`）、信照樣排在 queue。指令跟工具 `self_ctl` 的 stop 一樣（`ctl who` 認自己、`--no-wait`、在 `$AOS_WS` 跑），先送 stop 再寫回答：這一步結束才停，回答來得及寫；送不出去＝回答寫 `could not stop (<錯誤行>); still running`、照常跑。
6. **goal**：active 的話回答之後 idle 照常接 goal 提醒（同 /clear）；`/exit` 送成時這一步結束就停，提醒接進 history 但不會被答，下次 start 才接著做。

## 怎麼驗

見回 eca-aos 的信（乾淨複本、install.py、`tests/agent-fsm` 全部與 `test_slash_cmds` 8 條）。沒叫真模型；`/exit` 用假的 `aos-agent` 驗叫了哪兩條指令、在哪個目錄、送不出去時的回答，沒在真的 daemon 上停過。
