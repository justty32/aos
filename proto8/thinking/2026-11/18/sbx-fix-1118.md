沙箱碰得到 daemon（11-18 沙箱檢查的 A 落差）：家機重現、根因、四個修法與要使用者裁的題（線 sbx-fix-1118）。

← [2026-11-18](README.md)｜前情：[沙箱隔離-實機檢查](沙箱隔離-實機檢查.md) 的 A｜程式與說明：[aos-sandbox README](../../../py/aos/apps/sandbox/README.md)

使用者 11-18 晚：「先派線處理沙箱那個嚴重的落差。」修法有好幾種、各有取捨，而且都會動到範本或沙箱的語意，所以**這條線沒改程式、沒改範本**，只重現、找根因、把方案擺出來。

## 先講結論

- **重現了，而且比檢查紀錄寫的更嚴重**：照起手範本掛的 agent（`-w .`，工作區＝整棵樹），它的工具就算照範例關進沙箱（只綁工作區與自己的 stack、斷網），在沙箱裡還是能：看 daemon 的表、對別隻 agent 說話、往 llm kernel 的信箱寫檔、**改 llm kernel 的定義（`kernel.json` 那夾）、改自己的定義、改根的定義**，還能**叫 daemon 再掛一隻新的 agent——那隻在沙箱外面跑**（實測，見下表第 9 條）。等於沙箱只擋得住「外面的檔」，擋不住「整棵樹」。
- **根因是佈局，不是沙箱的程式錯**：範本讓 agent 的工作區＝整棵樹，而整棵樹裡就放著它的「控制台」——根的 stack（`.stack/`，裡面有 daemon 收指令的信箱）、llm kernel 的 stack 與定義（`llms/`）、所有 agent 與根的定義（`agents/`、`root/`）。沙箱綁工作區＝把控制台一起綁進去、還可寫。
- **只搬 daemon 的 stack 不夠**：定義夾也在工作區裡，改得到自己的 `body.json` 或 kernel 的端點設定，下次重起就在沙箱外跑（這條是推論，沒實測）。
- **推薦甲＋丁**：範本給 agent 一個專用的工作夾（例 `work/`），不再用整棵樹當工作區；再讓 `ctl add` 在工作區包住 daemon 的 stack 或定義夾時印一行警告。甲已在暫存樹實測：同一份沙箱設定，九條全部擋住，agent 照常問答。

## 重現（家機 Manjaro，HEAD `01458f544`）

暫存夾 `~/.aos/scratch/sbx-fix-1118/`：`git clone` 本機 repo、清掉所有 `AOS_*`、`AOS_HOME` 指複本、乾淨 PATH、`install.py`（退 0）；`cp -r templates/start-api tree`，照[重建步驟單](../17/重建步驟單.md)第 6 步起根、起 llm kernel、`ctl add --auto-restart -w . agents/ann`（`_clock`、`_sweeper`、`ann` 都 running）。

探測用一份跟 `examples/shell-boxed` 同樣綁法的沙箱設定（`commands` 列 aos-exec、aos-agent、aos-daemon-ctl；`rw` 只有 `$AOS_WS`、`$AOS_STACK`；`net:false`），環境照 ann 的 shell 工具會拿到的值給（`AOS_WS`＝工作區、`AOS_STACK`＝`.stack/procs/ann/tools/shell`），在沙箱裡跑一支探測腳本。設定與腳本在暫存夾 `probe/`，原始輸出 `probe/A-before.log`、`probe/B-ws-subdir.log`。

| # | 沙箱裡做什麼 | `-w .`（範本現樣） | `-w work`（甲） |
|---|---|---|---|
| 2 | 列根的 stack | 看得到 `procs_state.json`、`procs_requests` 等 | 只看得到自己那格的路徑骨架 |
| 3 | `aos-daemon-ctl ls` | 印出整張表 | `StateMissing`（看不到表） |
| 4 | 對 ann 說話 | 寄進去了，ann 回 `FAKE ANSWER to: probe-from-box-A` | `StateMissing` |
| 5 | 寫 llm kernel 的 `requests/` | 寫得進 | 看不到 |
| 6 | 寫 llm kernel 的定義夾 `llms/def/` | 寫得進 | 看不到 |
| 7 | 寫自己的定義 `agents/ann/` | 寫得進 | 看不到 |
| 8 | 寫根的定義 `root/` | 寫得進 | 看不到 |
| 9 | `ctl add` 一隻新的 `esc-A` | **掛上了**：表上 running，它的父行程是 daemon、mount namespace 跟主機同一個（＝不在任何沙箱裡） | 看不到 daemon |

