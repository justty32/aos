# 待答問題 — 結構索引

← [workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[原路徑指標](../OPEN-QUESTIONS.md)

本資料夾＝把七場研討會裡「使用者尚未拍板」的問題去重、彙整成的待答清單，附候選答案。
**本檔只做導航**，題目本身在下面十三個檔裡。第 1–24 題的分組與
`../background/questions-*.md` 那八份白話導讀一一對應，每個檔頭都有連結；第 25–37 題目前沒有導讀。

計數方式：〈核心行程與子行程〉的四位參與者，與其後六場沿用的四位參與者是兩批不同的人；同一人跨場重問只算一位。以下只保留使用者既有表態後仍未解的部分。

## 擋住事情的（第 1–24 題）

| 檔案 | 裡面有什麼 | 什麼時候看 |
|---|---|---|
| [direction.md](direction.md) | **第 1–3 題**：workflows 哪裡不好用、近期 core 要回撤到哪裡、第一個產品體驗是哪一邊 | 要決定先做什麼、scope 收多小時 |
| [host-and-trust.md](host-and-trust.md) | **第 4–6 題**：模型與工具的權限、第一個整合入口、golden slice 用哪支 agent CLI | 要讓模型輸出真的產生作用之前 |
| [deliver.md](deliver.md) | **第 7–9 題**：`aos deliver` 的命令形狀、key 保證什麼、成功／錯誤／退出碼 | 要動手寫 Deliver CLI／skill／MCP schema 時 |
| [workflow-state.md](workflow-state.md) | **第 10–11 題**：workflows 活狀態的真源放哪、人怎麼改它 | 要做 `wf` runtime 的磁碟版面時 |
| [reliability.md](reliability.md) | **第 12–14 題**：遠端 unknown 怎麼辦、crash 承諾到哪一級、`--durable` 承諾什麼 | 要跑無人值守 loop、或定恢復契約時 |
| [workflow-policy.md](workflow-policy.md) | **第 15–17 題**：完成史留不留、template 追不追上游、哪些 workflow 要自動喚醒 | 要決定 `wf done`／升級／tick 的政策時 |
| [agent-context.md](agent-context.md) | **第 18、19、24 題**：agent 的 stdin context 從哪來、要不要用 agent session、首版工具集合有幾支 | 要接第一個 coding agent 宿主時 |
| [child-work.md](child-work.md) | **第 20–23 題**：子工作成果何時進父世界、父怎麼等、子失敗怎麼走、序言／尾聲失敗算不算一回合 | 要開第二個 world 或 lane 之前 |

## 可以慢慢想的（第 25–37 題）

| 檔案 | 裡面有什麼 | 什麼時候看 |
|---|---|---|
| [core-primitives.md](core-primitives.md) | **第 25–27 題**：Publish 要不要公開、Effect 放 core 還是 adapter、平行 join／reconcile 放哪 | 近期 scope 不回撤、要自動 agent loop 時 |
| [kernel-provisioning.md](kernel-provisioning.md) | **第 28–29 題**：`.runi` 保存哪一版 kernel 現場、本地 kernel 由誰建立與升級 | 要真的把 `kernel.json` 做出來時 |
| [multi-world.md](multi-world.md) | **第 30–32 題**：非 UUID 的 handle 用什麼、一個 exec 推多世界是哪種、分支世界要不要做 | 出現第二個 world 之後 |
| [external-processors.md](external-processors.md) | **第 33–34 題**：外部處理器完成後交什麼、怎麼證明它讀對 ABI | 有第二個實作要接磁碟 ABI 時 |
| [workflows-scope.md](workflows-scope.md) | **第 35–37 題**：task 何時升成 world／lane、inbox 機械化到哪、workflows module 管到哪一層 | 要把 `wf/` 變成 aos module 時 |

## 題號速查

別處常用 `OPEN-QUESTIONS.md#<題號>-<標題>` 的形式連過來，這張表是題號 → 現在的落點。

| # | 題目 |
|---|---|
| **1** | [workflows 到底是哪一種不好用？](direction.md#1-workflows-到底是哪一種不好用) |
| **2** | [近期 core 要回撤到哪裡？](direction.md#2-近期-core-要回撤到哪裡) |
| **3** | [第一個產品體驗是哪一邊？](direction.md#3-第一個產品體驗是哪一邊) |
| **4** | [模型與工具先給到什麼權限？](host-and-trust.md#4-模型與工具先給到什麼權限) |
| **5** | [第一個整合入口先驗哪個？](host-and-trust.md#5-第一個整合入口先驗哪個) |
| **6** | [golden slice 先用哪支真 agent CLI？](host-and-trust.md#6-golden-slice-先用哪支真-agent-cli) |
| **7** | [`aos deliver` 第一版命令長什麼樣？](deliver.md#7-aos-deliver-第一版命令長什麼樣) |
| **8** | [Deliver 的 key 到底保證什麼？](deliver.md#8-deliver-的-key-到底保證什麼) |
| **9** | [Deliver 的成功、錯誤與退出碼採哪套？](deliver.md#9-deliver-的成功錯誤與退出碼採哪套) |
| **10** | [workflows 活狀態的真源放哪裡？](workflow-state.md#10-workflows-活狀態的真源放哪裡) |
| **11** | [人怎麼修改 workflows 活狀態？](workflow-state.md#11-人怎麼修改-workflows-活狀態) |
| **12** | [遠端效果變成 unknown 時預設怎麼辦？](reliability.md#12-遠端效果變成-unknown-時預設怎麼辦) |
| **13** | [crash 要承諾到哪一級？](reliability.md#13-crash-要承諾到哪一級) |
| **14** | [`--durable` 與 fsync 承諾什麼？](reliability.md#14---durable-與-fsync-承諾什麼) |
| **15** | [SESSION-LOG／WAIT_USER 要不要保留完成史？](workflow-policy.md#15-session-logwait_user-要不要保留完成史) |
| **16** | [template 安裝後還追不追上游？](workflow-policy.md#16-template-安裝後還追不追上游) |
| **17** | [哪些 workflow 需要自動喚醒？](workflow-policy.md#17-哪些-workflow-需要自動喚醒) |
| **18** | [stdout→stdin 的穩定 context 從哪裡來？](agent-context.md#18-stdoutstdin-的穩定-context-從哪裡來) |
| **19** | [agent session 要先求可攜還是續談速度？](agent-context.md#19-agent-session-要先求可攜還是續談速度) |
| **20** | [子工作成果何時進父世界？](child-work.md#20-子工作成果何時進父世界) |
| **21** | [父要怎麼等子工作？](child-work.md#21-父要怎麼等子工作) |
| **22** | [子工作失敗時父怎麼走？](child-work.md#22-子工作失敗時父怎麼走) |
| **23** | [kernel 序言／尾聲失敗怎麼算一回合？](child-work.md#23-kernel-序言尾聲失敗怎麼算一回合) |
| **24** | [coding agent 的首版 runtime tool set 有幾支？](agent-context.md#24-coding-agent-的首版-runtime-tool-set-有幾支) |
| **25** | [Publish 要不要成為公開 API？](core-primitives.md#25-publish-要不要成為公開-api) |
| **26** | [Effect 放 core 還是 adapter？](core-primitives.md#26-effect-放-core-還是-adapter) |
| **27** | [平行 join／reconcile 放哪裡？](core-primitives.md#27-平行-joinreconcile-放哪裡) |
| **28** | [`.runi` 要保存哪一版 kernel 現場？](kernel-provisioning.md#28-runi-要保存哪一版-kernel-現場) |
| **29** | [每份本地 kernel 由誰建立與升級？](kernel-provisioning.md#29-每份本地-kernel-由誰建立與升級) |
| **30** | [非 UUID 的 handle 用什麼？](multi-world.md#30-非-uuid-的-handle-用什麼) |
| **31** | [「一個 exec 推多世界」具體是哪種？](multi-world.md#31-一個-exec-推多世界具體是哪種) |
| **32** | [要不要把分支世界做成正式方向？](multi-world.md#32-要不要把分支世界做成正式方向) |
| **33** | [外部處理器完成後要交什麼？](external-processors.md#33-外部處理器完成後要交什麼) |
| **34** | [怎麼證明外部處理器讀對 ABI？](external-processors.md#34-怎麼證明外部處理器讀對-abi) |
| **35** | [task 何時升成 world／lane？](workflows-scope.md#35-task-何時升成-worldlane) |
| **36** | [inbox 要機械化到哪裡？](workflows-scope.md#36-inbox-要機械化到哪裡) |
| **37** | [workflows module 管到哪一層？](workflows-scope.md#37-workflows-module-管到哪一層) |
