# 缺口與風險

← [入口](../layer-interfaces.md)｜上一份：[跨層](04-cross-layer.md)

只記不修。行號照 commit 6ed9a7a7 的檔。「實驗」＝這次在暫存目錄跑過確認；「讀碼」＝照程式推出來、沒實跑。分三級：**接上 kernel／agent 前該處理**、**接上後會常碰到**、**文件不一致**。

## 一、接上 kernel／agent 前該處理

**G1 tasks.json 壞掉時，寫入工具會把整份表換成只剩新項（實驗）**
`aos7_fs.edit_json`（`lib/aos7_fs.py:193-203`）用寬鬆的 `read_json`（`:82-100`）讀舊內容：檔案半寫、不是 JSON、讀不到（EIO）、被換成 FIFO，一律回 `default`（`None`）。`aos7-ctl add`（`lib/aos7_ctl.py:115-131`）、restart 加 once 項（`lib/aos7_task.py:568`）、`retry_lost` 加回（`lib/aos7_task.py:278`）都把 `None` 當空表，於是寫回只剩新加的那項。實驗：寫一份壞掉的 tasks.json（兩項、少了結尾），跑 `aos7-ctl add` 加一項，結果檔裡只剩新的那一項。tick 讀表時是三態（壞掉＝當空表、不起），但**寫表的路徑沒有照三態**，spec 第 4.1 節也只規定了讀。kernel 接上後是最常寫 tasks.json 的角色，這會直接丟掉人寫的項目。

**G2 tick 的非 3 失敗被當成一回合，吃掉 `resume --rounds` 的倒數（實驗）**
`lib/aos7_daemon_timeline.py:280-286` 只特別處理退出碼 3 和逾時；其他失敗（Python 例外、退出碼 1）往下走成正常回合，tock 看到回合已關印 `skipped`，`:316-322` 判定「關上了」就呼叫 `round_done` 扣倒數。spec 第 2.1 節第 3 步沒定義 3 以外的失敗。實驗：`.aos/` 設唯讀，`resume --rounds 3` 只真跑 1 回合，node 又被同 owner pause 回去，status 只在 `last_error` 看得到 traceback。kernel 用 `rounds` 做「只跑 N 回合」、預算放行時會被騙。

