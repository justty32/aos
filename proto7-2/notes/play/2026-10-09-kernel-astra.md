四個標準崩潰窗口的主流程基本成立：**先保存意圖、恢復時沿用原 id／run，舊 kill 不會自動轉向新 run**。但整包仍有數個明確缺口，包括重啟後反覆通知／kill、通知數量上限造成永久停擺、錯誤回報不一致，以及範例可能刪掉使用者原有資料。

本次全程只讀，未修改檔案。執行了 **15 個純規則測試，全部通過**，另以記憶體 mock 重現下列主要問題；會寫檔、啟動 daemon 或送 SIGKILL 的整合測試僅閱讀，未執行。

下文檔名除特別註明外，皆位於 `proto7-2/packs/kernel/`。

**一、正確性**

先列出已成立的保證與適用範圍：

| 檢查項目 | 審查結果 |
|---|---|
| 存 state 前崩潰 | 尚未送出新控制；既有 state 與水位不變。重新觀測後再決定，符合契約。 |
| 存 state 後、送 ctl 前崩潰 | 啟動先核 pending，不等新 tock；使用原 id／run 補送。 |
| 送 ctl 後、讀回條前崩潰 | 既有 ctl 或相符回條可恢復；不建立新 id。目標換 run 後不改殺新 run。 |
| 讀回條後、存 state 前崩潰 | 重起可從保留的回條恢復 done。 |
| 同 tock 重送／跳號 | 正常整數輸入下，僅處理 `round > last_tock`；跳號處理最新，不補中間回合。布林值例外見 C8。 |
| `config_sha` 不合 | 啟動與新 tock 都檢查；退 1，pending 保留，停止新提交與補送。 |
| state 壞 JSON | 退 3，不覆蓋原檔。合法 JSON 的深層欄位損壞未完整攔截，見 C5。 |
| ctl-done 比對 | 比原請求 `id`、`op`、`run`；成功還要求 `result.run` 符合原槽／run。壞回條不盲目補送。 |
| 同一通知意圖崩潰後重送 | 使用固定 id；mail 掃描 inbox 與 done 去重。這個保證成立，但不涵蓋「新 run 產生的新通知意圖」。 |
| done 上限 | `save_state()` 每次截成最近 20 筆；通知／kill 去重另存在規則狀態，不靠完整 done 歷史。 |
| rename 原子性 | 共用 `aos7_fs.write_json()` 在同目錄寫暫存檔後 `os.replace()`；可避免程序崩潰留下半份正式 state。沒有 `fsync`，因此不能把此保證延伸為斷電後的持久性保證。 |
| 來源鐘 | 關回合取 round、開回合取 round−1；停鐘不老化，未知區間與倒退後重建基準。跳號跨過兩門檻時，通知與 kill 可在同次決定產生，沒有額外等待六回合的保證。 |

主流程依據：[aos7_kernel.py:119](../../packs/kernel/aos7_kernel.py)、[aos7_kernel.py:238](../../packs/kernel/aos7_kernel.py)、[aos7_kernel_state.py:130](../../packs/kernel/aos7_kernel_state.py)、[aos7_fs.py:124](../../lib/aos7_fs.py)。

**正確性問題清單**

1. **C1｜高｜範例可能刪掉指定目錄內原有的資料。**  
   位置：[examples/supervise-brain/run.py:73](../../packs/kernel/examples/supervise-brain/run.py)、同檔第 94–95 行。`--house` 宣稱必須空白，實際只檢查 `<house>/bob` 是否存在；啟動成功後，收尾會 `rmtree(house)`。  
   **重現：**指定一個已有 `keep.txt`、但沒有 `bob/` 的可丟棄目錄，不加 `--keep`；範例啟動成功後，收尾連 `keep.txt` 一起刪除。本次僅靜態確認，未執行刪除。  
   **建議：**既有非空目錄立即拒絕；自動清理限定本次自行建立的專用目錄，使用者指定目錄則保留。

