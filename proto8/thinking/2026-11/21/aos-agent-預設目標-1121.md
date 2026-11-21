# aos-agent 不給 -t 時從 cwd 找目標；不給 -d 時從那個 stack 往上兩層找 daemon（線 top-1121-deft，11-21）

← [2026-11-21](README.md)｜前情：[default-stack-1118](../18/default-stack-1118/README.md)（11-18 暫定丁、[05 11-20 補充](../18/default-stack-1118/05-使用者補充-1120.md)）｜同天的盤點：[aos-daemon-env-1121](aos-daemon-env-1121.md)

## 使用者原話（11-21，頂層轉述、逐字）

「對了，昨晚我記得有記一些筆記，其中一個是關於aos-agent -t xxx的這個-t xxx可以省略的。我覺得可以做。首先是-d不能省略，要麼-d明確指定，要麼export AOS_DAEMON指定。然後是-t xxx沒寫，AOS_AGENT又沒有的時候，會找./.stack內有沒有一個特徵檔(interfaces.json?)，可以讓我們跑aos-agent相關指令。沒有./.stack那就找./」

同天補的一句（關於丁）：

「agent記自己在哪個daemon底下...這個想法我覺得不行，agent不該和daemon耦合。這是爲了可遷移性，這樣我可以直接把相關資料夾複製一份丟到別的地方，用另一個daemon跑。這個也可以順便幫我調查一下可行與否。」

（「可行與否」那份調查是線 `top-1121-daemonenv` 做的，見上面「同天的盤點」。）

## 做成什麼樣

只改 `aos-agent`。

| 要知道的 | 依序看 | 都沒有 |
|---|---|---|
| 哪台 daemon | `-d D` → `$AOS_DAEMON` | `DaemonMissing`（不看 cwd） |
| 哪一隻 | `-t NAME` → `$AOS_AGENT`（空字串＝沒設）→ `./.stack` → `./` | `TargetMissing`，訊息列出四處各缺什麼 |

`./.stack`、`./` 怎麼算數：夾裡有 `stderr.txt`，**而且**它的真實路徑是 daemon 表上某一列的 `stack`，就用那一列的名字。表上本來就記著那隻的定義夾、工作區，所以 `tools`、`llm`、`system`、`hook`、`open` 這些要定義夾的子指令也照樣能用，全部子指令都能省 `-t`。

例子（先 `export AOS_DAEMON=<樹>/.stack`）：

```sh
cd <樹>/.stack/procs/ann && aos-agent ask hello     # 對 ann 說
cd <工作夾> && aos-agent ctl where                    # 工作夾的 .stack 是某隻的 stack＝那隻
cd <樹>/.stack/procs/ann && aos-agent -t bob say hi   # -t 贏
cd <樹> && aos-agent say hi                           # TargetMissing：樹根的 .stack 是 daemon 的
```

家機暫存樹（start-api、假腦）實跑全過，輸出貼在 [aos-agent docs/01「cd 進 agent 的 stack 就不用 -t」](../../../py/aos/apps/agent/docs/01-用法例子.md)。

## 特徵檔選 `stderr.txt`，不是 `interfaces.json`

- stack 裡的 `interfaces.json` 不是每隻都有：它是 agent 第一次呼叫工具、記帳時（`aos-observed`）才寫的。暫存樹實測，問過一句的 ann 有，掛上沒說過話的 bob 沒有。工具的小格（`<stack>/tools/<名>/`）也可能有一份，會認錯。
- 定義夾裡的 `interfaces.json` 一定有，但一份定義可以掛好幾隻，站在定義夾裡認不出是哪一隻。
- `stderr.txt` 是 daemon 每次起 proc 時在它的 stack（小格）建的，loop 型、exec 型都有，跟定義是哪一種無關；樹根的 `.stack`（daemon 自己的 stack）沒有它，所以站在樹根不會把 daemon 當成 agent。
- 不管特徵檔是哪個，最後拍板的都是「表上有沒有這個 stack」；特徵檔只是先篩掉明顯不是的夾，順便讓錯誤訊息說得清楚。

