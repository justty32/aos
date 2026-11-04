← [2026-09-25-company](../README.md)｜入口：[examples/company/README.md](../../../examples/company/README.md)

# 試玩：新使用者只拿公司樣板 README 開一家公司＋走一輪市場層

2026-09-25 12:32～12:50，試玩員（第一次碰這個專案）。規則：只看 [examples/company/README.md](../../../examples/company/README.md) 與它連到的東西（這次只多看了它指去的 [spec/team/market.md](../../../spec/team/market.md)）；不看 lib 原始碼、不看 notes。
實例放 `~/tmp/company-play/`（README 寫的是 `~/tmp/company-run/`，我照樣改路徑）。模型只走 LiteLLM `localhost:4000`，真的叫模型的 `order` 只跑 1 次。

## 1. 逐步紀錄

### 1-1 專案副本（照 README〈跑一家〉前三行）

```sh
mkdir -p ~/tmp/company-play/c1
rsync -a --exclude=.git --exclude=aos-runs ~/tmp/arknights-try/ ~/tmp/company-play/c1/proj/
ln -sfn ~/tmp/arknights-corpus ~/tmp/company-play/c1/arknights-corpus
```

一次成功。`proj/corpus/raw`、`extracted` 是 `../../arknights-corpus/…` 的相對連結，照 README 的 `ln` 就解得開。
疑慮：`~/tmp/arknights-corpus` 本身指向 `~/repo/narratives/arknights/corpus`（本尊）；README 寫「corpus 唯讀」，但沒說是誰保證唯讀。事後查過：跑完後本尊語料 0 個檔被改。

### 1-2 `new`

```text
$ python3 company.py new ~/tmp/company-play/c1 --prefix c1- --project ~/tmp/company-play/c1/proj
生好了 /home/lorkhan/tmp/company-play/c1：c1-hq-lead、c1-mfg-lead、…、c1-lib-librarian；正式 7/10、cpu 17/20、llm cpu 5/5
```

成功。**但印的是 `cpu 17/20`**：README 的組織圖寫 `cpu 12/20（cpu 不含 llm）`，`up` 之後的 `status` 也印 12/20。`new` 印的是 12＋5，同一個數字有兩種算法。
（用 `--llm-cpu 4` 開的假公司則印 `cpu 16/20`，同一個問題。）
`company.py new --help` 每個參數都沒有說明文字（`--prefix`、`--from`、`--name` 是什麼只能猜）。

### 1-3 換模型（README 沒寫，卡了一下）

任務要我用最便宜的模型。README 只說 `llm.json` 放「模型代號」，**沒說怎麼換成員用的模型**。我自己找到實例裡 `teams/*/team.json` 的 `"model"`，把 5 個 `gpt-5.5` 用 sed 改成 `deepseek-chat`（只改 `~/tmp` 裡的實例，沒動 repo）。新使用者不容易猜到「要改實例的名冊」，也不知道改了之後會不會被 `up` 蓋回去（實測沒有）。

### 1-4 `up`

```text
$ export AOS_COST_HOME=~/tmp/company-play/cost
$ python3 company.py up -C ~/tmp/company-play/c1
kernel 開了：/home/lorkhan/tmp/company-play/c1/K（default 12、llm 5 顆）
hq 部開工：c1-hq-lead
…
總機開了：company-relay-3d27c1d4（每 5 秒一輪）
```

4 秒跑完，一次成功，訊息清楚。沒提到 daemon 開在哪；事後在 `kernel.json` 才看到是 `~/tmp/company-play/D`（公司資料夾的**上一層**）。README 沒說，所以 `~/tmp/company-play/` 底下會多一個沒預料到的 `D/`。

### 1-5 `status`（下單前）

```text
公司 c1（startup）  kernel up
正式 7/10、cpu 12/20、llm cpu 5/5  （臨時工 0，不算人頭）
  hq    總裁辦      teams/hq           成員 1  單 0 進行／0 全部  等人答 0  有：總裁一人，兼業務與 HR 決策
  …
董事收件匣：0 封（company.py mail 看）
```

好讀。每列尾巴的說明很長，終端機會折行，但內容有用。

### 1-6 `order`（唯一一次真跑）

```text
$ python3 company.py order -C ~/tmp/company-play/c1 "補人物 老財"     # 12:33:11
沒有規則命中，已交給領隊 c1-hq-lead：1790310791505190193-567770-human
```

