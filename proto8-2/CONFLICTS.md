# proto8-2 慣例跟 proto8 原則相撞的地方（已全部裁定）

← [proto8-2](README.md)｜慣例：[CONVENTION.md](../proto8/CONVENTION.md)｜原話：[thinking/ideas](../proto8/thinking/2026-10-19-ideas.md)

這份只列**真的衝突**：proto8 裡使用者過去定的原則（C-xx 概念、N-xx 規範、wf user.md 的規矩），跟今天的決定或慣例對不上。措辭差異、程式還沒改的不列。**六條已全部由使用者 10-19 裁定**（總原話：「雖然10/16說那套很棒，但那是帶著鐐銬跳舞……終究不如我們現在直接把鐐銬拿掉」，見 [ideas § 9](../proto8/thinking/2026-10-19-ideas.md)）。每條只留：原則 ↔ 今天、撞在哪、裁定。

## 1. 「少用 sh」 ↔ 慣例入口是 shell 檔

**原則**：wf user.md「少用 sh」（10-15）。當時是看 proto8 的 agent 當工具要用 `sh -c 'aos loop; cat ret.json'` 串三步，使用者說「拜託，少用 sh」：inst 的 argv[0] 直接寫程式名，要重導、換資料夾就用 inst 現成的 key。

**今天**：§ 4「以我們 aos agent 的慣例來說，.aos/exec 他就是一個 shell 指令……內容就是 #usr/bin/sh aos-loop loop.json」。而且 agent-bob 的 fsm、idle、think、act 四格全是 sh 腳本（`cat`、`ls | head`、`cp`、`mv`、case）。

**撞在哪**：10-15 禁的是「拿 sh 拼字串當膠水」；今天入口本身就是 sh 檔，格裡的邏輯（讀狀態、挑題、搬檔）也靠 sh 寫。一句「少用 sh」現在不知道該管到哪。

**裁定（10-19）**：只考慮 Linux（跨平台之後再說）；shell 入口與格照用，只禁 `sh -c '…; …'` 拼字串。user.md 已補一句。

## 2. 「站在 stack、定義掛捷徑、路徑從 stack 算」 ↔ 「起跑 cwd＝定義資料夾、stack 走環境變數」

**原則**：10-16 夜定的 C-59／C-60／N-47／N-48：跑一份定義＝`aos exec stack 定義`——站進 stack（cwd），在 stack 裡放一條 `.aos` 捷徑（symlink）指向定義的 `.aos/`，定義裡的檔互相指一律寫 `.aos/x`、從 stack 算，「沒有第二種路徑規則」。使用者當時說「太優雅，太美了，這就是我要的」。C-65 也說 agent 跑的時候站在 stack。

**今天**：§ 1「在此處，cwd 是 agent-bob/，這會是慣例」；§ 2 執行狀態放 `AOS_STACK`。aos-exec 是 `cd DIR` 再跑入口；不掛捷徑；定義裡的檔用相對路徑從定義資料夾算（`loop.json`、`brain.py`），執行狀態寫 `$AOS_STACK/…`。

**撞在哪**：站的地方反了（proto8 站 stack、今天站定義），找定義檔的方法也不同（捷徑 vs 就在 cwd）。兩套不能並存，一份 agent 不是這樣寫就是那樣寫。

**裁定（10-19）**：走今天的：cwd＝定義資料夾、狀態走 `AOS_STACK`。

## 3. 「stdin 是正規參數入口、agent 的 stdin 只放定義」 ↔ 「aos 只訂環境變數，這次要做啥隨意」

**原則**：C-57／N-46（10-16）：正規參數入口是 stdin，argv 寫法都是語法糖，「不得有只能靠 argv 才做得到的事」。C-58／N-49：agent 的 stdin 只放一份、是定義；「這次的話」放在 stack。N-50：工具參數走門房的 stdin、分兩層。N-12：stdin／stdout／stderr 都是 JSON 串流。

**今天**：§ 4「entry 這塊，『這次要做啥』，其實就隨意……反正我們就是訂下一些環境變數，就這樣」。定義就是資料夾本身、不從 stdin 進；慣例上題目放工作區 `inbox/`（拍板點 2）；aos-exec 把 args／stdin 原樣透傳、不解讀。

**撞在哪**：proto8 說「參數一定從 stdin 進、形狀是 JSON」；今天說「從哪進都行、aos 不管」。N-12 對 proto8-2 的入口也不再適用。

**裁定（10-19）**：走今天的（這次要做啥隨意）。AI 曾建議「agent 之間傳題目走 inbox/ 當共同形狀」——使用者說「inbox先不管」，不採、不定。

## 4. 「結束碼只是參考、規範只定 0／非 0、停靠 stdout JSON」 ↔ 「停止碼 10」

**原則**：C-63（10-16）「結束碼只是參考，是 Unix 時代的遺留……真正的結果與狀態看 JSON」；N-43「規範只定 0＝正常、非 0＝有錯，aos 的程式說自己的錯一律退 1」；N-44 fsm 走到 end 時靠 stdout 那行 `"end": true` 讓 loop 停。

**今天**：拍板點 1 (b) 選了「停止碼 10」：idle 看 inbox 空就退 10，aos-loop 收到 10 當「正常停」、自己退 0；其他非 0 當失敗。