2. **C2｜高｜同一封信跨 run 反覆通知、反覆 kill，已確認。**  
   位置：[aos7_kernel_rules.py:66](../../packs/kernel/aos7_kernel_rules.py)、第 77–84 行；[ADVANCED.md:51](../../packs/kernel/ADVANCED.md)。基準是 `(id, step, run)`：run 一變就清掉 `notified`；`killed` 只記上一個 run。mail 的固定 id 去重無法阻止新決定產生的新 id。  
   **重現：**固定信 `letter`、step=2，run=1 觀測來源回合 0～12；換 run=2，再觀測 13～25。記憶體探針實際得到：`6 通知、12 kill、19 再通知、25 再 kill`。  
   **建議：**把「同一停滯事件已通知／已嘗試恢復」綁在來源、信 id、step，跨 run 保留；kill 請求仍綁具體 run。自動重試次數應有明確上限或等待人工處理狀態。**這是藍圖 §6 本身也允許的設計問題，不能只說實作偏離藍圖。**範例第 157 行把 deadline 改成 1 秒，才讓事件提早結案，沒有證明原設定不會循環。

3. **C3｜高｜11 個來源同時停滯，會永久延後，連 kill 都不做。**  
   位置：[aos7_kernel.py:222](../../packs/kernel/aos7_kernel.py)。新候選通知加上 pending 超過 10 封，就拒絕整輪並不保存規則狀態；下一輪仍提出相同 11 封，永遠超限。這在未設 mail 時也發生。  
   **重現：**設定 11 個來源與目標，同時建立基準，保持 task 不變。探針在來源回合 6、12、100 都得到零新意圖及「在途通知超過 10 封」。  
   **建議：**讓每輪至少能提交一部分來源，且只更新已提交來源的規則狀態；或在設定階段明確限制來源數，避免接受永遠無法執行的設定。

4. **C4｜高｜門檻設定未驗證，可以先 kill、完全沒通知。**  
   位置：[aos7_kernel_rules.py:26](../../packs/kernel/aos7_kernel_rules.py)、第 77–84 行；[aos7_kernel_state.py:66](../../packs/kernel/aos7_kernel_state.py)。錯型別、零或負數被默默換成預設值，也沒有檢查兩門檻順序。  
   **重現：**設定 `no_progress_rounds:10`、`kill_after_rounds:2`；探針在 age=2 只產生 kill。填 `"kill_after_rounds":"120"` 則悄悄改用 12。  
   **建議：**載入設定時驗證正整數及 `kill_after_rounds > no_progress_rounds`；不合退 2，且初始化 state 前就拒絕。

5. **C5｜中｜合法 JSON 的損壞 state 會被接受，甚至清掉去重記憶。**  
   位置：[aos7_kernel_state.py:115](../../packs/kernel/aos7_kernel_state.py)、[aos7_kernel_rules.py:35](../../packs/kernel/aos7_kernel_rules.py)。`_state_ok()` 只確認 `rules` 是 dict、`done` 是 list；規則遇到壞掉的 `brains`／`killed` 則把它們當空狀態。  
   **重現：**將正常 state 的規則狀態改為 `{"brains":[],"killed":[]}`，或 `done:[null]`；探針確認 `_state_ok()` 都回 True。前者會重新建立基準與去重記憶，後者讓 status 出現未捕捉例外。  
   **建議：**載入時驗證內建規則狀態、pending、done 的完整形狀；損壞退 3 並保留原檔，不能自動當成第一次執行。

6. **C6｜中｜設定驗證與規則使用不同的 node 比對方式，合法目標可能永遠不 kill。**  
   位置：[aos7_kernel_state.py:82](../../packs/kernel/aos7_kernel_state.py)、[aos7_kernel_rules.py:5](../../packs/kernel/aos7_kernel_rules.py)、第 81 行。設定驗證會正規化路徑；規則卻直接串接原始 `node/slot` 作 key。  
   **重現：**source 寫 `bob`、target 寫 `bob/.`，slot 都是 brain。設定通過，但探針重播到 age=19 只有 notify，沒有 kill。  
   **建議：**在設定邊界統一正規化來源／目標身分；規則、驗證、pending 衝突檢查共用同一套 key。

7. **C7｜中｜status 的「都在動」沒有觀測依據，停滯或不知道也可能顯示正常。**  
   位置：[aos7_kernel.py:356](../../packs/kernel/aos7_kernel.py)、第 364 行。它只看 pending、本 tock 的 done 與 `last_error`，不讀規則內的停滯／gap 狀態。通知完成後下一個 tock，就可能恢復顯示「都在動」。  
   **重現：**保留卡住來源的 `rules.supervise-brain.brains`，pending 為空、沒有本 tock 的 done；探針得到 `(0, "監督 1 件：都在動，沒有要處理的")`。來源讀不到但只留下 gap，也會落入相同分支。  
   **建議：**依已保存的觀測顯示「停滯中，已通知」「讀不到來源」「閒置」；單純沒有控制請求時，只能說「目前沒有在途操作」。