第一次看到「沒有規則命中」會以為出錯了；其實 README 說過門房沒命中就交給總裁，這是正常的路。建議改成「交給總裁 c1-hq-lead（門房沒有對應規則）」。
**README 沒說怎麼知道單做完了**。我每 15 秒跑一次 `status`，看到的過程：

| 時間 | 看到 |
|---|---|
| 12:33:32 | 總機 o-0001 `hq → mfg open 補人物 老財（只寫詞條）` |
| 12:36:03 | o-0001 拿到任務單 t-0001（寫手在做） |
| 12:38:18 | o-0001 done；總裁開了 o-0002 `hq → qa 驗貨 老財` |
| 12:38:37 | **董事收件匣出現品管檢驗員寄給「董事」的 DONE**（其實是給總裁的回覆，只是總機還沒搬走） |
| 12:38:54 | 總裁寄給董事的結案信到了；品管那封從董事收件匣消失 |

中途想看部門細節，README 說用 `aos-team mail --target …`，但 **`aos-team` 不在 PATH**，README 也沒說它在 `proto5/cli/aos-team`。我猜到路徑後，`python3 cli/aos-team task ls --all --target …/teams/mfg` 可以用。

### 1-7 `mail`

```text
09-25 12:38  hq   c1-hq-lead → 董事  DONE  o-0002  老財 已補完：mfg 寫成 lore/characters/老財.md 與 lore/evidence/characters/老財.md（未動索引與計數）；qa 抽驗 3 列全數對得上原文…
```

結案信寫得清楚。`qa-reports/老財.md` 第一行是「結論：合格」。
小坑：12:38:37 那一刻，董事收件匣會短暫出現「部門寄給董事」的內部回覆，幾秒後被總機搬走，數字又變回原樣。我原本拿「收件匣 ≥ 2 封」當結束條件，結果多等了 9 分鐘（這是我的錯；但如果 README 寫「看到總裁寄來的 DONE／FAILED 就是結案」，就不會猜錯）。

### 1-8 `down`

```text
$ python3 company.py down -C ~/tmp/company-play/c1
hq 部收工 / lib 部收工 / mfg 部收工 / qa 部收工 / rd 部收工 / kernel 關了
$ python3 company.py status -C ~/tmp/company-play/c1 | head -1
公司 c1（startup）  kernel up        ← 剛說關了，這裡還說 up
```

- 行程：開始前和關機後的 `ps` 清單逐行相同，沒有殘留；`K/kernel.log` 最後一筆是 `stopped`。所以**實際上是乾淨的，只是 `status` 誤報 `kernel up`**。
- `down` 沒印「總機撤了」（`up` 有印「總機開了」），看不出總機有沒有收掉。實測總機的行程也沒了。

### 1-9 市場層（假資料，不開機、不叫模型）

README〈開幾家〉只示範 `open` 與 `pool`，其他步驟要去 [market.md](../../../spec/team/market.md) §3 看。我用獨立的 `AOS_MARKET_HOME=~/tmp/company-play/mkt`、`AOS_COST_HOME=~/tmp/company-play/mkt-cost`，開了三家 `m1～m3`（`new --llm-cpu 4`，不 `up`）。

| 步驟 | 打了什麼 | 看到 |
|---|---|---|
| open | `market.py open m$i ~/tmp/company-play/mkt/m$i` ×3 | `開了 m1…`；`pool`：名額剩 70／140／8，錢是 `{}`（沒設 `total` 就不管錢） |
| score | `score m1 --quality 85 --seconds 300`；m2 70／200；m3 40／600 | 每家印一行 JSON（`source: manual`） |
| rank | `market.py rank` | 表格：m1 67.67、m2 67.00、m3 32.33；**「省」三家都是 0.0**（三家都花 0 token，照理應該並列最省） |
| grant | 先 `--dry-run`，再 `grant --usd m3=-1.0 --tokens m3=-2000000`（用負數覆寫把 m3 收光，好測倒閉） | m1 0.875 美元／1,749,999 token（44%）、m2 0.625／1,250,000（31%）、m3 **-1.0（25%，覆寫）**；負數照收、沒有警告，括號裡的 25% 也不對 |
| bankrupt | 先 `--dry-run`，再真跑 | `m3 倒閉：…名額回總池 {"regular": 10, "cpu": 20, "llm_cpu": 4}；放出 7 個名字；封存到 …/archive/m3-bankrupt-…`；資料夾真的搬走了 |
| merge | 先 `--dry-run`，再真跑 | 計畫清楚：兩個經理裁掉，寫手／審查／檢驗員轉成正式，工具匠／館員因為正式名額滿了轉成臨時工；`m2 併進 m1：5 人轉入、2 人裁掉；餘額轉 {"usd": 1.625, "tokens": 3250000}`；m1 的名冊真的多了 `employment: temp` 的列 |