**撞在哪**：10 是一個「有意思」的結束碼——不是錯、是訊號，正是 C-63 說不該靠的那種；N-43 說非 0 一律是錯，10 卻是正常。

**裁定（10-19）**：走今天的，停止碼 10 照用。

## 5. 「agent 的定義不含 loop」 ↔ 「入口就是 aos-loop loop.json」

**原則**：N-53／C-62（10-16 KISS 重審拍板 4）：aos 的 agent 是被外面的 loop 一拍一拍驅動的狀態機，**定義不含 loop**——反覆幾次、隔多久是外面那個 loop 的事；為的是 agent 方便審視自己。

**今天**：§ 1「定義一個資料夾 agent-bob/，然後設定入口：一個 shell 檔案……內容是 aos-loop loop.json，那個 loop.json 的位置是 agent-bob」。loop 在 agent 資料夾裡、就是入口。

**撞在哪**：字面上 agent-bob/ 這個「定義」含了 loop。

**裁定（10-19）**：走今天的，agent 資料夾可帶 loop 當入口。

## 6. 「工作區保持乾淨、stack 別放在工作區裡」 ↔ 「AOS_STACK 預設 $AOS_WS/.aos/」

**原則**：C-65（10-16 夜）：工作區＝使用者的檔、成品要留的地方，「跑完只多出成品，不留 `.aos`、history、`work/` 這類執行時的東西（stack 別放在工作區裡，除非呼叫方自己選）」。使用者原話：「我不喜歡 /ws 底下出現一個 work/，這太突兀了，工作區會變得不乾淨。」

**今天**：§ 2「所以我們再設定一個 AOS_STACK=ws/.aos/」——預設就把 stack 放進工作區的隱藏資料夾。

**撞在哪**：預設值正是 C-65 說「別放」的位置，差別只在它是隱藏的 `.aos/`，不是 `work/`。

**裁定（10-19）**：走今天的，`AOS_STACK` 預設 `$AOS_WS/.aos/`。

## 7. 「收到 SIGTERM＝優雅收工、退 0」 ↔ 「被外層逾時殺掉＝那格失敗」（10-19 第二輪）

**原則**：N-52（10-16）：所有 aos 程式收到 SIGTERM 都是「優雅收工」——收好子程式、寫好狀態、**退 0**、不寫 stderr；要分「做完」還是「被叫停」看 JSON，不看結束碼（C-63）。

**今天**：P-36：巢狀時外層的 `timeout_ms` 到了，aos-inst 對整個子行程群組送 SIGTERM（過 grace 再 SIGKILL）；被殺的那格結束碼是 128＋訊號、`trace.jsonl` 記 `timed_out: true`，fsm 不換狀態、以那個碼退，loop 當失敗停下（P-19、P-20）。

**撞在哪**：照 N-52，cathy 的 loop 收到 SIGTERM 應該退 0——那 bob 的 act 會看到 0、以為 cathy 做完了，拿不到答案才在下一步失敗，錯誤位置往後飄一格；外層自己的 `timed_out: true` 也被「0＝成功」蓋掉。例子：bob 的 act 包 10 分鐘逾時叫 cathy，cathy 的腦卡住；照 N-52 bob 看到 0、去 `cp $sub/ws/out/q.txt` 失敗退 1，人看到的是「act 複製失敗」，不是「cathy 逾時」。照 P-36 bob 看到 143、stderr 只有 cathy 那層的一行、bob 的 act 說「cathy 失敗」，trace 寫 `timed_out`。

**預設裁定**：走今天的（P-36）——這是 CONFLICTS 4「結束碼走今天的」的延伸：proto8-2 沒有 stdout JSON 給人看「被叫停」，只剩結束碼，所以被殺就得是非 0。§ 9「剩下都用今天的做法」應該涵蓋；列出來是因為 N-52 是使用者 10-16 親口定的原則（「退 0……重點在於把該做的事情做一做後才結束」）。使用者沒反對就照 P-36 做。

## 方向問題（原則推不出、看使用者喜好）

### 甲、agent 當工具時，題目怎麼交給它

**背景**：bob 的 act 叫 cathy。cathy 是標準範本，認 `$AOS_WS/inbox/` 一題一檔（拍板點 2）。使用者 10-19 說「inbox 先不管」——不把 inbox 定成 agent 之間的共同形狀。

**P-32 的預設**：呼叫方照被叫者自己的說明備題。cathy 的說明說她看 `inbox/`，所以 bob 在她的小格裡開 `ws/inbox/<題名>`、叫她、從 `ws/out/<題名>` 拿答案。這不是規則、是 cathy 的介面（P-26 工具參數怎麼進由工具說明定）。

**另一條路**：agent 當工具時統一「題目 stdin 進、答案 stdout 出」（像 stamp），工作區只給需要留成品的。好處：bob 叫 cathy 跟叫 stamp 一行一樣、不用備工作區；代價：cathy 得多一層入口把 stdin 寫進自己的 inbox、跑完 `cat out/`，又回到 10-15 被使用者否決的 `sh -c 'aos loop; cat ret.json'` 那種殼（user.md「少用 sh」）。

**要問的**：以後 agent 當工具，是 (a) 各看各的說明（預設，demo 這樣做）、還是 (b) 定一個共同的題目／答案通道（定了就等於把 inbox 或 stdin 定成共同形狀，跟「inbox 先不管」要再對一次）。沒回答就照 (a)。