8. **C8｜中｜布林 tock 可被當成整數，寫出下一次自己讀不了的 state。**  
   位置：[aos7_kernel.py:288](../../packs/kernel/aos7_kernel.py)，依賴 [modules/tools/aos7_taskside.py:44](../../modules/tools/aos7_taskside.py)。`isinstance(True,int)` 成立，且 `True == 1`，因此 round／run 的型別界線失守。  
   **重現：**自身 run=1、last_tock=0，tock 為 `{"run":true,"round":true}`。探針確認 `wait_tock()` 回 True；存成 `last_tock:true` 後，kernel 的 `_state_ok()` 卻判不合法。  
   **建議：**tock 的 round 與 run 都使用排除 bool 的 `is_int()`；回條原請求 run 也應採相同嚴格型別檢查。

9. **C9｜中｜通知文字的換行會把整輪控制一起拒絕。**  
   位置：[aos7_kernel_rules.py:79](../../packs/kernel/aos7_kernel_rules.py)、[aos7_kernel.py:95](../../packs/kernel/aos7_kernel.py)。規則把 task 的 `line` 原樣塞進單行通知；含換行時候選不合法，整輪包含 kill 都被拒絕。  
   **重現：**task 的 line 為 `"第一行\n第二行"`，保持到 age=12；探針得到「text 要是非空的一行」，notify 與 kill 都不提交。現行 brain 通常會壓平 line，因此這主要是輸入防禦缺口。  
   **建議：**產生通知標題時壓平 `\r`／`\n`、限制長度；詳細內容放信件正文，避免顯示文字阻斷控制。

10. **C10｜中｜unknown 回條的處置與藍圖不同，未定結果會進入可淘汰的 done。**  
    位置：[aos7_kernel.py:137](../../packs/kernel/aos7_kernel.py)、[spec.md:85](../../packs/kernel/spec.md)。ctl 還在時會繼續等；ctl 已消失且收到相符 `ok:false,msg:"unknown…"` 時，則移入 `done unknown`，不再核對，最終可能被 20 筆上限淘汰。藍圖 §3 寫的是保留請求、下回合再核。  
    **重現：**準備相符 unknown 回條、ctl 不存在，呼叫 settle；pending 被移除，done 記 unknown。既有 `test_k17_consumed_unknown_never_resends` 明確要求這個行為。  
    **建議：**對齊藍圖、核心與 kernel spec，區分「請求仍在」及「請求已消耗但結果未知」。後者不應盲目補送，但未解證據也不宜只放在會被淘汰的歷史清單。

測試另有兩個盲點：`test_notify_cap_defers` 只驗第一輪拒絕，沒有驗後續能否前進；`test_k24_three_hundred_tocks_bounded_state` 最後只有 5 筆 done，實際沒有跨過 20 筆裁切門檻。應分別補「多轮後仍能完成」及「超過 20 筆後只保留最新 20 筆」的案例。

**二、簡潔：最值得簡化的四處**

README 的開頭與一行示範已容易上手；新手困難主要出在讀完輸出後，不知道「回合」是哪一種、通知要求自己做什麼，以及「接著做」為何最後變成 BLOCKED。

1. **S1｜中｜「回合」混用工作步驟與心跳計數。**  
   位置：[README.md:10](../../packs/kernel/README.md)、[aos7_kernel_rules.py:79](../../packs/kernel/aos7_kernel_rules.py)。README 說每秒做一步，但實際 task.step 可以停在 2，來源鐘持續累加 6、12。  
   **重現：**照 README 看通知「停在第 2 回合，已 6 回合沒進展」，很容易理解成彼此矛盾。  
   **建議：**工作進度一律叫「第 2 步」；監督門檻叫「6 次心跳」，範例再補「這裡約 6 秒」。