甲的對照另外確認 agent 本身照常：`ctl add -n ann2 -w work agents/ann` 後問一句，回 `FAKE ANSWER …`；`AOS_LLM_KERNEL` 是根的 `.env` 用根的工作區算的，所以 agent 換工作夾不影響問腦。

順帶確認：家機這台的 bwrap、s6 都在，結果跟公司 WSL 的檢查紀錄一致，不是那台特有的。

## 為什麼會這樣（三層各管一點）

1. **範本的擺法**：`start-api`、`start-eca` 的 README 與重建步驟單都寫 `ctl add -w .`；`daemon-root` 的 README 寫明「`-w .`＝工作區是專案資料夾」，而那個專案資料夾裡同樣放著 `stacks/root` 與 `defs/`。不算 thinking 的舊紀錄，還有十來個檔這樣寫（公開文件 `docs/zh/` 三頁、知識庫 `cli/agent.json`、aos-agent 搬家說明、`kits` README、11-18 的教學與重建紀錄），是一個慣例，不只一份範本。
2. **daemon 的 stack 放在它的工作區裡**：根在樹裡起、stack 就是樹裡的 `.stack/`（portable-flow 那套「daemon 在 ws 裡起、`cd ws` 就找得到 `./.stack`」，使用者 11-05 裁的）。agent 又沿用同一個工作區，就一起包進去。
3. **沙箱照設定綁、不另外遮**：`rw` 綁一個夾就是整夾可寫，包含底下的 stack 與定義。aos-sandbox README 早就寫了「daemon 的 stack 放在工作區裡時，綁 `AOS_WS` 就已經把整台 daemon 綁進去了……要真的關住，daemon 的 stack 別放在工作區裡」，但範本本身就是這個佈局，照做的人不會想到。

沙箱的程式本身沒有錯：它照設定綁、綁的範圍也算對。問題是「工作區」這個詞在範本裡等於「整棵樹＋控制台」。

## 修法

### 甲：範本給 agent 一個專用工作夾（推薦）

樹裡多一個 `work/`（名字可換），`ctl add -w work agents/ann`；要 agent 做某個專案就 `-w <那個專案>`（放樹外也行，像 realmodel-home-1118 那條線用 `-w ../box-ws`）。根照舊在樹裡起、stack 照舊是 `.stack/`。

- 好處：一次解掉九條（stack、信箱、定義都不在工作區裡）；daemon 的 stack 位置不動，portable-flow 那套照舊；整棵樹連 `work/` 一起搬家照舊；不改沙箱與 daemon 的程式。
- 代價：「`-w .`＝工作區是專案資料夾」這個慣例要改成「工作區是樹裡的 `work/`，或你的專案夾」，十來個檔要改（範本 README 五份、步驟單第 6 步、知識庫 `cli/agent.json`、`docs/zh/` 三頁、搬家說明、11-18 教學；更早的 thinking 紀錄不改）；agent 的工作區裡不再有樹的定義（本來也不該讓它改；在沙箱裡要讀自己定義的工具〔self_tools 等〕本來就要另外唯讀綁定義夾，aos-sandbox README 已寫）。另外教學那幾份正被 eca-lab 線改著，要等它交了再動。
- 要裁的細節：夾名（`work`／`ws`／別的）；`daemon-root` 那份（專案夾裡放 `stacks/`、`defs/`）要不要一起改；`templates/tests/test_start.py` 若要範本帶一個空的 `work/`，git 不收空夾，得放一個說明檔。

### 乙：daemon 的 stack 搬出工作區