**G3 父 kill 子 daemon 時，子 daemon 的任務可能變孤兒（實驗）**
父的 kill 是 SIGTERM 加 1 秒寬限（`lib/aos7_proc.py:27`、`lib/aos7_task.py:390-411`）；子 daemon 把 SIGTERM 當 stop＋kill（spec 第 83 行），逐槽收自己的任務、每槽也最多 1 秒。子任務各在新 session、身分是子 node 的，父的 Q1 範圍（spec 第 315 行）蓋不到。實驗見 [04 第 3 節](04-cross-layer.md#3-子-daemon--父時間線s-21-路一)：兩個不理 SIGTERM 的子任務留下。父表那項還在時新的子 daemon 會接手；拿掉那項就沒人管。

**G4 daemon 控制檔沒有請求 id，回條同名蓋掉，也沒有完成證據（讀碼）**
spec 第 76-77 行、`lib/aos7_daemon.py:397-440`。kernel 想知道「我上一次下的 pause 生效了沒」只能比 `queued_at`，同名的下一份請求一進來舊回條就沒了；請求刪不掉時（`:438` 吞掉 OSError）同一份每圈重做，`resume --rounds` 會一直被重設。任務控制已經有 `ctl_id`＋`ctl-seen.json`，daemon 這一側沒有對應的東西。

**G5 proto7-1 的 kernel／agent 程式不能直接跑（讀碼）**
`proto7-1/lib/aos7_agent.py:15` import `task_dirs_of`、`task_read`，proto7-2 的 `aos7_fs` 沒有這兩個；`aos7_kernel.py:21-45`（`load_state`）、`aos7_kernel_rules.py:37,69` 也用它們。另外 `aos7_kernel_rules.py:103` 讀 status 的 `paused`（proto7-2 是 `paused_by`），`:239-243` 的 `issued` 以 tid 為鍵（槽名固定後 restart 一次就永遠不再 restart 同一槽），`aos7_kernel.py:56-62` 的 daemon 控制檔每回合換檔名又不帶 owner。對照全表在 [03 第 3 節](03-kernel-agent.md#3-接到-proto7-2-的介面上會怎樣)。

## 二、接上後會常碰到

**G6 pause 擋住任務控制和 tock（讀碼，spec 已知）**
spec 第 312 行「node 被 pause 時等到 resume」、第 388 行「pause 中做任務控制（N-82）之後再說」。kernel 想「先 pause 止血、再 kill 燒錢的任務」做不到：kill 要等 resume。`lib/aos7_fs.py:524` 的 `wait_tock` 沒設逾時就永遠等，`modules/counter.py` 就是這樣寫的。

**G7 任務 `ctl.json` 一個槽只有一份，後寫的蓋掉先寫的（讀碼）**
`lib/aos7_ctl.py:97-111` 直接覆寫。kernel 和人同時對同一個槽下 kill／restart，先寫的那件無聲消失（沒有回條）。proto7-1 kernel 先看「已存在就不寫」，但「看」和「寫」之間不是原子的（沒用 `O_EXCL`）。

**G8 任務環境整份繼承 daemon，tasks.json 沒有 `env` 欄（讀碼）**
`lib/aos7_task.py:844-851`、`lib/aos7_fs.py:546-552`。daemon 環境裡有什麼（例如 LLM key），每個任務都拿得到；想只給某一項設環境變數，只能寫進 argv（`sh -c 'X=1 ...'`）或用 inst。跟 LLM 端點筆記「只有根分配者拿得到真的 key」（待定點 2）衝突。機制是通用的，影響最大的是 LLM 端點。

**G9 paused.json 誰能寫，spec 說法含糊（讀碼）**
spec 第 13 行把 paused.json 列成「多人讀—改—寫、要拿鎖」；程式（`lib/aos7_daemon.py:112-136`）是 daemon 唯一寫者，只在起來時讀一次。人或 LLM 直接改它：daemon 跑著時不生效，下一次 pause／resume 會被蓋掉，daemon 重開時才生效。proto7-1 的 llmkernel 探針正是「daemon 起來前先寫 paused.json」。

**G10 `.aos/` 裡哪些名字是核心保留的，沒有定義（讀碼）**
spec 第 1、3、5 節分散列了核心的檔（round.json、last-round.json、tasks.json、timeline.json、action.*、ctl-seen.json、tasks/）。proto7-1 kernel 把 `roster.json` 寫進成員的 `.aos/`；核心以後若加一個同名檔就會撞。

**G11 kernel 要的回饋 status 沒有（讀碼）**
crash loop 看不到（N-29、N-71 沒做，status 沒有 `last_task_fail`）；last-round.json 只留上一次，kernel 取樣比成員回合慢就會漏掉 `ended`；子 daemon 的 status 父看不到（N-14）。kernel 只能自己掃各槽的 exit.json（下一個 run 起來就被清）或開歷史 module。

**G12 拿著 tasks.json.lock 太久的副作用（讀碼）**
tick 等 1 秒拿不到，這回合不起任何東西；restart 請求拿不到鎖回 `ok: false` 而且**請求被消耗**（`lib/aos7_task.py:569-570` 之後照樣寫回條、刪 ctl.json），要重送。spec 第 318、323 行有寫，但 kernel 作者容易以為「沒執行＝留著下次再做」（其他「不知道」的情況請求確實留著）。

**G13 一回合要收很多槽時，tick／tock 可能逾時（讀碼推論）**
kill 在拿著 action.lock 時做，每槽最多 1 秒＋等 exit.json 0.5 秒。kernel 一次對同一個 node 下幾十個 restart，而任務又不理 SIGTERM 時，可能超過 `action_timeout_s`（預設 30 秒）被 SIGKILL，回合標 `incomplete`。

**G14 執行中加掛隨 keep 換 run 消失（spec 已知）**
spec 第 236 行：重建 `mnt/` 只照宣告加上 restart 帶的 `mounts_dyn`。keep 任務自己掛掉、下一回合重起時，之前請求到的掛載沒了，要重請、多等一個 tick。

**G15 掛載與控制都跨不出空間根（spec 已知）**
`lib/aos7_mount.py:44-51`。子 daemon 裡的任務掛不到父空間的資料夾、寫不到父 daemon 的 `.aosd/ctl/`（除非用絕對路徑繞過 S-10）。團隊用子 daemon 做邊界時，跟上層分配者之間的信箱沒有正規的路。

## 三、文件不一致

**G16 用量（usage.json）有三種說法**
proto7-1 程式：`{tokens, calls}` 一直累加（`proto7-1/lib/aos7_agent.py:67-70`），kernel 把所有任務的 `tokens` 加總（`aos7_kernel_rules.py:44-47`）。proto7-2 spec 第 354-357 行（A2-09 後）：usage.json 只記這一次 run，`{run, usage}`，kernel 對每個 run id 取最大值再相加。`notes/changes-from-7-1.md:29` 還是舊說法：「usage.json 在槽裡跨 run 只增不減；kernel-state 記每槽已見最大值＋`retired`」。槽重用後，照 proto7-1 寫法的 agent 會把前幾個 run 的累計帶下去，照 spec 的算法會重複算。

**G17 README 過時**
`proto7-2/README.md:10` 還寫「2 條要你決定：P2-01、P2-02」，`notes/problems.md` 已是 0 條；`:40` 寫「219 項」，最新 commit 訊息是 222 項，工作區另有兩個還沒 commit 的測試檔（`tests/test_matrix_a3.py`、`test_options_a3.py`，別的隊伍正在做）。

**G18 第一輪綜合筆記過時**
`proto7/notes/thinking/2026-10-04-r1-synthesis.md:75` 說 `until_round`「缺」、`:77` 說回合中 wake 無效、P2-01 待決定；兩件 proto7-2 都已實作（commit 060dca8b、79e67233）。

**G19 S-10「任務只碰 tick 給的資料夾」沒有強制（spec 已接受）**
spec 第 308、383 行。任務拿得到 `AOS7_ROOT`，掛載只是方便；`modules/history.py` 沒掛載時也直接照 `$AOS7_ROOT/<id>` 讀。記在這裡是因為 kernel／agent 接上後，「只碰給的資料夾」完全靠程式自律。