## 邊緣狀況怎麼處理

- `./.stack` 在、但沒有 `stderr.txt`（例如樹根）：繼續試 `./`。把他的「沒有./.stack那就找./」讀成「沒有 agent 的 `./.stack`」。
- `./.stack` 有 `stderr.txt`、表上卻沒有這個 stack（不是掛在 `-d` 那台底下、或已經 `ctl rm`）：`InstanceMissing …/.stack looks like an agent's stack … but no agent on the daemon table D has that stack`，不再試 `./`、不去猜別台。
- `AOS_AGENT=""`：當沒設，往下看 cwd。
- `-t` 與 `AOS_AGENT` 都有：`-t` 贏（照舊）；兩個都有時不看 cwd。
- 站在 stack 的子夾（`think/`、`tools/<名>/`）：不往上找，`TargetMissing`。
- 從 cwd 找到時不在 stderr 印提示：舊的 daemon 從 `./.stack` 找到時也沒印，照這個慣例；要確認是哪隻用 `ctl where`。
- agent 自己的 proc 裡（daemon 給了 `AOS_DAEMON`、`AOS_STACK`）：daemon 那邊不受影響。loop 型的 cwd 是自己的 stack，所以工具裡不帶 `-t` 打 aos-agent，以前是 `TargetMissing`，現在會對到自己；出廠的工具都帶 `-t` 或用 `ctl who`，全套測試沒有因此變紅。
- 設了 `AOS_KERNEL`、沒給 `-d`：照舊問 kernel 要表，cwd 找目標也用問來的那份表。這條路本來就不讀 `AOS_DAEMON`，沒動。
- `ctl add`／`rm`／`set-def`／`ls`／`who` 本來就不吃 `-t`，也不從 cwd 找。

## -d 不再從 cwd 猜

`aos-agent` 原本 `-d` ＞ `AOS_DAEMON` ＞ cwd 的 `./.stack`（11-05 portable-flow 題 3）。照今天的話拿掉第三步，而且 `./.stack` 現在是用來找 agent 的，兩種意思不能並存。共用的 `daemon_ctl.find_daemon` 加了 `cwd=False` 參數，只有 aos-agent 傳；`aos-daemon-ctl`、`aos-sweeper`、`aos-mailbox`、`aos-eca-screen` 照舊會看 `./.stack`。`using-aos-agent.sh` 原本在 `AOS_DAEMON` 沒設時替你設成 `$PWD/.stack`，這也是從 cwd 猜，一起拿掉。

連帶的影響：人在殼裡 `aos-exec agents/x`（定義的 `_entry` 是 `aos-agent ctl add`）要先 `export AOS_DAEMON`，不然 `DaemonMissing`。範本 README 的指令本來就都寫 `-d .stack`，不受影響。

## 丁的去留

不做丁。stack 和定義夾裡都不寫「屬於哪個 daemon」，找目標時也不讀這種檔；daemon 只從 `-d`／`AOS_DAEMON` 來（第二輪起也可從 stack 所在的位置往上兩層找，見文末；照樣不讀 stack 裡的檔），執行時拿 stack 路徑去那台的表上對。程式裡沒找到丁的殘留：沒有任何地方把 daemon 寫進 agent 的檔（daemonenv 那份盤點也是這個結論）。

## 要給條文加註的字（`proto8/docs/` 沒改）

- N-63（`docs/NORMS/10-…/07-…/02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md`）寫「`./.stack` 是 `AOS_DAEMON` 唯一一條退路」：建議加註「11-21 起 aos-agent 不走這條退路：`./.stack` 在 aos-agent 改成找目標 agent，daemon 改從那個 agent stack 往上兩層找（第二輪）；aos-daemon-ctl 等照舊」。

## 沒做的

