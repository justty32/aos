搬家本身大致完整：未發現條號遺失、重號、區內壞連結或壞錨點，混合檔拆條也沒有漏搬。  
主要問題在行為契約：程序收尾、`aos-as`、當機紀錄，以及區外舊規則仍會讓實作者做出互相矛盾的版本。  
全程唯讀、未改檔；條號檢查通過，完整 schema 驗證受環境阻擋，全 repo lint 失敗但整理區單獨通過。

以下位置以 `proto6/spec/` 為根。git／cgroup 草稿本身不列問題，只指出它們被當成現行規則的地方。

**必修**

- **必-1｜daemon 可能收不到自己正常開出的任務。**  
  **位置：**[settled/daemon.md，B-601、B-604](../../../spec/settled/daemon.md)，對照 `base/inst.md`「執行與錯誤」、B-202。  
  **問題：**daemon 在 runner 啟動前建立並記住程序群組；inst 卻要求 runner 的子程式再另開群組。照兩邊一起實作，真正的 tick／掛載程式就不在 daemon 記住的群組裡，停機、取消與格後收尾可能漏掉正常任務。另有直接矛盾：B-601 說格後直接 SIGKILL、跳群組的不保證清掉，卻引用要求 TERM→寬限→KILL、另開 session 也不能漏的 B-202。  
  **建議改法：**明定實際受管群組由誰建立、如何交給 daemon／helper；本輪收尾以 B-601／B-604 為完整正本，區外引用只保留不衝突的串流與取消規則。

- **必-2｜`aos-as` 複製整份環境，破壞憑證與鎖的契約。**  
  **位置：**[settled/helper.md，B-303](../../../spec/settled/deferred/helper.md)；`settled/protocol/tick.md` P-212；`settled/daemon.md` B-609、B-612；P-109。  
  **問題：**暫存 inst 要寫入「目前的環境」，正常情況下便會把 `AOS_TICK_TOKEN` 寫到磁碟，違反 B-612「只放記憶體、不寫檔」。另外，fd 經 SCM_RIGHTS 傳遞後編號可能改變；複製進 inst 的舊 `AOS_TICK_LOCK_FD` 又可能覆蓋 runner 補的新編號。  
  **建議改法：**明列通道憑證與 fd 編號不得序列化進 inst；由 runner 在最後建立子程序環境時補入正確值。

- **必-3｜helper 的 spawn 請求缺少 runner 必需的來源路徑。**  
  **位置：**[settled/protocol/daemon/provision-and-runner.md，P-108、P-109](../../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)；B-609；`daemon-helper.schema.json`。  
  **問題：**公開 `spawn_as` 有 `.aos/jobs/` 下的 inst 路徑，私有 `daemon.helper.spawn` 卻只傳 node、UID、token 與快照等 fd，沒有原始路徑。helper 因而無法填 runner 必填的 `--target`，也不能依規定重驗原來源 bytes。schema 還拒絕額外欄位。  
  **建議改法：**私有協議傳入已核准的來源路徑，或等效的可信來源 handle 與資訊；同步 schema、範例及 runner 的來源核對規則。

- **必-4｜格數保證不倒退，但保存方式不支持這項保證。**  
  **位置：**[settled/tick.md，B-633](../../../spec/settled/tick.md)，P-213。  
  **問題：**`seq` 完全靠 `current.json`／`last.json` 推算，卻明定不 fsync。整機斷電或 WSL VM 強制關閉後，不能保證只是「少一筆、看到 `ended:false`」；也可能恢復成較舊紀錄。這會破壞跨重啟不倒退的承諾，連帶影響鬧鐘與保留期。  
  **建議改法：**分開定義「格數」與「每項結果」的落盤要求；至少為開格序號及檔名切換補足必要的持久化步驟。不要讓保留期依賴可能倒退的序號，卻仍宣稱單調。

- **必-5｜恢復流程把 git、needs、group 的舊規則帶回來。**  
  **位置：**[settled/tick.md，B-625](../../../spec/settled/tick/recovery.md)；`settled/daemon.md` B-607；`settled/protocol/tick.md` P-207、P-210；對照 A-102。  
  **問題：**恢復前必須完成 A-102，但它仍要求檢查 needs、group 連續、kind 順序及提交後 resume。這會拒絕第二十批允許的陌生 key，也使無 git 的基礎流程需要 commit。P-207 自己也同時寫「只做原子替換」及「已提交／commit 故障」。  
  **建議改法：**把通用、無 git 的修改與恢復契約放回整理區；領域驗證只在安裝對應任務時適用。現行碼表描述原子替換結果，git 提交流程移到下一步段落。

