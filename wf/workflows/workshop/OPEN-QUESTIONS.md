# 尚未回答的問題
← [workshop](README.md)

**本檔已拆成 [OPEN-QUESTIONS/](OPEN-QUESTIONS/README.md)——一組一個檔。** 這裡只留導航。

別處是用 `OPEN-QUESTIONS.md#<題號>-<標題>` 連過來的話，看下表的題號找到檔；
**三十七條題號逐條速查在 [OPEN-QUESTIONS/README.md](OPEN-QUESTIONS/README.md#題號速查)**。

| 檔案 | 裡面有什麼 | 什麼時候看 |
|---|---|---|
| [direction.md](OPEN-QUESTIONS/direction.md) | **第 1–3 題**：workflows 哪裡不好用、近期 core 要回撤到哪裡、第一個產品體驗是哪一邊 | 要決定先做什麼、scope 收多小時 |
| [host-and-trust.md](OPEN-QUESTIONS/host-and-trust.md) | **第 4–6 題**：模型與工具的權限、第一個整合入口、golden slice 用哪支 agent CLI | 要讓模型輸出真的產生作用之前 |
| [deliver.md](OPEN-QUESTIONS/deliver.md) | **第 7–9 題**：`aos deliver` 的命令形狀、key 保證什麼、成功／錯誤／退出碼 | 要動手寫 Deliver CLI／skill／MCP schema 時 |
| [workflow-state.md](OPEN-QUESTIONS/workflow-state.md) | **第 10–11 題**：workflows 活狀態的真源放哪、人怎麼改它 | 要做 `wf` runtime 的磁碟版面時 |
| [reliability.md](OPEN-QUESTIONS/reliability.md) | **第 12–14 題**：遠端 unknown 怎麼辦、crash 承諾到哪一級、`--durable` 承諾什麼 | 要跑無人值守 loop、或定恢復契約時 |
| [workflow-policy.md](OPEN-QUESTIONS/workflow-policy.md) | **第 15–17 題**：完成史留不留、template 追不追上游、哪些 workflow 要自動喚醒 | 要決定 `wf done`／升級／tick 的政策時 |
| [agent-context.md](OPEN-QUESTIONS/agent-context.md) | **第 18、19、24 題**：agent 的 stdin context 從哪來、要不要用 agent session、首版工具集合有幾支 | 要接第一個 coding agent 宿主時 |
| [child-work.md](OPEN-QUESTIONS/child-work.md) | **第 20–23 題**：子工作成果何時進父世界、父怎麼等、子失敗怎麼走、序言／尾聲失敗算不算一回合 | 要開第二個 world 或 lane 之前 |
| [core-primitives.md](OPEN-QUESTIONS/core-primitives.md) | **第 25–27 題**：Publish 要不要公開、Effect 放 core 還是 adapter、平行 join／reconcile 放哪 | 近期 scope 不回撤、要自動 agent loop 時 |
| [kernel-provisioning.md](OPEN-QUESTIONS/kernel-provisioning.md) | **第 28–29 題**：`.runi` 保存哪一版 kernel 現場、本地 kernel 由誰建立與升級 | 要真的把 `kernel.json` 做出來時 |
| [multi-world.md](OPEN-QUESTIONS/multi-world.md) | **第 30–32 題**：非 UUID 的 handle 用什麼、一個 exec 推多世界是哪種、分支世界要不要做 | 出現第二個 world 之後 |
| [external-processors.md](OPEN-QUESTIONS/external-processors.md) | **第 33–34 題**：外部處理器完成後交什麼、怎麼證明它讀對 ABI | 有第二個實作要接磁碟 ABI 時 |
| [workflows-scope.md](OPEN-QUESTIONS/workflows-scope.md) | **第 35–37 題**：task 何時升成 world／lane、inbox 機械化到哪、workflows module 管到哪一層 | 要把 `wf/` 變成 aos module 時 |

## 題號 → 現在的落點

下表把原本 `OPEN-QUESTIONS.md#<題號>-<標題>` 的錨點**全部重新宣告在這裡**，
所以舊連結仍然有效——它會捲到下表對應的那一列，再由該列連到真正的內文。

| 題 | 現在在哪 |
|---|---|
| 1. workflows 到底是哪一種不好用？<a id="1-workflows-到底是哪一種不好用"></a> | [direction.md](OPEN-QUESTIONS/direction.md#1-workflows-到底是哪一種不好用) |
| 2. 近期 core 要回撤到哪裡？<a id="2-近期-core-要回撤到哪裡"></a> | [direction.md](OPEN-QUESTIONS/direction.md#2-近期-core-要回撤到哪裡) |
| 3. 第一個產品體驗是哪一邊？<a id="3-第一個產品體驗是哪一邊"></a> | [direction.md](OPEN-QUESTIONS/direction.md#3-第一個產品體驗是哪一邊) |
| 4. 模型與工具先給到什麼權限？<a id="4-模型與工具先給到什麼權限"></a> | [host-and-trust.md](OPEN-QUESTIONS/host-and-trust.md#4-模型與工具先給到什麼權限) |
| 5. 第一個整合入口先驗哪個？<a id="5-第一個整合入口先驗哪個"></a> | [host-and-trust.md](OPEN-QUESTIONS/host-and-trust.md#5-第一個整合入口先驗哪個) |
| 6. golden slice 先用哪支真 agent CLI？<a id="6-golden-slice-先用哪支真-agent-cli"></a> | [host-and-trust.md](OPEN-QUESTIONS/host-and-trust.md#6-golden-slice-先用哪支真-agent-cli) |
| 7. `aos deliver` 第一版命令長什麼樣？<a id="7-aos-deliver-第一版命令長什麼樣"></a> | [deliver.md](OPEN-QUESTIONS/deliver.md#7-aos-deliver-第一版命令長什麼樣) |
| 8. Deliver 的 key 到底保證什麼？<a id="8-deliver-的-key-到底保證什麼"></a> | [deliver.md](OPEN-QUESTIONS/deliver.md#8-deliver-的-key-到底保證什麼) |
| 9. Deliver 的成功、錯誤與退出碼採哪套？<a id="9-deliver-的成功錯誤與退出碼採哪套"></a> | [deliver.md](OPEN-QUESTIONS/deliver.md#9-deliver-的成功錯誤與退出碼採哪套) |
| 10. workflows 活狀態的真源放哪裡？<a id="10-workflows-活狀態的真源放哪裡"></a> | [workflow-state.md](OPEN-QUESTIONS/workflow-state.md#10-workflows-活狀態的真源放哪裡) |
| 11. 人怎麼修改 workflows 活狀態？<a id="11-人怎麼修改-workflows-活狀態"></a> | [workflow-state.md](OPEN-QUESTIONS/workflow-state.md#11-人怎麼修改-workflows-活狀態) |
| 12. 遠端效果變成 unknown 時預設怎麼辦？<a id="12-遠端效果變成-unknown-時預設怎麼辦"></a> | [reliability.md](OPEN-QUESTIONS/reliability.md#12-遠端效果變成-unknown-時預設怎麼辦) |
| 13. crash 要承諾到哪一級？<a id="13-crash-要承諾到哪一級"></a> | [reliability.md](OPEN-QUESTIONS/reliability.md#13-crash-要承諾到哪一級) |
| 14. `--durable` 與 fsync 承諾什麼？<a id="14---durable-與-fsync-承諾什麼"></a> | [reliability.md](OPEN-QUESTIONS/reliability.md#14---durable-與-fsync-承諾什麼) |
| 15. SESSION-LOG／WAIT_USER 要不要保留完成史？<a id="15-session-logwait_user-要不要保留完成史"></a> | [workflow-policy.md](OPEN-QUESTIONS/workflow-policy.md#15-session-logwait_user-要不要保留完成史) |
| 16. template 安裝後還追不追上游？<a id="16-template-安裝後還追不追上游"></a> | [workflow-policy.md](OPEN-QUESTIONS/workflow-policy.md#16-template-安裝後還追不追上游) |
| 17. 哪些 workflow 需要自動喚醒？<a id="17-哪些-workflow-需要自動喚醒"></a> | [workflow-policy.md](OPEN-QUESTIONS/workflow-policy.md#17-哪些-workflow-需要自動喚醒) |
| 18. stdout→stdin 的穩定 context 從哪裡來？<a id="18-stdoutstdin-的穩定-context-從哪裡來"></a> | [agent-context.md](OPEN-QUESTIONS/agent-context.md#18-stdoutstdin-的穩定-context-從哪裡來) |
| 19. agent session 要先求可攜還是續談速度？<a id="19-agent-session-要先求可攜還是續談速度"></a> | [agent-context.md](OPEN-QUESTIONS/agent-context.md#19-agent-session-要先求可攜還是續談速度) |
| 24. coding agent 的首版 runtime tool set 有幾支？<a id="24-coding-agent-的首版-runtime-tool-set-有幾支"></a> | [agent-context.md](OPEN-QUESTIONS/agent-context.md#24-coding-agent-的首版-runtime-tool-set-有幾支) |
| 20. 子工作成果何時進父世界？<a id="20-子工作成果何時進父世界"></a> | [child-work.md](OPEN-QUESTIONS/child-work.md#20-子工作成果何時進父世界) |
| 21. 父要怎麼等子工作？<a id="21-父要怎麼等子工作"></a> | [child-work.md](OPEN-QUESTIONS/child-work.md#21-父要怎麼等子工作) |
| 22. 子工作失敗時父怎麼走？<a id="22-子工作失敗時父怎麼走"></a> | [child-work.md](OPEN-QUESTIONS/child-work.md#22-子工作失敗時父怎麼走) |
| 23. kernel 序言／尾聲失敗怎麼算一回合？<a id="23-kernel-序言尾聲失敗怎麼算一回合"></a> | [child-work.md](OPEN-QUESTIONS/child-work.md#23-kernel-序言尾聲失敗怎麼算一回合) |
| 25. Publish 要不要成為公開 API？<a id="25-publish-要不要成為公開-api"></a> | [core-primitives.md](OPEN-QUESTIONS/core-primitives.md#25-publish-要不要成為公開-api) |
| 26. Effect 放 core 還是 adapter？<a id="26-effect-放-core-還是-adapter"></a> | [core-primitives.md](OPEN-QUESTIONS/core-primitives.md#26-effect-放-core-還是-adapter) |
| 27. 平行 join／reconcile 放哪裡？<a id="27-平行-joinreconcile-放哪裡"></a> | [core-primitives.md](OPEN-QUESTIONS/core-primitives.md#27-平行-joinreconcile-放哪裡) |
| 28. `.runi` 要保存哪一版 kernel 現場？<a id="28-runi-要保存哪一版-kernel-現場"></a> | [kernel-provisioning.md](OPEN-QUESTIONS/kernel-provisioning.md#28-runi-要保存哪一版-kernel-現場) |
| 29. 每份本地 kernel 由誰建立與升級？<a id="29-每份本地-kernel-由誰建立與升級"></a> | [kernel-provisioning.md](OPEN-QUESTIONS/kernel-provisioning.md#29-每份本地-kernel-由誰建立與升級) |
| 30. 非 UUID 的 handle 用什麼？<a id="30-非-uuid-的-handle-用什麼"></a> | [multi-world.md](OPEN-QUESTIONS/multi-world.md#30-非-uuid-的-handle-用什麼) |
| 31. 「一個 exec 推多世界」具體是哪種？<a id="31-一個-exec-推多世界具體是哪種"></a> | [multi-world.md](OPEN-QUESTIONS/multi-world.md#31-一個-exec-推多世界具體是哪種) |
| 32. 要不要把分支世界做成正式方向？<a id="32-要不要把分支世界做成正式方向"></a> | [multi-world.md](OPEN-QUESTIONS/multi-world.md#32-要不要把分支世界做成正式方向) |
| 33. 外部處理器完成後要交什麼？<a id="33-外部處理器完成後要交什麼"></a> | [external-processors.md](OPEN-QUESTIONS/external-processors.md#33-外部處理器完成後要交什麼) |
| 34. 怎麼證明外部處理器讀對 ABI？<a id="34-怎麼證明外部處理器讀對-abi"></a> | [external-processors.md](OPEN-QUESTIONS/external-processors.md#34-怎麼證明外部處理器讀對-abi) |
| 35. task 何時升成 world／lane？<a id="35-task-何時升成-worldlane"></a> | [workflows-scope.md](OPEN-QUESTIONS/workflows-scope.md#35-task-何時升成-worldlane) |
| 36. inbox 要機械化到哪裡？<a id="36-inbox-要機械化到哪裡"></a> | [workflows-scope.md](OPEN-QUESTIONS/workflows-scope.md#36-inbox-要機械化到哪裡) |
| 37. workflows module 管到哪一層？<a id="37-workflows-module-管到哪一層"></a> | [workflows-scope.md](OPEN-QUESTIONS/workflows-scope.md#37-workflows-module-管到哪一層) |
