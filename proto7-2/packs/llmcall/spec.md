# llmcall 規則（假傳輸 v1）

← [契約卡與第一次跑](README.md)｜正本：[llm2 藍圖](../../notes/blueprint-llm2.md)、[items](../../notes/blueprint-llm2-items.json)

## 1. 身分與檔案

`node = Bud.node`，`CD = <node>/llmcall/<budget_id>/<call_id>/`。call_id 只准 `^[A-Za-z0-9_-]{1,64}$`。K＝`bg.make_key(budget_id, holder, call_id)`、kid＝`bg.kid_of(K)`，logical 只記不進 K；attempt 不進 K。

| 檔案 | 內容／用途 |
|---|---|
| CD/request.json | `{v:1,call_id,logical,budget,holder,req_sha,reserve,meter:"fake.total_tokens/1",endpoint:"fake",request}`；req_sha＝bg.sha(request) |
| CD/raw.json | `{v:1,call_id,req_sha,source:"transport"或"adopted",reply,at}`；原始回覆先存再算 |
| CD/receipt.json | 已結算交付的回條；pending 不寫 |
| CD/request.json.lock | 整次 call／adopt 的 flock，`locked(CD/request.json, timeout=0)`；拿不到 unknown、stage busy、退出 3 |
| budget/id/gateway/kid.json | intent／done 證據，與 budget 共用 K 鎖 `locked(bud.p("gateway", kid+".json"))`，無 timeout |
| llmcall/fake-remote.json | 假遠端 sends 計數，僅測試觀察；任何恢復路徑不讀 |
| llmcall/.crash | 測試 SIGKILL 點 |

鎖序固定為 call 鎖 → K 鎖；傳輸持 K 鎖，settle 前釋放 K 鎖、仍持 call 鎖。鎖檔不刪；資料保存到預算退役，未結算／pending 不清。

## 2. call

CLI：`aos7-llmcall call budget/<id> --holder H --call C --request req.json --reserve R [--logical L] [--deadline 60] [--patience 5] [--out f]`。

1. call_id 不合、holder 空、R 非正整數、deadline 不在 (0, 86400]（含 inf／nan）、patience 負、req 不存在／不是 JSON／不是物件：退出 2、未送請求、未寫檔。req 讀不到 EIO 類＝unknown、stage io、退出 3。
2. 取 call 鎖。request 不存在就寫固定請求。存在則只比 req_sha／reserve／holder／budget；任一不同 conflict 退出 1，不寫檔（已有 receipt 也一樣，不重印舊回條）；其後用已存內容（logical 以已存為準）。
3. receipt 存在且 OK：讀回物件以同樣 json.dumps 重印，按回條算退出碼；有 --out 也寫一份；結束。否則 after-request。
4. content＝`{resource:"llm.tokens",gateway:"llm.fake",amount:R,payload_sha:req_sha}`。`bg.ask(bud,"reserve",K,content,patience)`：denied／conflict／bad 印 outcome、stage reserve、why，退出 1、不寫 receipt；不是 reserved／settled＝unknown 退出 3。after-reserve。
5. 持 K 鎖，依下表恢復或首次准入。
6. 釋放 K 鎖。done.billing pending：不送 settle，印回條 used null／settle null，不寫 receipt，退出 4。其餘 `bg.ask(bud,"settle",K,patience=...)`；不是 settled＝unknown 退出 3；after-settle；原子寫 receipt；after-receipt；印回條，有 --out 也原子寫。

| 本地證據 | 動作 |
|---|---|
| 入口紀錄存在且 digest 不同（outcome cancelled 的 done 除外） | conflict 退出 1，不寫檔、不結算 |
| raw 存在、入口 done | 原樣用 done 與 raw，不改位元組、不送 |
| raw 存在、入口未 done | 由 raw 算 done、at 取 raw.at，寫入口；不送 |
| raw 不存在、入口 done | 照用 denied／cancelled；digest 不同且 outcome 非 cancelled＝conflict 退出 1 |
| raw 不存在、入口 intent | digest 不同＝conflict；否則 unknown、stage intent，intent 後無回覆、不重送、預留留著，退出 3 |
| 無入口紀錄 | read_ledger＋judge 首次准入；unknown／not_yet 退出 3 不寫入口；denied 寫 done used 0／usage null／overrun 0／billing final／raw_sha null／why；ok 核帳 K reserved 且 digest 相同，再 intent → 傳輸 |

首次准入的預留不存在／非 reserved＝unknown 退出 3，digest 不同＝conflict 退出 1。intent 凍結內容：`{stage:"intent",kid,key,digest,gateway:"llm.fake",call_id,admitted_tock:c,at}`。寫 intent 後 after-intent，傳輸回覆後 after-send，原子寫 raw 後 after-raw，算 done 寫入口後 after-done。

## 3. 計量與 done

done 的欄位：`{stage:"done",kid,key,digest,gateway:"llm.fake",call_id,outcome,used,usage,overrun,billing,raw_sha,at}`；未知 usage 時不寫 used。raw_sha＝bg.sha(已存 raw 物件)。由 raw 重建的 at 固定取 raw.at，已有 done 不改。

status ok→answered；error→failed；reject 且 billed 明確 false→rejected，used 0、overrun 0、billing final，不看 usage。其他形狀（壞 status、reject 但 billed 非 false）→failed 且 usage 視為未知。

