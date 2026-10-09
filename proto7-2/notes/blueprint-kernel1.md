# kernel 第一版藍圖（kernel1）：決策骨架＋監督 brain 範例

← [意圖卡](intents/kernel.md)｜依據 [kernel-pack](reviews/2026-10-05/kernel-pack.md)（§2～§6 契約、§9 驗收、§10 預設全採）、[r7 Q5](../../proto7/notes/thinking/2026-10-05-r7-decisions.md)、核心 [spec §6](../spec.md)、[錯誤藍圖](blueprint-errors.md)｜分線 [blueprint-kernel1-teams.json](blueprint-kernel1-teams.json)。Fable 2026-10-09 20:30。

## 1. 一句話

新包 `packs/kernel/`：**kernel-core 骨架**（觀測→規則→驗證→存意圖→送控制→核對）＋**一條規則 supervise-brain**。核心零改動；用既有 `ctl.json` kill 協定；step／budget／adapt 不碰。

## 2. 七題全照預設（代定）

第一版＝骨架＋進度監督，只觀測與綁 run 的 kill｜規則＝純函式、JSON 型別邊界、薄入口注入｜同 run 恢復後已送的 kill 不撤回、釘原 run、狀態標「可能延後生效」｜接續＝同部署同 node 同槽，初始化與執行分開｜單一控制者，`sources`（可讀）與 `targets`（可控）兩份設定｜三包獨立｜不綁 aos7-pack（裝法＝`aos7-ctl add` 一行）。

## 3. 檔案與接點

- 設定 `<node>/kernel/kernel.json`：`{"v":1,"sources":[{"node","slot","kind":"brain"}],"targets":[{"node","slot"}],"rules":[{"name":"supervise-brain","no_progress_rounds":6,"kill_after_rounds":12,"notify":"you"}],"events":false}`。target 不在 sources 裡＝設定錯（退 2）。
- 自己槽內 `state.json`（唯一恢復真相，一次 rename）：`{"v","config_sha","instance","rev","last_tock","rules":{...},"pending":[{"id","op":"kill","target","run","why","basis","sent":bool}],"done":[最近 20 筆]}`。`decisions.json` 只留上一次、只給人看。
- 快照每項：`{"src","file","run","seq","completed_tock","read":"ok|absent|bad|unknown","value"}`；讀前後核對 run，不一致＝`unknown`；絕不折成空物件；不呼叫會收程序的判定（只讀公開檔，不用 `judge_resolved`）。
- 控制：寫目標槽 `ctl.json`＝`{"op":"kill","run":int,"id","by":"kernel/<slot>","why"}`；回條 `ctl-done.json` 比 `id`＋`run`＋`op`，不符不認領；`ok:false` 且 msg 以 `unknown` 開頭＝請求仍在、下回合再核。
- tock：只收自己的；跳號處理最新、不補造；同 tock 重送不重提交；來源年齡用來源 `completed_tock`（關了取 round、開著取 round−1），來源鐘停＝不老化。

## 4. 規則介面（純函式）

`rule(ctx, snap, rstate) -> (rstate2, candidates)`；`ctx={"v","tock","config"}`；`candidates=[{"op":"kill","target","run","why","basis"}|{"op":"notify","target","text","basis"}]`。骨架整份驗證：未知 op、型別錯、target 不在 targets、run 非整數→整份拒絕不部分送；同目標重複合併、矛盾拒絕；規則丟例外＝這輪不提交、記 `last_error`。第一版只註冊內建兩條：`supervise-brain`、`noop`（測試用）。

## 5. 執行順序與崩潰點

① 讀設定＋state（`config_sha` 不合→停止新提交、保留 pending、退 1 說明）② **先核既有 pending**（不等新 tock）③ 新 tock→快照→規則 ④ 驗證 ⑤ 一次 rename 存 rstate＋`last_tock`＋pending ⑥ 送 ctl ⑦ 依回條更新。崩潰點：⑤前（無新 ctl、水位不前進）、⑤後⑥前（重起直接送同 id）、⑥後⑦前（不造新 id、不誤殺新 run）、回條後存 state 前（從回條恢復）。state 寫失敗＝記憶體水位也不前進。