2. **S2｜中｜通知把內部證據交給人，沒有告訴人要做什麼。**  
   位置：[aos7_kernel.py:166](../../packs/kernel/aos7_kernel.py)、[aos7_kernel_rules.py:79](../../packs/kernel/aos7_kernel_rules.py)。標題是長信 id；正文主要是 basis JSON，還被 mail 模板補成「需要決定的事：無」。  
   **重現：**打開任一 kernel 的 NEEDS-USER 信即可看到。  
   **建議：**以原信標題、目前停在哪一步、接下來會發生什麼及可採取的操作為主；id、run、來源鐘移到末尾的證據區。

3. **S3｜低｜留下多套早期介面相容層，增加閱讀分支。**  
   位置：[aos7_kernel.py:26](../../packs/kernel/aos7_kernel.py)、[aos7_kernel_rules.py:21](../../packs/kernel/aos7_kernel_rules.py)、第 42、88 行。noop 定義兩份；正式規則已存在仍保留「尚未實作」的可選 import；params 可從兩處取得，snap 可是 list 或包一層 dict，src 又可是字串或 dict。  
   **重現：**新人從 `cmd_run → decide → supervise_brain` 追讀，必須反覆判斷哪種形狀才是真正入口送來的。  
   **建議：**正式路徑固定一種 ctx／snap／src 形狀，直接匯入單一 RULES；特殊測試格式在測試端轉換。

4. **S4｜低｜每個來源的資料重複包裝，內建規則只用其中一部分。**  
   位置：[aos7_kernel_state.py:186](../../packs/kernel/aos7_kernel_state.py)、[aos7_kernel.py:211](../../packs/kernel/aos7_kernel.py)。快照分 birth／task 兩筆，重複 src、run、clock；`seq` 等於 task.step，內建規則仍直接讀 step；ctx 同時提供合併後 config 與 rule。  
   **重現：**追查 age 的來源，會穿過多個重複欄位，但真正判定只使用 task 那筆的 run、completed_tock、id、step。  
   **建議：**下一次調整契約時，可考慮每來源一筆觀測、分開固定設定與規則參數。讀前後比對 birth 的安全檢查要保留，不能為少幾行而刪除。

**三、錯誤路徑**

以下以 `aos7_kernel.py` 簡稱 K、`aos7_kernel_state.py` 簡稱 S。這是**各錯誤分支的出口盤點**；「合規」指一般單行輸入，未包含後述換行注入問題。

