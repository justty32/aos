git-image 發現 4～5（極限情境跑不到、雜項）與已核對清單
← [入口](../04-設計規劃.md)｜上一份 [02-git-image](02-git-image.md)｜下一份 [02-續2-git-image決策表](02-續2-git-image決策表.md)

### 4. 極限情境跑不到，外推數字嚇人過頭；「不隨週數長」自相矛盾
- **類別**：設計（調查品質）｜**嚴重度**：品質
- **檔:行**：`02-極限分析.md:7,12`；`03-實測數據.md:5,81,84`；`README.md:18`；`proto8/templates/agent-fsm/brain.py:182`；`proto8/kernel/llm-kernel/kernel.json:7`
- **commit／哪隊**：`04185730c`（I 隊，sol）
- **問題**：
  - 情境是一隻 agent 跑 10080 輪，每輪長 3 KB。可是 brain 每一題都把整份 history 送出去（`brain.py:182`），smart-high 的 context 上限是 200000 token，大約 260 輪就撞頂，之後就是 `BrainFailed`、停下等人。70 GiB、0.8 GiB 都建立在這個做不到的情境上。
  - 數據全是用隨機詞組成的假樹，沒有拿真的 stack 量（試驗場實跑被砍了，03:96）。
  - 03:84 寫「0.8 GiB，不隨週數長」，可是 README:20 自己說「image 本身還是會線性長」。實際上它是「不隨 commit 次數長」，會隨週數長。
  - 結論的方向（擋 request 和 log、只留最新）不受影響。
- **使用者原話**：「討論在極限狀況下……是否會導致膨脹無法遏止」（`README.md:7`）
- **建議**：可以直接修，在 03 補一句「單隻 agent 的 history 被 context 上限卡住；真正的極限是 agent 數 × 約 1 MB」，84 行改成「不隨 commit 次數長」。

### 5. 雜項（品質）
- `README.md:52` 還寫著「依本次指示未 commit，沒有 commit hash」，實際上已經是 `cf5799221`（Z 隊）。
- 量測腳本的 ignore 規則（`gitimage_bench.py:22-43`，`**/queue.json`、`.trash/`）跟落地範本不一樣（`/queue.json`、根 `ws/.trash/`），03 沒有註明。

### 已核對沒問題的
- wait 格（`proto8/templates/agent-fsm/wait.py:112-114`）：沒有 pending 也沒有 request 時退 11 回 think 重組，就是使用者點的選項原文（`04185730c` 的 README 方向題 2：「wait 格找不到這個檔，就退回 think 重組」）。「有 pending 時先收原回信」可以從「不重寄」推出來，不算代定。think 重跑沒有副作用（`brain.py` 只讀 history，寫 request）。
- 擋 request 時的 kernel 回錯路徑：以前人重跑是「重寄」，現在是「重組再寄」，結果一樣。
- 時鐘檔 `<daemon stack>/tick`（`impls/aos-daemon/src/daemon/daemon.hpp:14`）沒被擋，凍住後 tick 數會帶走，符合 fs-image「凍住＝時間沒走」。
- `used.json`、`pending.txt`、在途信箱 `new/`／`cur/`、`think/reply/` 都沒被擋；沒有出現 `**/cur/` 這類太寬的規則。`endpoints.json` 是 kernel 每拍重寫的表，擋了沒差。
- 這次實驗之後，`git ls-files` 裡沒有任何 `request.json`，`**/think/request.json` 規則有效。
- `/queue.json` 依任務書沿用 A 區第 4 條，不重審。
- 專門 repo、orphan commit＋`push --force`＋tag：寫在 sol 方向題 1 推薦選項的原文裡，使用者點了這一項，不算 sol 擅自代定。