- `aos-agent` 以外吃目標 agent 的指令沒動：`aos-hook … --agent`、`aos-gdb NAME`、`aos-daemon-ctl`（`where`／`stop` 等吃名字）、tools 的 `self_*`（本來就用 `ctl who` 認自己）。它們不共用 `common.target`。
- 範本、教學裡「站在樹根不帶 -d」的寫法沒逐一翻；範本 README 歸別條線，而且出廠範本本來就寫 `-d .stack`。
- 想問使用者的（沒問）：要不要在 stack 裡記「定義夾、工作區在哪」，好讓沒掛在任何 daemon 上的 stack 也能下 aos-agent 指令——這牽涉可遷移性，是新的設計決定，這次沒做。

## 使用者對特徵檔的回應（11-21，頂層轉逐字）

頂層轉述「特徵檔用 `stderr.txt`，不是 `interfaces.json`」後，他說：「特徵檔竟然是用stderr.txt嗎？好，沒關係，反正這本來就是一種tricky式的非正規用法，本來就要求使用者自己要把握好，至少自己稍微看過，確定這是agent stack」

結論：`stderr.txt` 照用。從所在資料夾找目標是非正規的便利用法，認對 stack 的責任在下指令的人。

## 第二輪：-d 也能省，往上兩層找（11-21，頂層轉逐字）

「啊，既然是tricky用法...那也幫我把-d省略也做一下吧，弄成往上兩層去找，因爲默認是.stack/procs/ann這樣。」

這句取代了上面「-d 不再從 cwd 猜」的一部分：daemon 現在也能從 cwd 找，但只認「agent stack 往上兩層」，樹根的 `./.stack` 本身照樣不當 daemon。

| 要知道的 | 依序看 | 都沒有 |
|---|---|---|
| 哪台 daemon | `-d` → `$AOS_DAEMON` → cwd 認出的 agent stack 往上兩層 | `DaemonMissing`，訊息寫試過哪裡 |
| 哪一隻 | `-t` → `$AOS_AGENT` → `./.stack` → `./` | `TargetMissing` |

「cwd 認出的 agent stack」跟找目標用同一套：`./.stack` 先、再 `./`，第一個有 `stderr.txt` 的夾說了算。往上兩層那個夾要有 `procs_state.json`（是 daemon 的 stack），而且表上有一列的 stack 就是它；不成就 `DaemonMissing`，不再試別處。只看路徑的位置，stack 裡照樣不記、也不讀「屬於哪個 daemon」，整夾搬到別台的 `procs/` 底下照樣認得。

例子（都不設 `AOS_DAEMON`）：

```sh
cd <樹>/.stack/procs/ann && aos-agent ask hello        # daemon＝<樹>/.stack，目標＝ann
cd <樹>/.stack/procs/ann && aos-agent -t bob say hi    # 同一台的 bob
cd <樹>/work2 && aos-agent ctl where                    # cal 用 -s work2/.stack 掛的：往上兩層是 <樹>，DaemonMissing
cd <樹> && aos-agent ctl ls                             # 樹根：DaemonMissing（./.stack 本身不當 daemon）
```

家機暫存樹實跑四條都照上面；新增的測試 3 項（共 9 項）都過。

替使用者做的選擇：

- 給了 `-t` 或 `AOS_AGENT`、沒給 `-d`／`AOS_DAEMON` 時：照樣用 cwd 的 agent stack 往上兩層當 daemon，再到那台的表上找 `-t` 那個名字。理由：daemon 跟目標各自照自己的順序找，規則簡單；站在 ann 的 stack 裡對同一台的 bob 下指令也不用多打 `-d`。
- 不需要目標的動作（`ctl ls`、`ctl add`、`ctl who`…）也照這條找 daemon：找 daemon 的地方只有一個，沒有分開處理。
- `-s` 掛在別處的 stack（例如 `ws/.stack`）往上兩層不是 daemon，就是 `DaemonMissing`，不往更上層找。原話只說「往上兩層」。
- 設了 `AOS_KERNEL` 照舊問 kernel，不往上找。
- 照使用者說的「本來就要求使用者自己要把握好」，不加防呆提示，找到時也不在 stderr 印東西。