## 6. supervise-brain 規則

- 進度來源：`<brain 槽>/../../brain/task.json`（公開事實）：`{"id":信,"step","line","stall","run"}`；基準＝`(id, step)`。沒有 task.json＝閒置或已結案（含 LT1 的「卡住」結案）→不納入。`run` 與 birth 不合、讀不到＝unknown→不計老化、恢復後重建基準。
- 老化＝來源 completed_tock 距基準建立的回合數。≥`no_progress_rounds`→`notify` 一次（mail NEEDS-USER 給 `you`：「bob 的信〈標題〉第 N 回合起沒進展」；沒 mail 只寫 decisions.json）；≥`kill_after_rounds`→`kill` 綁當時 run，一個 run 最多一次。
- 新信、新 step、新 run→重建基準並清通知旗標。brain 自己的「連續 3 回合沒進展→要你決定」會先觸發，所以預設 6／12 是它的保底；brain 真的壞死（程序活著但不寫 task.json）才會走到 kill。
- 範例 `examples/supervise-brain/`：用 `aos7-up` 起假 AI node，寄一封標題含「沒進展」的信（假 AI 會一直回「卡住」），看 kernel 第 6 回合寄信、第 12 回合 kill、keep 重起後 brain 從 task.json 接續；再寄一封正常信證明不誤殺。

## 7. 錯誤與人類面

退出碼照 [blueprint-errors](blueprint-errors.md)：0 做到／1 做不到（設定雜湊不合、目標不在 targets）／2 你給的不對／3 不知道（state 讀寫故障、回條未到；證據留著）。stderr 一行「aos7-kernel: 發生什麼。怎麼辦」。對外指令 2 個：`run`（keep 任務用）、`status <node>` 一行白話。README 三行頭＋第一次跑（假 AI、不花錢、≤10 分鐘）；契約卡、state 形狀、規則介面在 ADVANCED。QUICKSTART 不動。

## 8. 驗收（R 隊逐條）

骨架：K01、K02（dry-run 不改檔）、K03、K04、K06、K10～K18、K21、K24（300 回合 state 不長）；規則：K05、K07、K08、K09；整合：I01（kernel 被殺三包照跑）、I02（不另派 step 子工作——第一版根本不碰）。範例：假 AI「沒進展」信→第 6 回合一封 NEEDS-USER、第 12 回合 kill 回條 `ok:true`、brain 重起接續、正常信零動作；每個崩潰點 SIGKILL ×3；全套退出碼 0。人類面：Haiku／luna 照 README ≥7、指令 ≤2、概念 ≤4。

## 9. 不做（本輪）

§2 列的全部；啟動逾時規則；外部程式規則；`aos7-up --watchdog` 整合（r7，避開 up 的檔）；`aos7-pack`。

## 10. 分線（領地互不重疊；細節在 json）

| 線 | 領地（皆 `proto7-2/packs/kernel/`） | done |
|---|---|---|
| KC1 骨架 | `aos7_kernel.py`、`aos7_kernel_state.py`、`bin/aos7-kernel`、`tests/test_kernel_core.py`、`spec.md` | §8 骨架條；規則用 `noop` 與測試假規則 |
| KR1 規則 | `aos7_kernel_rules.py`、`tests/test_kernel_rules.py`、`tests/fixtures/brain/` | §8 規則條（純函式單測，不起 daemon） |
| KE1 範例＋文件 | `examples/supervise-brain/`、`README.md`、`ADVANCED.md`、`INDEX.md` 一列、`tests/test_kernel_example.py` | §8 範例條＋人類面 |

介面在本藍圖凍結（§3 state／快照／ctl 形狀、§4 規則簽名），KC1 與 KR1 並行；KE1 等兩者進 main。避開 M1（up brain）、ST（up status）、LT2（compact）、S3b（author examples）的檔——本包全新，只讀 brain/task.json。
