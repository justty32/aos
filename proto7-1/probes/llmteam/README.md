# llmteam：路一＋路二混合的 LLM 團隊

**是什麼**：兩個只靠讀寫檔的 LLM 同時操作，用 [llmop.py](../llmop.py) 的 read_file／write_file 兩個工具，加上[操作卡](../llm_card.md)。

- **A**：node `lab` 裡由 tick 起的任務（[a_task.py](a_task.py)，靠 `spawn/` 起一次）。A 要在自己的 node 開子 daemon（路一，子根 `lab/sub`），在裡面建 w1、w2 兩個 worker node，就緒後寫 `lab/READY.json`。之後外面會把子 daemon stop 掉，A 要讓它「停了就保持停住」。A 只准寫 `lab/`。
- **B**：外部維運員（探針程序裡跑）。只准寫 `lab/sub/.aosd/` 與 `ops/`，用子 daemon 的控制檔（路二）做三件事：pause w1、讓 w2 只再跑 3 回合、stop 整個子 daemon。結果寫在 `ops/report.json`。

旁邊有一個取樣 thread，每 50 ms 看一次子 daemon 的 pid、gen、stopped 與 w2 回合。daemon 開著寫入紀錄（`AOS7_AUDIT=1`）。

**跑法**

- 離線（run_all 用，約 9 秒）：`python3 probe.py`。A、B 都是照稿腦，分兩場：
  - 主場：A 會擋 keep。
  - naive 場：A 寫完 READY 就收工。
- 真模型：`python3 probe.py --real A模型,B模型 [--cap 30,30]`。精簡逐字紀錄與結果放在 `runs/`。

**想逼出的**

- B stop 子 daemon 之後，父的 keep 會不會把它起回來（路一和路二打架）。
- 子根的相對路徑與絕對路徑會不會讓人困惑。
- 父 daemon 看不到子 daemon 的狀態（N-14）。
- 誰能替子 daemon 建 node。
- 結束碼與孤兒程序。

## 離線結果（照稿，全綠）

| 量 | 主場 | naive 場 |
|---|---|---|
| B 的 pause／resume rounds=3／stop | 都 ok | 都 ok |
| w2 在 resume rounds=3 之後又收幾回合 | 3（**當時進行中的那回合也算一回合**） | 3 |
| B stop 之後被 keep 起回來 | 0 次（A 在 50 ms 內看到 `stopped` 就改了 tasks.json，搶在父的下一個 tick 之前） | **1 次**（下一個 tick，gen 1→2；起回來後照讀 paused.json，w1、w2 都停著，但 daemon 活著） |
| subd 的結束碼 | 0 | 0（被 stop 收掉跟自己做完分不出來） |
| 寫入紀錄判 ok:false 的 | subd 任務：`lab/sub`、`lab/sub/w1`、`lab/sub/w2`（子 daemon 和它的 tick／tock 寫自己的根）；llm-a：`lab/sub/w1`、`w2`（A 替子 daemon 建 node） | 同左 |

## 真模型（兩場合計 115 次呼叫，上限 130）

| 場 | A 模型（呼叫） | B 模型（呼叫） | A 就緒 | B 三步 | 子 daemon 保持停住 | report |
|---|---|---|---|---|---|---|
| 1 | deepseek-chat（30，用完） | claude-haiku-4.5（30，用完） | 36 秒（中間 crash loop 69 次） | 0/3（A 自己先把子 daemon stop 了，B 到的時候它已經死了） | 是（但是 A 自己 stop 的） | 沒寫 |
| 2 | chatgpt-gpt-6-luna-low（30，用完） | deepseek-chat（25，自己結束） | 79 秒（crash loop 約 67 次） | **3/3**，回條都 ok，w2 剛好 3 回合 | **否**：stop 後 0.15 秒被 keep 起回來，gen 1→2，B 看出來了但改不了 | 沒寫（B 在想辦法時就結束了） |

第 2 場起，A 的目標多加一句「停是維運員的事，你不要自己停它」，因為第 1 場 A 自己把子 daemon stop 了。

## 發現（LLM 的誤解，附證據）

1. **argv 的相對路徑以 node 為 cwd，subroot 卻是空間路徑，兩個模型都寫錯。**
   - 兩個 A 第一次都寫 `argv: ["aos7-daemon", "lab/sub"], subroot: "lab/sub"`，cwd 是 `lab`，實際指到 `lab/lab/sub`，不存在。
   - 子 daemon 退出碼 1，out.log 是「root 要是已存在的資料夾」。
   - keep 每 300 ms 再起一次，形成 **crash loop：第 1 場 69 個、第 2 場約 67 個任務資料夾**（N-29）。兩個 A 都要 10～20 秒才看到 out.log。
