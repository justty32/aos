# llmcall 規則（fake／LiteLLM）

← [契約卡與第一次跑](README.md)｜凍結介面：[llm2 藍圖](../../notes/blueprint-llm2.md)

## 1. 身分與檔案

`node = Bud.node`，`CD = <node>/llmcall/<budget_id>/<call_id>/`。call_id＝`^[A-Za-z0-9_-]{1,64}$`。K＝bg.make_key(budget_id,holder,call_id)，kid＝bg.kid_of(K)；logical／attempt 不進 K。

| 檔案 | 內容／用途 |
|---|---|
| CD/request.json | `{v:1,call_id,logical,budget,holder,req_sha,reserve,meter,endpoint,request}`；req_sha＝bg.sha(request) |
| CD/raw.json | `{v:1,call_id,req_sha,source:"transport"或"adopted",reply,at}`；原始回覆先存再算 |
| CD/receipt.json | 已結算交付的回條；pending 不寫 |
| CD/request.json.lock | 整次 call／adopt 的 flock，`locked(CD/request.json, timeout=0)`；拿不到 unknown、stage busy、退出 3 |
| budget/id/gateway/kid.json | intent／done 證據，與 budget 共用 K 鎖 `locked(bud.p("gateway", kid+".json"))`，無 timeout |
| llmcall/fake-remote.json | 假遠端 sends 計數，僅測試觀察；任何恢復路徑不讀 |
| llmcall/.crash | 測試 SIGKILL 點 |

鎖序 call → K；傳輸持 K，settle 前放 K、仍持 call。鎖檔不刪；未結算／pending 不清。

## 2. call

CLI：`aos7-llmcall call budget/<id> --holder H --call C --request req.json --reserve R [--logical L] [--deadline D] [--patience 5] [--out f]`。

1. 先驗 call_id／holder／正整數 R／有限 deadline (0,86400]／非負 patience／JSON 物件 request；壞輸入退出 2 不寫檔，讀檔 EIO 回 unknown io／3。
2. 持 call 鎖，首次寫 request；已存則比較 req_sha／reserve／holder／budget，不同 conflict／1 不寫（即使有 receipt）。之後用已存 logical。receipt 已有就原樣重印／--out，否則 after-request。
3. content＝`{resource:"llm.tokens",gateway,amount:R,payload_sha:req_sha}`，ask reserve；denied／conflict／bad 回 1 不寫 receipt，非 reserved／settled 回 unknown／3；after-reserve。
4. 持 K 鎖依下表；釋放後 pending 不 settle／receipt，印 used／settle null 回 4。其餘 ask settle，非 settled 回 unknown／3；after-settle → 寫 receipt → after-receipt → 印回條／--out。

| 本地證據 | 動作 |
|---|---|
| 入口紀錄存在且 digest 不同（outcome cancelled 的 done 除外） | conflict 退出 1，不寫檔、不結算 |
| raw 存在、入口 done | 原樣用 done 與 raw，不改位元組、不送 |
| raw 存在、入口未 done | 由 raw 算 done、at 取 raw.at，寫入口；不送 |
| raw 不存在、入口 done | 照用 denied／cancelled；digest 不同且 outcome 非 cancelled＝conflict 退出 1 |
| raw 不存在、入口 intent | digest 不同＝conflict；否則 unknown、stage intent，intent 後無回覆、不重送、預留留著，退出 3 |
| 無入口紀錄 | read_ledger＋judge 首次准入；unknown／not_yet 退出 3 不寫入口；denied 寫 done used 0／usage null／overrun 0／billing final／raw_sha null／why；ok 核帳 K reserved 且 digest 相同，再 intent → 傳輸 |

首次准入須帳上 K reserved 且 digest 相同，否則 unknown／conflict。intent 欄位：`{stage:"intent",kid,key,digest,gateway,call_id,admitted_tock:c,at}`。intent → after-intent → send → after-send → raw → after-raw → done → after-done。

## 3. 計量與 done

done：`{stage:"done",kid,key,digest,gateway,call_id,outcome,used,usage,overrun,billing,raw_sha,at}`；未知 usage 不寫 used。raw_sha＝bg.sha(raw)，at＝raw.at；已有 done 不改。

status ok→answered；error→failed；reject 且 billed 明確 false→rejected，used 0、overrun 0、billing final，不看 usage。其他形狀（壞 status、reject 但 billed 非 false）→failed 且 usage 視為未知。

usage 欄存 reply.usage 原樣（非 dict 就 null）。U＝usage.total_tokens，只有非負整數（bool 不算）才已知，不加總其他欄。U 已知：used=min(U,R)、overrun=max(0,U−R)、billing＝overrun>0 ? overrun : final。未知且非 rejected：不寫 used、overrun 0、billing pending。meter 依傳輸取值，bound 固定 soft。

## 4. 回條與退出碼

回條鍵的順序固定：`{v:1,call_id,logical,kid,key,req_sha,meter,bound:"soft",reserve,outcome,usage,used,overrun,billing,raw_sha,text,settle}`。text＝reply.body 原文，不是字串就 null；無 raw 的 denied／cancelled 也為 null。settle＝帳回條的 settle 物件原樣，pending 為 null；used＝done.used，pending 為 null。

stdout 一行 `json.dumps(obj, ensure_ascii=False)`；receipt／--out 用 write_json；重印以同樣 dumps，最後一行位元組相同。