usage 欄存 reply.usage 原樣（非 dict 就 null）。U＝usage.total_tokens，只有非負整數（bool 不算）才已知，不加總其他欄。U 已知：used=min(U,R)、overrun=max(0,U−R)、billing＝overrun>0 ? overrun : final。未知且非 rejected：不寫 used、overrun 0、billing pending。meter 固定 `fake.total_tokens/1`，bound 固定 soft。

## 4. 回條與退出碼

回條鍵的順序固定：`{v:1,call_id,logical,kid,key,req_sha,meter,bound:"soft",reserve,outcome,usage,used,overrun,billing,raw_sha,text,settle}`。text＝reply.body 原文，不是字串就 null；無 raw 的 denied／cancelled 也為 null。settle＝帳回條的 settle 物件原樣，pending 為 null；used＝done.used，pending 為 null。

stdout 是一行 `json.dumps(obj, ensure_ascii=False)`，receipt／--out 用 write_json。重印讀回物件以相同方式 dumps，最後一行位元組與首次相同。

| 碼 | 條件 |
|---|---|
| 0 | answered＋final；status／adopt 成功 |
| 1 | failed／rejected／denied／cancelled＋final；reserve denied／conflict／bad；conflict；adopt 條件不合 |
| 2 | 壞輸入、未送任何請求 |
| 3 | busy、intent 無回覆、傳輸逾時或例外、帳未回、讀寫未知 |
| 4 | billing pending 或 overrun |

Unknown、bg.LedgerDown、OSError 一律一行 JSON outcome unknown／stage io、退出 3，不留 traceback。call 鎖拿不到是 stage busy。帳 patience 沿用 completed_tock 回合，不換成牆鐘。

## 5. 傳輸與 deadline

模組屬性 `TRANSPORT = aos7_llmcall_fake.send`。在 daemon thread 呼叫 send(node, call_id, request, deadline)，主執行緒 join(deadline)；逾時／傳輸例外退出 3、intent 留著。daemon thread 不等，程序可以結束；重跑不查假遠端、不重送。

假傳輸先 edit_json(`<node>/llmcall/fake-remote.json`, fn, default={sends:{}}) 做 sends[call_id]+=1，再回覆 `{status,billed,body,usage}`。request.fake 缺省 mode ok／usage 10。

| mode | 回覆 |
|---|---|
| ok／over | status ok、billed true；body=text，預設 `{"v":1,"mode":"keep"}`；usage＝{total_tokens:U,prompt_tokens:U−U//3,completion_tokens:U//3} |
| no_usage | 同 ok，usage null |
| fail | status error、billed true、body 錯誤訊息，usage 同 ok |
| reject | status reject、billed false、usage null |
| late | 記受理後 sleep(delay)，再回 ok 形狀；delay>deadline 時閘道已逾時離開 |
| 未知 mode | 丟 ValueError；閘道視為傳輸例外 |

## 6. status 與 adopt

status CLI：`status budget/<id> --holder H --call C`。唯讀印 indent=1 JSON：request、raw 是否存在及 raw_sha、入口紀錄、bg.status 的 key 版、receipt，成功退出 0。

adopt CLI：`adopt budget/<id> --holder H --call C --raw f`。f 讀不到或非物件＝2。取 call 鎖（拿不到＝3）→K 鎖，只在 request 存在、入口 stage intent、raw 不存在、f.call_id==C、f.req_sha==request.req_sha、f.reply 是 dict 時，寫 `{v:1,call_id,req_sha,source:"adopted",reply:f.reply,at}`，印一行、退出 0。其他條件不合一律印原因、退出 1、不寫資料。adopt 不算 done、不 settle；其後同 C 重跑 call 走有 raw 路徑。

## 7. 崩潰點與驗收

test_crash(node, point) 讀 llmcall/.crash，內容等於 point 就刪旗標，`os.killpg(os.getpgid(0), SIGKILL)`；測試子程序一律 start_new_session。

八點：after-request、after-reserve、after-intent、after-send、after-raw、after-done、after-settle、after-receipt。F01／F02 各點三個獨立 C 各真 SIGKILL 一次（首跑必須 -9），同 C 重跑恢復，最多一次送出、一 reserve 最多一 settle。after-intent 沒送、after-send 有送無 raw，均保留 intent 與 R；其他點恢復終局。F02 與另一 C 無崩潰基準比較計量與結算，raw_sha 核對、回條重印及檔案不變。獨立 audit 每筆 log 重放守恆且非負。

F03 驗 U<R、U=R、pending、overrun、兩 C 搶最後額度；F04 驗 deadline、睡眠中殺整組 ×3、不退款、cancel 守門與 adopt 接回。B2（budget 部分結算，`PARTIAL_SETTLE`）已在 main，全部案子都跑、零 skip。

## 8. 相依與界線

B2 budget 必須接受 0≤used≤amount，先判 billing pending 留 R，再驗 used；done key／digest 綁帳（cancelled used 0／digest null 例外），settle.overrun 與帳頂 overrun 累計；不可查回 llm.fake intent 的 cancel 必須 unknown、不改入口。以 PARTIAL_SETTLE 宣告就緒，本包只讀 import、不修改 budget。

只做假傳輸，不做真模型、串流、多端點／計量、價格帳、隱藏重試、遠端查回、llmcall cancel、overrun 後自動凍結、pending 自動補帳、作者／adapt 接線。holder 是合作式自報。保存到預算退役，未結算不清。只承諾本輪驗證的程序 SIGKILL 恢復，不承諾斷電持久性。