六步全部一次成功。每一步都有 `--dry-run`，用起來很安心。不順的地方：`market.py --help` 裡 `open／score／rank／grant／bankrupt／merge／ls` 都沒有一句說明（只有 `close／pool／slots` 有），`score` 的 `--hops`、`--eval` 也沒說明。

## 2. 五條標準

| 標準 | 分數 | 一句理由 |
|---|---|---|
| README 能不能一次照做成功 | **4** | 八條指令都一次成功；扣分在沒寫怎麼換模型、`aos-team` 在哪、怎麼判斷單做完了，市場層也只示範 open／pool |
| 出錯訊息看不看得懂 | **3** | 這次沒真的出錯，但有三個「看起來正常、其實誤導」的訊息：`new` 印的 cpu 17/20、`down` 之後 `status` 說 kernel up、負數撥款照收還標 25% |
| 概念第一次讀懂沒 | **4** | 公司／部門／總機／董事那張對照表一讀就懂；正式／臨時、「總池」要到 market.md 才懂；董事收件匣短暫出現內部信，會讓人以為總機壞了 |
| 指令名字與參數直不直覺 | **4** | `new／up／order／status／mail／down` 跟 `open→score→rank→grant→bankrupt→merge` 都是字面意思；`--help` 幾乎沒有說明文字，要回 README／spec 查 |
| 關機後乾不乾淨 | **4** | 行程跟開始前逐行相同、kernel 記錄也停了；扣分在 `status` 仍說 kernel up、`down` 沒說總機撤了沒，還有一個 README 沒提到的 `../D/` 留在公司資料夾外面 |

卡住次數：**0 次真的卡死**；3 次要自己摸索（換模型、找 `aos-team`、判斷結案）。

## 3. 我會改的三件事（給研發部，只寫不做）

1. **README 補三小段：換模型、找工具、看結案。** 「成員用的模型寫在實例的 `teams/<部門>/team.json` 的 `model`，`new` 之後、`up` 之前改」；「`aos-team` 是 `proto5/cli/aos-team`」；「董事收件匣出現總裁寄的 DONE／FAILED 才算結案，中途可能短暫看到部門的內部回覆」。再加一句成本提醒：這次全用 deepseek-chat，一張單就花了 **451 萬 token**，比市場層的開辦費（200 萬 token）還多——照預設參數，一家公司跑一張單就會倒閉。
2. **同一個數字只准有一種算法，狀態要說實話。** `new` 印的 cpu 改成跟 `status` 一樣不含 llm（12/20）；`down` 之後 `status` 不要再說 `kernel up`；`down` 補印「總機撤了」和 daemon 有沒有關；README 提一句 daemon 會開在公司資料夾上一層的 `D/`。
3. **市場層補說明和防呆。** `market.py` 每個子指令補一句 help；`grant` 的負數覆寫要嘛擋掉、要嘛明講「這是收回」，也不要照舊印百分比；三家都花 0 token 時，「省」應該並列 100（或都不算），而不是都 0；README〈開幾家〉直接給一段「用假資料走完 open→score→rank→grant→bankrupt→merge」的範例（上表那幾行就夠），不用再跳去 spec。

## 4. 真跑 1 次的結果

| 項目 | 數字 |
|---|---|
| 單 | `order "補人物 老財"`（c1，前綴 `c1-`） |
| 結果 | **成功**：製造部 t-0001 一次過（驗收＋審查），品管「結論：合格」，總裁寄董事 DONE（o-0002） |
| 秒 | **約 343 秒**（12:33:11 下單 → 12:38:54 總裁結案信） |
| 模型次數 | **126 次**，全是 deepseek-chat（寫手 82、審查 30、總裁 7、檢驗員 7） |
| token | 4,513,016（prompt 4,489,521＋completion 23,495；寫手一人就 379 萬） |
| 路徑 | 董事→總裁→〔總機 o-0001〕→製造→〔總機〕→總裁→〔總機 o-0002〕→品管→〔總機〕→總裁→董事 |

跟報告裡 gpt-5.5 的第 2 次真跑（34 次、89 萬 token、3 分 26 秒）比：換成 deepseek 也做得成，但寫手的呼叫次數約 4 倍、token 約 5 倍，也多花 2 分多鐘。