- **必-6｜沒有 cgroup 的限制，仍被其他現行段落蓋掉。**  
  **位置：**[settled/tick.md，B-625](../../../spec/settled/tick/recovery.md)；T-09；P-208；[daemon 協議 P-106](../../../spec/settled/deferred/protocol/daemon/registration.md)。  
  **問題：**B-625 仍說 daemon／VM 重啟先清空舊程序；T-09 也把重啟列入程序群組收尾。這與已接受的「無 cgroup 時 daemon 重啟清不掉」不符。P-208 還把 `cgroup_delegate` 列成當前部署操作；P-106 引用的最小正例則回傳完整 cgroup 配置，與本輪一律 `null` 相反。  
  **建議改法：**重啟描述直接沿 B-603 的已接受限制；交框操作明標下一步；現行查詢正例改成 `cgroup:null`，未來範例另標草稿。

- **必-7｜結束碼 schema 接受正文不允許的結果。**  
  **位置：**[settled/protocol/tick.md，P-213](../../../spec/settled/protocol/tick.md)；`protocol/schemas/tick-record.schema.json`；B-620、B-633。  
  **問題：**整格的頂層 `exit` 接受 0～255，包括 3、125；`stopped_after` 也能配成功碼或從未執行的 ID。唯讀實測確認這些資料都通過目前 schema。這裡指整格結果，任務自己的 0～255 沒有問題。  
  **建議改法：**紀錄頂層只收實際會寫入的 0／1／2，75 不寫紀錄；有 `stopped_after` 必須回 1。停在哪個 ID 的跨欄位關係交給補充驗證器，並加入反例。

- **必-8｜方案 A 尚未完成，協議篇仍是部分行為的唯一正本。**  
  **位置：**[P-103 授權表](../../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md)、P-102、P-108、P-115；node 協議 P-204、P-206、P-213。  
  **問題：**包含完整 method 授權、helper 由子到父解除的條件、PID 檔生命週期、boot ID 不持久化，以及「普通程式回 125 不能推定沒跑」「不另做通用收據」等。這些不是單純欄位格式，主規格還直接向協議篇索取行為。  
  **建議改法：**將獨有行為歸入對應 B 條；協議留下欄位、碼義、JSON、schema、範例與定位連結。README 已列疑點，不能代替搬回正本。

**設計問題**

- **設-1｜任務表到底由誰驗 kind／methods，責任沒有接完整。**  
  **位置：**[settled/tick.md，B-620、B-626](../../../spec/settled/tick.md)；P-202；`tick-tasks.schema.json`。  
  **問題：**核心說忽略 kind／methods、只驗四件事；schema 卻要求 kind、限制其值及 methods 形狀。收件任務目前只明定檢查跨任務 methods 重複。缺 kind、`system.x`、methods 型別錯時，誰拒收並不清楚。  
  **建議改法：**分清「驗結構」與「解釋行為」，逐項指定負責者；說明完整 schema 是核心必驗，還是供外部工具／系統任務驗證。

- **設-2｜結束碼紀錄中途寫失敗，後續讀者如何退化沒有定完。**  
  **位置：**[settled/tick.md，B-633「例外」](../../../spec/settled/tick.md)，B-621、B-623。  
  **問題：**規格只說寫不進就照跑、不設環境變數。若前幾項已經成功寫入，後來才滿碟，舊 `current.json` 還在；若開格切換失敗，也可能留下上一格的內容。哪些讀者必須停止相信它、從何時起不再發布紀錄，沒有明確界線。  
  **建議改法：**定義「本格紀錄已失效」的狀態轉換，要求後續任務無法把殘留檔當有效本格紀錄；補開格失敗、中途失敗及下格恢復的驗收。

- **設-3｜`aos-as` 被取消後，另一帳號的原指令可能繼續跑。**  
  **位置：**[settled/daemon.md，B-609](../../../spec/settled/daemon.md)；B-303；P-108。  
  **問題：**原指令在 helper 的另一個 session；wrapper 被訊號結束，並不會自然取消那個程序。規格卻說取消／逾時由呼叫方管，又沒有對應 spawn 識別或取消接口。可能出現核心已開下一項，前一項原指令仍在改檔。  
  **建議改法：**補上 wrapper 消失、回報 pipe 斷線時的 helper 收尾流程，以及何時才能視為該項結束。這與任務故意留下後代不同。

- **設-4｜帳號名稱綁 UID 的保護，跨重啟是否成立不清楚。**  
  **位置：**[settled/daemon.md，B-606](../../../spec/settled/daemon.md)、B-603；P-116。  
  **問題：**規則要求首次命中名稱後綁 UID，之後同名換 UID 必須拒絕；但恢復檔沒有保存這份綁定。daemon 停止期間帳號被刪掉重建，重啟後可能直接接受新 UID。  
  **建議改法：**明定綁定壽命；若跨重啟仍有效，就保存並重新核對；若只保證單次 daemon 存續，須把限制寫在保證旁。