| 出口／條件 | 檔:行 | 現況 | 判定 |
|---|---|---|---|
| 參數錯、缺子命令／node、`--rounds` 非整數 | K:375 | 退 2，一行前綴與用法例子 | 合規 |
| 缺 AOS7 環境變數、RUN 不能轉整數 | K:267 | Stop(2)，一行與安裝例子 | 合規；RUN 格式錯也被說成「缺環境變數」，措辭不精準 |
| kernel.json 不存在 | S:51 | Stop(2)，附設定例子 | 合規 |
| kernel.json 讀不到／非一般檔 | S:53 | Stop(3)，有「不確定：」及重試方式 | 合規 |
| kernel.json 壞 JSON、版本／來源／目標／規則／events／mail 外形不合 | S:55–78 | Stop(2)，附例子 | 已攔到的部分合規；驗證不完整見 C4、E2 |
| state 不存在但 decisions 尚在 | S:136 | Stop(1)，不初始化 | 合規 |
| state 讀不到、壞 JSON、外層欄位不合 | S:146 | Stop(3)，保留原檔 | 外層合規；深層見 C5 |
| 啟動時 config_sha 不合 | S:149 | Stop(1)，pending 保留 | 合規 |
| 執行中新設定雜湊改變 | K:305 | Stop(1)，pending 保留 | 合規 |
| 執行中設定變成壞 JSON／非法設定 | K:291 → S:78 | Stop(2) | 分類屬輸入錯；但整個 invocation 可能早已做過副作用，與嚴格「退 2＝什麼都沒動」有落差 |
| 初始化 state／decisions 寫入 OSError | S:142 → K:394 | 退 3，一行，保留已寫檔案 | 合規 |
| dry-run 規則例外／候選被拒 | K:279 | Stop(1)，stdout 保留決策 JSON | 合規 |
| 正式 run 規則例外／候選被拒 | K:215、242、302 | 只記 last_error；跑完指定回合仍退 0，stderr 空 | 不合規，E1 |
| dry-run／run 因 busy 或通知上限延後 | K:223 | 只記 note；有限回合可退 0 | 未表達「未完成」；另有 C3 |
| 每輪提交 state 失敗 | K:249 | 印錯誤後繼續重試，可能多行；退出未彙整失敗 | 不完整，E1 |
| settle 更新 state 失敗 | K:315 | 印錯誤、保留舊 state；`--rounds 1` 仍可退 0 | 不合規，E1 |
| 目標未掛載、ctl 衝突、ctl／回條讀不到、回條形狀不合、birth 讀不到 | K:122–150 | 記 pending.wait；有限 run 仍可退 0，stderr 空 | 未依「在途／不知道」退 3，E1 |
| ctl 寫入失敗 | K:182 | 轉 pending.wait；有限 run 仍可退 0 | 不合規，E1 |
| 寄信 OSError／ValueError／Refused | K:169 | 全部轉 wait，不分暫時故障、設定錯、確定拒絕 | 不合規，E1／E2 |
| 相符 rejected／unknown 回條 | K:144 | 記入 done；有限 run 仍退 0 | 未反映控制結果；unknown 另見 C10 |
| decisions 寫入失敗 | K:256 | 靜默忽略 | 可接受：文件明定只是顯示用，state 已提交 |
| status 找不到 kernel.json | K:333 | 退 2，一行與例子 | 合規 |
| status 的 kernel.json 讀不到／壞 JSON／形狀錯 | K:335 | 全部退 3 | I/O 故障合規；確定設定錯應為 2，E3 |
| status 的 tasks.json 讀不到／壞 JSON | K:323、339 | 退 3，一行 | 合規 |
| status 的 tasks.json 是錯誤 JSON 形狀 | K:325–327 | 有些當成空表，有些拋 TypeError | 不合規，E2／E3 |
| status 找不到 state | K:343 | 退 0，「還沒開始」 | 真正未初始化時合理；遺失 state 時可能誤報 |
| status 的 state 讀不到／外形錯 | K:345 | 退 3，一行 | 外層合規 |
| status 的 pending／done 元素錯形狀 | K:348–361 | 未捕捉 AttributeError／KeyError／TypeError | 不合規，E2 |
| 外層 OSError | K:394 | 退 3，一行不確定訊息 | 合規 |
| 其他未捕捉例外 | K:391–397、bin/aos7-kernel:6–8 | Python traceback，通常退 1 | 不合規，E2 |
| SIGTERM／SIGINT、正常有限回合完成 | K:283、302 | 退 0 | 正常路徑符合包 spec；未解故障不應被此出口掩蓋 |

**錯誤路徑問題清單**

1. **E1｜高｜正式 run 把失敗／不確定吞成成功。**  
   位置：[aos7_kernel.py:249](../../packs/kernel/aos7_kernel.py)、第 302、312 行。規則失敗、pending 未完成、控制／寄信失敗與 state 寫入故障沒有統一影響最終退出碼。  
   **重現：**以記憶體 mock 讓 `settle()` 每次拋 OSError，執行 `run --rounds 1`；實際結果是 **退出碼 0、stderr 三行**。規則丟例外時，正式 run 也可退 0，只有 dry-run 退 1。  
   **建議：**明確區分長駐中的暫時等待與指令退出結果；有限執行結束時，未定／I/O 故障退 3，確定拒絕退 1，彙整成一行錯誤。

2. **E2｜中｜多個資料邊界會外洩 traceback。**  
   位置：[aos7_kernel_state.py:74](../../packs/kernel/aos7_kernel_state.py)、[aos7_kernel.py:163](../../packs/kernel/aos7_kernel.py)、第 348、356、391 行。  
   **重現：**`mail.from:123` 會因驗證先 `str()` 而通過，寄信時 `name(123)` 拋 TypeError；`status` 讀到 `pending:[null]` 或 `done:[null]` 拋 AttributeError。兩類皆已用探針確認。自身 birth 的 mounts 錯形狀、信箱內壞信缺必要欄位，也有未捕捉出口。  
   **建議：**輸入型別在設定階段退 2；恢復資料／外部證據損壞退 3。補齊各邊界驗證與例外轉譯，避免用大範圍吞例外掩蓋程式 bug。

