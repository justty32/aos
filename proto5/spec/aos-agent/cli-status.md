← [aos-agent](README.md)｜[spec 總導航](../README.md)

## 1.3 `status`：現在怎樣了（09-24 試玩 r2 補）

唯讀、不要 `AOS_KERNEL_HOME`、壞了什麼都照樣印（它是診斷工具）。家不是 agent 家＝`NotAnAgent` 退 1，其餘退 0。每項一行：

（09-24 試玩 r3 補）**第一行 `health <一句>`** 說現在正不正常，先中先印：K 知道且 [kernel 健康](../kernel/README.md)不是 ok＝`kernel 家有問題：<kernel 那句>`（停機中＝`kernel 停機中（…）`）；沒登記＝`沒登記（aos-agent start --target <dir>）`；
（09-24 fix-r4 補）手動暫停＝`手動暫停（aos-agent continue --target <dir>）`，同時也在連敗暫停就寫 `手動暫停＋連敗暫停（修好原因後 aos-agent continue --target <dir>）`；連敗暫停門還沒開＝`連敗暫停（aos-agent continue --target <dir>）`；K 帳本那筆 `bad`＝`kernel 判壞了（看 <dir>/log/agent.err）`；（09-24 fix-r5 補，下面三種都不再印 `ok`）kernel 健康是 `recovering`＝`恢復中（<kernel health 那句，例如「池 P 少 N 顆」或「搬池中：池 P」）`；連敗未滿 3 次（`errors` 1、2）＝`重試中（連敗 N/3）`；`continue` 解了連敗暫停、還沒等到一次成功（家裡有 `resumed`，見 §1.4）＝`已解除暫停，等下一次成功`；info／state 讀不到＝`家的設定讀不到（看下面 info／state 行）`；其他＝`ok`。
（09-24 fix-r5 補）所以 kernel 那邊只有 `recovering` 不歸進「kernel 家有問題」：cpu 死了 daemon 會自己重拉，排在暫停、`bad` 之後。

| 行 | 印什麼 |
|---|---|
| `agent` | 家的絕對路徑；info 讀驗錯另一行 `info bad：<代號>: <白話>`；（access-impl）[access 檔](access.md)壞了另一行 `access bad：<代號>: <白話>…` |
| `state` | `state`、`errors`；（09-24 試玩 r3 補）連敗暫停中不印會誤導的 `errors 0`，改印 `連敗暫停中（已連敗 3 次）`；（09-24 fix-r4 補）手動暫停中行尾加 `手動暫停中（<paused 檔的時間>）`，兩種同時就兩段都印；state.json 讀驗錯＝`state bad：…`，後面靠 state 的行略過（手動暫停照樣在 health 行看得到） |
| `batch` | 沒有＝`-`；有＝kind、送出幾個／共幾個（`sent:false` 時寫送件中）、收回幾個 |
| `wait` | 每道門一行：路徑、到了沒；連敗暫停的門（agent 家的 `continue-*.json`）附 `（連敗暫停，aos-agent continue）`；（09-24 試玩 r3 改）完整 `touch <絕對路徑>` 只在 `-v`／`--verbose` 與 `--json` 出現 |
| `input` | `input` 指到、還沒收的檔數與路徑；`intake` 做到一半另一行 |
| `error` | （09-24 試玩 r3 改）**這次卡住的原因**：連敗暫停中＝導致暫停的那行 `engine:`（agent.err 裡最後一個 `stuck:` 之前最近的一行，去掉前綴），下一行 `已連敗 3 次，等 aos-agent continue --target <dir>`；還在連敗沒到 3 次＝最近的 `engine:` 行＋`已連敗 N 次（3 次會暫停）`；K 帳本那筆 `fails` > 0 或 `bad`＝agent.err 最後一行；都不是＝`（無）`，agent.err 有內容就另印 `last-error  （已恢復） <MM-DD HH:MM:SS>  <最後一行的短版>`（時間是 agent.err 的修改時間；09-24 fix-r5 改：標記移到最前面；家裡有 `resumed` 時標記改成 `（已解除暫停，等下一次成功）`）。
短版（09-24 fix-r5 補）：去掉開頭的 `aos-agent: `、舊格式 stuck 行的 `touch <路徑> 繼續` 改寫成 `修好原因後 aos-agent continue --target <dir>`、批次名（`aw-<資料夾名>-<數字>-<數字>…`）縮成 `aw-…`、超過 120 字截斷並加 `…（-v 看全文）`；`-v` 印原文，`--json` 的 `last_error` 也是原文。`-v` 另印一行 `stuck` 原文 |
| `kernel` | K 帳本裡 `agent-<資料夾名>` 那筆的 status／runs／fails；K 取 `AOS_KERNEL_HOME`，沒設就用 `tick.json` 記的，都沒有＝（09-24 試玩 r3 改）`kernel 從沒 start 過（沒設 AOS_KERNEL_HOME、也沒 tick.json）；aos-agent start --target <dir>`；帳本讀不到、沒登記各有一句 |