**建議**

- **建-1｜對外依賴有列出，但尚未分清哪些是基礎必需、哪些只是領域用法。**  
  **位置：**[settled/README.md，「對外依賴」](../../../spec/settled/README.md)；B-601、B-606、B-623；P-208、P-210。  
  **問題：**通用契約仍混著 kernel 如何補登記、agent 如何被叫醒、LLM 路線驗證等具體做法。依賴表也漏列收件實際引用的完整發布／儲存契約，以及部分建立、恢復入口。整理區可讀，但尚未自足。  
  **建議改法：**將基礎必需的契約列完整；領域做法標成使用例或附加驗證，避免它們成為普通 tick 的前提。這不要求本輪重寫區外各篇。

- **建-2｜名詞篇仍重寫太多行為，容易形成第二份正本。**  
  **位置：**[settled/terms.md，T-07、T-09、T-10](../../../spec/settled/terms.md)，對照 B-620、B-626、B-633。  
  **問題：**核心四件事、四類程式、停格／擋板、daemon 收尾在名詞與主規格反覆完整重述；目前「重啟先清空」就是已經漂移的例子。  
  **建議改法：**名詞留一句定義與正本連結，執行順序、例外、保證及驗收集中在主規格。

- **建-3｜README 的 schema 搬移理由有一處事實錯誤。**  
  **位置：**[settled/README.md，「怎麼判斷哪些放進來」](../../../spec/settled/README.md)，無條號。  
  **問題：**「schema 沒有 `$id`」並非全部成立；`node-tasks`、`node-tick-record` 已有。  
  **建議改法：**刪掉這個錯誤前提，保留相對 `$ref`、共用依賴與暫不搬動的實際理由。

**要使用者裁定**

- **裁-1｜多個任務各自取通道訊息，如何避免拿走別人的件？**  
  **位置：**[settled/tick.md，B-623](../../../spec/settled/tick/mq.md)；B-614；P-119。  
  **問題：**每個 node 共用一個 FIFO，`node.take` 只有 token／limit，取走即刪；各任務卻必須自己取。任務 A 先取一批，就可能拿走應由 B 處理的訊息。這在正常執行就會發生，不能只用「不保證送達」帶過。  
  **選項：**① `node.take` 加 method／task 選取，各任務只領自己的；② 指定一項普通任務取整批、落到共享收件區，其他任務再處理；③ 每個 node 限一個通道消費者，由它負責分派。

- **裁-2｜daemon 的所有內部計時，都算毫秒例外嗎？**  
  **位置：**[settled/daemon.md，「時間用毫秒」及 B-610](../../../spec/settled/daemon.md)；P-109；第二十批追答 4。  
  **問題：**裁定說內部決定的保留期等改用格數；正文卻以「daemon 不在格內」為理由，連診斷保留期、批次間隔等都保留毫秒。這比明示的叫醒週期例外更廣，不能直接當成使用者已裁定。  
  **選項：**① 明確允許 daemon 自身全部計時用毫秒；② 只有週期、OS 收尾等保留毫秒，政策性保留期用所屬上層格數；③ 逐項列出毫秒例外，不用「是否在格內」一概判斷。

**自動檢查結果**

| 檢查 | 結果 |
|---|---|
| `python3 proto6/spec/check_ids.py --strict` | **通過，exit 0**。3380 次引用、241 個定義；缺號、重號、只剩索引、預留未寫均為 0。 |
| 指定的 `uv run --no-project --with jsonschema …/validate.py` | **未完成，exit 2**。uv 無法在唯讀 `~/.cache/uv/` 建暫存鎖；路徑未搬。 |
| 直接用 `python3 -B` 執行同一驗證器 | **未完成，exit 1**。現有 Python 缺 `referencing`；未安裝套件或繞過沙盒。 |
| `wf/tools/wf-lint.sh` | **失敗，exit 1**。全 repo：壞連結 76、超長檔 40、biglist 1563、biglist_links 157。壞連結均在本輪範圍外。 |
| 補跑整理區 lint | **通過，exit 0**。壞連結 0、超長檔 0；另列 biglist 33、biglist_links 3。 |
| 整理區相對連結與錨點 | **通過**，未發現損壞。 |

另以現有 jsonschema 的唯讀接口局部驗證了必-7，確認不合法結果確實被接受；這不等於完整 schema／範例驗證通過。