3. **E3｜中｜status 與 run 對相同壞資料採不同判定。**  
   位置：[aos7_kernel.py:320](../../packs/kernel/aos7_kernel.py)、第 335、343 行。status 自己做較鬆的驗證：確定壞設定當 unknown，錯形狀 tasks 有時當不存在，state 遺失又可能當尚未開始。  
   **重現：**同一份壞 kernel.json，run 退 2、status 退 3；保留 decisions、移除 state，run 退 1、status 退 0。  
   **建議：**共用不會初始化或寫檔的讀取／驗證函式；status 保留自己的展示方式，但不要另造資料有效性的規則。

4. **E4｜中｜stderr 單行及指令前綴沒有封住。**  
   位置：[aos7_kernel.py:166](../../packs/kernel/aos7_kernel.py)、第 375、392 行；依賴 [aos7_mail.py:121](../../modules/mail/aos7_mail.py)。直接呼叫 mail.send 會把 mail 的提示直接印到 stderr；錯誤字串也沒有統一壓成單行。  
   **重現：**寄給尚不存在的合法收件人時，成功也會出現 `aos7-mail: 注意…`；未知參數中帶換行，可讓用法錯誤跨行。持續寫入失敗則會反覆印同類訊息，見 E1。  
   **建議：**mail 函式提供安靜的程式呼叫介面，由 kernel 統一輸出；所有對外錯誤文字先壓平換行，固定 `aos7-kernel:` 前綴。

5. **E5｜低｜統一錯誤路徑測試沒有納入 kernel。**  
   位置：[tests/core/test_error_path.py:107](../../tests/core/test_error_path.py)、[tests/error_path.json](../../tests/error_path.json)。測試由清單生成，目前查不到 kernel 項目。  
   **重現：**搜尋該 JSON 的 `kernel` 無結果；因此整套錯誤路徑測試通過，也不能代表 kernel 合規。  
   **建議：**加入正式入口的 help／bad／unsure 案例，再補 run 中途故障、深層壞 state 與 mail 設定錯型別。

本次直接執行的正式 CLI 基本路徑均正常：`--help` 退 0 且 stderr 空；未知參數、缺任務環境的 `run`、不存在 node 的 `status` 都退 2、stderr 一行，沒有 traceback。

**四、NEEDS-USER 現在實際長怎樣**

信件不是以 `NEEDS-USER` 當標題；那是 frontmatter 的 status。標題由規則產生，README 記錄的實例是：

> bob 的 brain：信 you-20261009T213549-f681d54f4bf1 停在第 2 回合，已 6 回合沒進展（停在：第 1 回合，下一步第 2 回合）

預設寄件人 `kernel`、收件人 `you`；id 是 `k-<instance前8碼>-<rev>-<序號>`，`re` 沒填原信 id。正文經 mail 模板補成：

```text
## 做了什麼
kernel kernel 的通知（依據：{"src": "...", "file": "brain/task.json",
"run": ..., "completed_tock": ..., "id": "...", "step": ...,
"since": ..., "age": ...}）

## 產出（檔案路徑 / commit / 分支）
無

## 沒做到、或證據不足的部分
無

## 需要對方或使用者決定的事
無
```

上方 JSON 為欄位示意；實際程式把序列化結果截前 500 字，可能截斷 JSON。來源：[aos7_kernel.py:166](../../packs/kernel/aos7_kernel.py)、[aos7_mail.py:88](../../modules/mail/aos7_mail.py)。

**一般人能看出 bob 卡住，但不知道是哪件工作、需要決定什麼、該怎麼處理。**尤其 status 寫 NEEDS-USER，正文卻說「需要決定的事：無」，語意直接衝突。建議標題改成「bob 的〈原信標題〉停在第 2 步」，正文說明已等多久、何時會自動重啟，以及確實可用的查看／處理方式；原信 id、run 與時鐘留在證據區。

**最該先修的 5 條**

1. **C1：封住範例刪除既有目錄的風險。**這是整包唯一可直接造成使用者資料遺失的問題。
2. **C2：同一停滯事件跨 run 保留通知與恢復嘗試紀錄。**停止同信反覆通知、反覆 kill 的循環。
3. **C4：完整驗證設定，尤其通知／kill 門檻順序與型別。**避免使用者以為先通知，實際卻直接 kill。
4. **C3：修正通知上限造成的永久延後。**超限時仍須有可完成的前進路徑。
5. **E1／E2：統一失敗出口並封住 traceback。**讓失敗、在途、資料損壞確實回報 1／3，而不是退 0 或裸露 Python 例外。