| 碼 | 條件 |
|---|---|
| 0 | answered＋final；status／adopt 成功 |
| 1 | failed／rejected／denied／cancelled＋final；reserve denied／conflict／bad；conflict；adopt 條件不合 |
| 2 | 壞輸入、未送任何請求 |
| 3 | busy、intent 無回覆、傳輸逾時或例外、帳未回、讀寫未知 |
| 4 | billing pending 或 overrun |

Unknown／bg.LedgerDown／OSError 印 unknown io／3、無 traceback；鎖忙 stage busy。patience 計 completed_tock，不是牆鐘。

## 5. 假傳輸與 deadline

`TRANSPORT = aos7_llmcall_fake.send` 保留。send 在 daemon thread 執行，join(deadline)；逾時／例外回 3、留 intent，程序不等 thread；重跑只看本地證據。

假傳輸先 edit_json(`<node>/llmcall/fake-remote.json`) 做 sends[call_id]+=1；恢復不讀計數。request.fake 缺省 mode ok／usage 10。ok／over／late／no_usage 回 status ok、billed true；fail 回 error、billed true；reject 回 reject、billed false。no_usage／reject 的 usage null，其餘 usage 為 total_tokens:U、prompt_tokens:U−U//3、completion_tokens:U//3。body 為 text（預設 `{"v":1,"mode":"keep"}`），fail 為錯誤文字。late 記受理後 sleep(delay)；未知 mode 丟 ValueError。

### 傳輸 llm.litellm

頂層有 litellm 就選此傳輸；值須為物件，model 是字串、messages 是 list。fake 與 litellm 並存、型別不合、缺必要欄或 stream true，退出 2、不寫檔。其他請求沿用 fake。不加 CLI 旗標。

| 傳輸 | gateway | meter | endpoint | 未給 deadline |
|---|---|---|---|---|
| fake | llm.fake | fake.total_tokens/1 | fake | 60 秒 |
| LiteLLM | llm.litellm | litellm.total_tokens/1 | AOS7_LITELLM_URL，預設 http://localhost:4000/v1 | MAX_DEADLINE＝86400 秒 |

reserve.content.gateway、intent／done 依傳輸；request.json 保存該 meter／endpoint。grant 由 budget judge 驗 llm.litellm；明給 deadline 驗 (0,86400]，HTTP timeout＝thread join。

`TRANSPORT_LITELLM = aos7_llmcall_litellm.send`；POST `<base>/chat/completions`，body 是 request.litellm 原樣，**不加 max_tokens 或任何上限**，由呼叫者決定。只有 AOS7_LITELLM_KEY 非空才送 Authorization: Bearer；不寫計數檔、不重試。

| 回覆 | status／billed | body／usage |
|---|---|---|
| 200 合法 JSON 且有 choices[0] | ok／true | message.content 是字串才保存；usage dict 原樣，其他 null |
| 200 壞 JSON／缺 choices | error／true | content 若可得；usage dict 若可得，否則 null |
| 400–499（除 408、429）且回應無 usage | reject／false | 原文字串截 64 KiB；usage null |
| 其他 4xx（408、429 或帶 usage）、3xx（不跟重新導向）、5xx | error／true | usage dict 原樣，沒有就 null（pending） |
| ConnectionRefusedError（含 URLError.reason） | reject／false |「連線被拒，未送達」；usage null |
| 其他例外（逾時／中斷／DNS 等） | 丟出 | 閘道 unknown、留 intent、退出 3 |

reply 另保存 model、finish_reason、http（狀態碼）、elapsed（秒 float，四捨五入至三位小數）、response（完整 JSON 原樣；解析不了保存原文字串截 64 KiB）。整份 reply 的孤立 surrogate 換成 U+FFFD，確保 raw 能存。失敗仍依既有 usage 規則結帳：已知 U→final／overrun；未知→pending、留 R、退出 4。

## 6. status 與 adopt

`status budget/<id> --holder H --call C` 唯讀印 indent=1 JSON：request、raw_exists／raw_sha、入口、帳上 K、receipt，退出 0。

`adopt budget/<id> --holder H --call C --raw f`：檔讀不到／非物件退出 2。持 call 鎖（busy＝3）→K 鎖，只收 request 已存、入口 intent、無 raw，且 f.call_id／req_sha 與 request 相同、reply 為 dict。成功寫 raw（source adopted、at now），退出 0；其他退出 1 不寫。adopt 不 done／settle，同 C 重跑才結帳。

## 7. 崩潰點與驗收

`.crash` 到點刪旗標並 SIGKILL 整組（start_new_session）。八點：after-request／reserve／intent／send／raw／done／settle／receipt。無 raw 的 intent 不重送、留 R；有 raw 靠本地恢復。一 reserve 至多一 settle；audit 每筆 log 守恆、非負。F01～F04 零 skip；LiteLLM 只連本地 HTTP 假伺服器。

## 8. 相依與界線

B2 budget（PARTIAL_SETTLE）接受部分結算、pending 留 R、overrun 累計、done key／digest 綁帳；不可查回 intent 的 cancel 回 unknown。本包只讀 import、不修改 budget。

支援 llm.fake／llm.litellm；不做串流、端點輪替、價格帳、重試、遠端查回、cancel、自動凍結／補帳、作者／adapt 接線。holder 自報；保存到退役，未結算不清；只驗 SIGKILL、不承諾斷電持久性。