2. **subroot 寫錯不會被擋。**
   - 第 2 場的 A 改成 `argv: ["aos7-daemon","sub"], subroot: "sub"`。argv 對了，subroot 卻變成空間根的 `sub/`，tick 在**空間根**建了 `sub/.aosd/`（B 列根目錄看到 `.aosd/ lab/ ops/ sub/`）。
   - 能動只是因為第一次已經在 `lab/sub/.aosd/` 留了標記。subroot 跑出自己的 node，不合 S-10，tick 卻照收。
3. **先建子 node、再起子 daemon，會被父 daemon 搶走（P-11 的 LLM 版）。**
   - 第 1 場的 A 先寫 `lab/sub/w1/.aos/timeline.json`，那時 `lab/sub/.aosd/` 還不存在，父 daemon 就把 `lab/sub/w1`、`w2` 當成自己的 node，跑了 7 回合。
   - 之後 subroot 標記一出現，父那邊就當它們消失（Q4 會 kill 上面的任務）。
   - A 花了 8 輪猜「是誰起了子 daemon」（「I bet the parent daemon has a subroot auto-start」），完全沒想到是父 daemon 自己。操作卡沒寫這個順序。
4. **`stop` 帶 `node` 也被接受，結果整個 daemon 都停了。**
   - 第 1 場的 A 想「模擬維運員」，寫了 `{"op":"stop","node":"w1"}`，回條 `ok: true, "stopping"`，整個子 daemon 退出。
   - LLM 以為 stop 能只停一個 node，daemon 不吭聲就照做了。
5. **daemon 死了，寫給它的控制檔沒人回，也不會過期。**
   - 第 1 場的 B 對已經停掉的子 daemon 寫了 rescan、wake，兩個檔一直留在 `ctl/`，沒有回條。B 花了約 20 輪才確定 daemon 死了，靠的是 status 的 `at` 不動、`stopped: true`。
   - 這些檔會在子 daemon 下次被起來時才執行。如果留下的是 `stop`，起來的瞬間就又停了。
6. **路二 stop 會被路一的 keep 抵銷**（離線 naive 場、第 2 場）。
   - 起回來的是新 gen、新 pid，`stopped: false`。B 自己查到 `lab/.aos/tasks.json` 的 keep 是原因，但它只能寫子 daemon 的控制檔，沒有任何一個控制檔能說「別再起我」。
   - 被 stop 收掉的 subd 結束碼是 0，父那邊看起來跟「自己做完」一樣。
7. **長的 jsonl 只看得到開頭。**
   - log.jsonl、rounds.jsonl 一長，read_file 只回前 6000 字。三個模型都說「the log is truncated, I need the end」。B 只好用 round.json 加上時間估算「w2 停在 89」，驗不了到底是不是剛好 3 回合。
   - 只靠讀檔的操作者需要「最近 N 筆」：rounds.jsonl 沒有尾端摘要，log.jsonl 只增不減。
8. **resume rounds 的語意**：「再跑 3 回合」把當時進行中的那一回合也算進去（w2：回條之後收的是 87、88、89，87 是回條當下已經開了的回合）。B 沒有懷疑，但它也驗不了（見 7）。
9. **寫入紀錄把子 daemon 自己判成越界**：子 daemon 和它的 tick／tock 繼承了 subd 任務的 `AOS7_TASK` 與 audit hook，寫自己的根全部記成 ok:false。A 替子 daemon 建 node 也被判越界，「誰能播種子 daemon 的 node」沒有說法。
10. **呼叫數都用完了**：兩個 A 都撞到 30 次的上限，大半花在等待與猜測；沒有 sleep 工具，就只能一直重讀 status。

## 修補之後（10-03）

- **已套用**：
  - F1：stop 帶 node 回 ok:false。
  - F2：`AOS7_SUBROOT`。
  - F3：subroot 要在自己 node 底下。
  - F4：寫入紀錄把子根算任務的。
  - F5：卡與 spec 寫明順序。
  - 細節在 infra-needs N-66、N-67。
- 離線照稿版的 A 仍寫 `lab/sub` 這種舊寫法，照樣通過（subroot 在自己 node 底下）。
- D1 列成 infra-needs **Q5**；使用者 10-03 答「子 daemon 歸起它的 node，那個 node 允許 stop 才有用」，已做（`allow_stop`、owner.json、stopped.json）。離線照稿改驗新行為：A 設 `allow_stop` 那場 stop 後保持停住；naive 那場 B 的 stop 被拒。D2 取 (a)：照現在，寫明。