例 `.stack/` 改到 `~/.aos/stacks/<樹名>/` 或樹外的旁邊。

- 好處：控制信箱（第 2～5 條）不在工作區裡了。
- 代價：**第 6～8 條照舊**（定義還在工作區裡，可以改自己的 `body.json` 或 kernel 的端點設定，下次重起就在沙箱外跑——推論、沒實測）；跟 portable-flow「`cd ws` 就找得到 `./.stack`」衝突，搬家要多搬一處。單用不夠，不推薦。

### 丙：aos-sandbox 自動遮住控制台

`rw` 的某條路徑包住 `$AOS_DAEMON`、`$AOS_LLM_KERNEL`、`$AOS_KERNEL` 或自己的定義（`$AOS_CD`）時，沙箱自動把那幾條改成唯讀（自己那格 stack 照舊可寫，因為「深的那條說了算」）。

- 好處：範本不用動，照現樣擺也關得住大半。
- 代價：改了沙箱的語意——現在是「設定說了算、白名單」，多一條看不見的規則；而且遮不全：llm kernel 的定義夾（`kernel.json`）、根的定義、別隻 agent 的定義都沒有環境變數可指，第 6、8 條還是寫得到。

### 丁：只加警告（可跟甲合用）

`aos-agent ctl add` 發現工作區包住 daemon 的 stack、llm kernel 的 stack 或定義夾時，stderr 印一行 `warning`（照常掛上）；或改由 aos-sandbox 在 `rw` 包住 `$AOS_DAEMON` 時警告。

- 好處：小、不改行為，跟使用者 11-12「設定寫壞照跑、出事自己負責」的精神一致；甲改完之後還照舊寫 `-w .` 的人會被提醒。
- 代價：只提醒、不擋；單用的話範本照現樣擺，每次掛 agent 都會冒一行警告。

## 使用者裁定（11-18 晚，頂層轉）

選項框選「先不修，只寫 README」，之後原話：「好，沙箱這個基本上是使用者要自己承擔的風險吧。」

照做：不改程式與範本行為，只在 [aos-sandbox README](../../../py/aos/apps/sandbox/README.md)、[start-api](../../../templates/start-api/README.md)／[start-eca](../../../templates/start-eca/README.md) README、公開文件 `docs/zh/manual/security.html` 的沙箱段寫明：`-w .` 掛的 agent 在沙箱裡碰得到整棵樹的控制台，是使用者自己承擔的風險；要隔得乾淨就用專用工作夾（例 `-w work`）。教學那幾份正被 eca-lab 線改著，沒碰。

## 要使用者裁的題（已裁，見上）

1. 用哪個修法：**甲＋丁（推薦）**／只甲／丙／乙＋丙／先不修，只在範本 README 寫清楚。
2. 選甲的話：工作夾叫什麼（推薦 `work`；`ws` 跟環境變數 `AOS_WS` 同名，容易混）；`daemon-root` 範本與公開文件的 `-w .` 一起改（推薦）還是只改兩份起手範本。
3. 選丁的話：警告放 `ctl add`（推薦，掛的當下就看到）還是 aos-sandbox（真的關沙箱時才看到）。

## 這次順帶碰到的

- **私人 tmux 伺服器會被 tmux-continuum 灌進使用者的 session**：家機的 `~/.tmux.conf` 開了 `@continuum-restore 'on'`，`tmux -L <私人名>` 開新伺服器時，它把使用者存的九個 session（各專案夾的 zsh）在我的伺服器裡復原了一份；收尾時 `tmux -L sbxfix kill-server` 一起收掉，resurrect 的存檔沒被蓋（最後一份還是 11-08）。之後開私人 tmux 要加 `-f /dev/null`。
- 活樹 `~/aos-home` 沒看（規矩不碰）；它若是照步驟單 `-w .` 掛的，狀況相同，但只有在把工具關進沙箱、又指望沙箱擋住時才算漏。
- 收尾：兩台 daemon `shutdown`（5＋1 個 procs 睡下）、私人 tmux 收掉、`pgrep` 確認沒留我的行程；暫存夾都留著，沒刪任何東西。
