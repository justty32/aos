# 待答問題：world handle、多世界與分支世界
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)

第 30–32 題：非 UUID 的 handle 用什麼、「一個 exec 推多世界」具體是哪種、要不要把分支世界做成正式方向。

## 可以慢慢想的

### 30. 非 UUID 的 handle 用什麼？

**問題｜**既然不綁 UUID，world／子工作 handle 要直接用相對路徑，還是用父域內的 name＋generation？  
**為什麼卡著｜**兩者都符合非 UUID，但同名刪除重建後，舊 receipt／join 是否會誤投的結果不同。  
**在哪問過｜**〈四個懸而未決的設計選擇〉；4 位獨立地提出非 UUID 後的兩種殘留方案。  
**候選答案｜**

- **正規相對路徑**——rename 就是改址、copy 是新 world；metadata 最少。
- **父域 name＋generation**——同名新目錄不收上一代結果；跨父域要 detach／adopt。

### 31. 「一個 exec 推多世界」具體是哪種？

**問題｜**未來真的推多世界時，要同一 OS 行程內 multiplex、一個命令接多個 world，還是由命令樹逐個呼叫單世界 exec？  
**為什麼卡著｜**使用者已表態傾向一個 exec 推多世界，但這三種對 root fd、cwd、退出碼與故障隔離的要求不同；回頭審視建議先等第二個 world。  
**在哪問過｜**〈四個懸而未決的設計選擇〉；4 位各給了不同實作。  
**候選答案｜**

- **同一 OS 行程 multiplex**——抽 `advance_once(World&)`，所有內部 I/O 改 root fd／`*at`。
- **一個命令接多個 world**——`aos exec w1 w2` 逐 root fd 推進，另定 busy／失敗與總退出碼。
- **命令樹逐個單世界 exec**——父批次呼叫多個 `aos exec <path>`，保留現有 cwd 模型。

### 32. 要不要把分支世界做成正式方向？

**問題｜**四位都挑中的「複製世界、試跑未來、提交一條」要先做 boundary fork、回合 branch、speculate，還是 arena？  
**為什麼卡著｜**它不擋近期 Deliver，但若轉成 roadmap，要先定可複製狀態、`.runi` 邊界與勝者如何成為 current。  
**在哪問過｜**〈隨意發想〉；4 位獨立地提出並各自選中同一家族。  
**候選答案｜**

- **`aos fork --at-boundary`**——有 `.runi` 就拒絕，複製 world／kernel、清空在途狀態。
- **`aos branch world@turn`**——保存真實回合快照，再從指定現場分兩條未來。
- **`aos speculate -n N`**——reflink 多份候選 world，評分後原子切換 current。
- **arena＋winner**——各 agent 在具名子目錄跑固定回合，由 judge 把勝者 rename 成 winner。