`--json` 印一行 JSON，同樣的資訊（鍵：`dir`、`info_error`、`state_error`、`access_error`、`state`、`errors`、`batch`、`waits`、`pending_inputs`、`intake`、`last_error`、`kernel`）。
（09-24 試玩 r3 補）另有 `health`（`{code, message}`，code：`ok`／`kernel`／`unregistered`／`manual_paused`（09-24 fix-r4 補）／`paused`／`bad`／`config`）、`current_error`（上表 error 欄的原因，沒有＝null）、`streak`（連敗次數，暫停中＝3）、`paused`（**連敗**暫停）、`last_error_time`（ISO 時間或 null）；`last_error` 照舊是最後一行。
（09-24 fix-r4 補）`manual_paused`（布林）、`manual_paused_since`（`paused` 檔的修改時間，ISO，沒暫停＝null）。
（09-24 fix-r5 補）`resumed`（布林）、`resumed_since`（`resumed` 檔的修改時間，ISO，沒有＝null）；health 的 code 多三個：`recovering`、`retrying`、`resuming`。

## 1.4 `continue`：解除暫停（09-24 試玩 r2 補；fix-r4 改成兩種都解）

（09-24 fix-r4 補）先解手動暫停：家裡有 `paused` 就刪掉、印 `continued: 解除手動暫停`。然後解連敗暫停：
讀 state，找 `waits` 裡帶 `consume`、指到 agent 家 `continue-*.json`、檔還不在的門（§9 加的那種），逐一建那個檔（空檔），每個印 `continued: touched <絕對路徑>`、退 0；
下一格 tick 開門、搬進 `done/`。檔已在（touch 過、還沒被收）＝印「已經 touch 過，等下一格 tick」、退 0；兩種都沒有＝印 `沒有在暫停`、退 0。
（09-24 fix-r5 補）**兩階段**：要建門檔之前先在家裡放 `resumed`（先放再建：門開之前 tick 不會重問，所以成功結清刪 `resumed` 一定在這之後，不會被蓋回去；門檔已在＝上次 continue 已放過，不再放）（寫一行 `resumed at <ISO 時間>`，`.tmp` 再 rename），最後印一行 `已解除暫停，等下一次成功（aos-agent status --target <dir> 看）`；
`status` 在 `resumed` 還在時標「已解除暫停，等下一次成功」。下一次 think **成功**結清時 tick 刪掉 `resumed`（§7），這之後才標「已恢復」。只解手動暫停不放 `resumed`（手動暫停不是失敗）。

**`continue --all`**（09-24 fix-r5 補）：llm.json 是 kernel 的 llm cpu 共用的，一壞所有正在說話的 agent 會一起連敗暫停，這個一次救回。
K＝`AOS_KERNEL_HOME`（沒設＝用法錯 2）；讀 K 帳本（讀不到＝退 1），`procs` 裡名字是 `agent-` 開頭、不是 once、`target` 檔名是 `tick.json` 的，它所在的資料夾就是一個 agent 家（沒 `info.json` 或字面是別種家就跳過）。
每個家各印一行 `<行程名>  <家>  <結果>`：暫停中（手動或連敗）就照上面解，結果寫 `解除手動暫停`／`解除連敗暫停`／兩者；沒在暫停＝`沒在暫停`；state 讀不了＝`跳過：<原因>`。最後一行 `continued <解了幾個>／<登記的 agent 幾個>`。有跳過的退 1，否則退 0；一個都沒登記＝印 `K 帳本裡沒有登記的 agent`、退 0。
別人加的門不碰。家不是 agent 家（沒有 `info.json`）＝`NotAnAgent`、退 1；state 讀驗錯＝退 1（手動暫停已經先解掉了）。不拿 tick 鎖：只刪一個檔、建幾個檔，不寫 `state.json`。

## 1.6 `pause`：手動暫停（09-24 fix-r4 補）

家還登記在 kernel、kernel 照樣每格叫 `tick`，但 `tick` 看到家裡有 **`paused`** 這個檔就什麼都不做、直接退 0（§2 第 0 步）——不收輸入、不送批、不收回音、不清檔；
在途的工作照跑，回音留在 K，`continue` 之後再收。

`pause`：家要有 `info.json`（不讀驗內容，設定壞了也停得住；沒有、或字面寫著別種家＝`NotAnAgent`、退 1）；建 `paused`（寫一行 `paused at <ISO 時間>`，`.tmp` 再 rename），印 `paused <dir>（aos-agent continue --target <dir> 解除）`、退 0。
已經有＝印 `已經暫停了`、退 0。不拿 tick 鎖、不寫 `state.json`：只放一個檔，所以不會跟正在跑的那格互相蓋掉；正在跑的那格照樣做完，下一格起才停。
落地成一個檔而不是 `state.json` 的一格，是因為 `state.json` 只有 tick 寫（§13）；外人改它會跟正在跑的那格互相蓋掉。
`paused` 不是 `.json`，所以就算 `input` 指到家本身也不會被當成輸入收走。
