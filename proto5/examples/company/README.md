← [proto5 README](../../README.md)｜規格：[spec/team/company.md](../../spec/team/company.md)｜比喻版：[playbook/company.md](../../playbook/company.md)｜報告：[notes/2026-09-25-company](../../notes/2026-09-25-company/README.md)

# 公司樣板：用 aos 團隊蓋一間新創公司

董事（使用者）說：「就當做是開公司，業務就是產出 narratives……我要的是用我們現有的 aos 體系去建立這個公司架構。」
這裡就是那間公司：**每個部門是一支真的 aos 團隊**（`team.json` 名冊＋成員的家），部門之間的信由一支**不叫模型的總機**搬，董事就是 `human`。

| aos 的東西 | 在公司裡是 |
|---|---|
| `human`（`aos-team ask`／`answer`／收件匣 `team/human/`） | **董事**：出資、下單、拍板。永遠是人 |
| hq 團隊的領隊 `hq-lead` | **總裁**：把董事的話翻成給部門的單、追到結案、回報 |
| 一支團隊（`teams/<部門>/`） | 一個部門；名冊的成員＝員工 |
| 成員有家、`notes: true`、記憶留著 | **正式員工**（算人頭） |
| `spawn_member` 生的成員、一次性模型呼叫（評審）、機械程式（郵差、驗收員、門房、心跳、總機） | **臨時工**／「當工具看待」，不算人頭 |
| 信（`team_say`）、任務單（`handoff`）、郵差 | 部門內的往來 |
| 總機（`company.py relay`，§3 of [company.md](../../spec/team/company.md)） | 部門之間的往來：信第一行寫 `〔給 mfg〕…` |
| 心跳 routines | 季度節奏（例行單） |
| `aos-team verify`／審查員 | 驗貨 |
| `aos-team score`、HR 試用 | 考核 |
| kernel 的池（`pools.default`／`pools.llm`） | cpu／llm cpu 名額（硬上限） |

## 組織圖（新創期：正式 ≤10、cpu ≤20、llm cpu ≤5）

現在的編制：**正式 7 人**、還有 3 個名額可以擴編；cpu 12／20（default 池；cpu 不含 llm，同 HR 的算法）、llm cpu 5／5。十個名額不夠每部門都放人，所以兼任與「純機械部門」是常態，兼任寫在 `company.json` 的 `staff.*.roles`；正式／臨時看名冊的 `employment`（HR 部）。

| 部門 | 團隊資料夾 | 成員（名／模板／模型／類型） | 多掛 | 收什麼單 | 交什麼貨 | 對應的 lib／spec | KPI（機械量得到） | 狀態 |
|---|---|---|---|---|---|---|---|---|
| **董事會** | —（`human`） | 使用者本人 | — | — | 方向、拍板、抽查 | [ask.md](../../spec/team/ask.md)、`company.py order／mail／answer` | — | 有 |
| **總裁辦** hq | [teams/hq](teams/hq/team.json) | `hq-lead`／lead／gpt-5.5／正式（**總裁，兼業務、兼 HR 決策**） | — | 董事的一句話（`company.py order` → hq 門房 → 總裁） | 給部門的〔給 …〕單；給董事的結案信 | [route.md](../../spec/team/route.md)、[company.md](../../spec/team/company.md) | 董事下單到結案信的秒數；總機單結案率 | 有 |
| 業務部 sales | 併在 hq | 門房（機械，hq 的 [routes.json](teams/hq/routes.json)）＋總裁兼判斷 | — | 董事一句話 | 命中門房就直接做，沒命中交總裁 | route.md、[crystal.md](../../spec/team/crystal.md) | 門房命中率（`route.log`） | 兼任 |
| **製造部** mfg | [teams/mfg](teams/mfg/team.json) | `mfg-lead`／lead／gpt-5.5／正式（窗口，拆批次）；`mfg-writer1`／worker／**gpt-6-astra**／正式（09-25 五家真跑：astra 八張一次過、每張 132 萬 token，見[報告](../../notes/2026-09-25-company/market-run-5/README.md)）；`mfg-reviewer`／reviewer／gpt-5.5／正式；忙時 `mfg-lead` 可 spawn worker（臨時工，不用批） | corpus 唯讀（寫手、審查） | `〔給 mfg〕補人物 X`（全套，動索引）／`補人物 X（只寫詞條）`（門房直接開單給寫手） | `lore/characters/X.md`＋證據檔，過驗收（機械 5～6 條）＋審查（judge） | [examples/arknights](../arknights/README.md)、[tasks.md](../../spec/team/tasks.md)、[verify.md](../../spec/team/verify.md) | 一次過率（attempt=1 的 done）、每單 token、每單秒數 | 有 |
| **品管部** qa | [teams/qa](teams/qa/team.json) | `qa-inspector`／worker／deepseek-chat／正式；**評審**＝`eval.sh` 裡一次性的 claude-opus-5 呼叫（臨時工） | corpus 唯讀 | `〔給 qa〕驗貨 X`（門房直接開單） | `qa-reports/X.md`（`結論：合格／不合格`＋抽查 3 列）；批次時 `eval.sh` 分數 | [examples/arknights/eval](../arknights/eval/)、verify.md | 驗貨合格率；eval 機械層全過率、證據列 ok 率 | 有 |
| **研發部** rd | [teams/rd](teams/rd/team.json) | `rd-smith`／worker／gpt-5.5／正式（工具匠） | — | `〔給 rd〕要一支工具…`（沒門房規則，信給窗口） | 工具草稿（人 `aos-team tool approve` 才裝） | [toolsmith.md](../../spec/team/toolsmith.md)、[tools/](../../tools/README.md) | 草稿牢裡測試通過率；被批准數 | 有 |
| HR hr | 併在 hq | 機械：名額由 HR 擋（`up` 把 `company.json` 的上限寫進這家的 `K/hr/policy.json`，`init`／`start`／生成員超了就擋）、`aos-team hr` 薪資表與試用、spawn 生臨時工；決策＝總裁兼、改名冊＝董事 | — | `〔給 hr〕…`（落到總裁） | 名冊改動（人批）、臨時工 | [hr.md](../../spec/team/hr.md)、[spawn.md](../../spec/team/spawn.md)、[score.md](../../spec/team/score.md) | 正式 N/10、cpu N/20、llm cpu N/5 不超（`company.py status` 與 `aos-team hr cap` 同一組數） | 兼任＋機械 |
| 圖書館 lib | [teams/lib](teams/lib/team.json) | `lib-librarian`／librarian／deepseek-chat／正式（只判「像不像舊條目」，其餘郵差機械做） | commons 唯讀 | 各部門成員 `commons_submit` 的投稿（每個成員都自動有 `commons_search`／`commons_submit`） | 這家的 commons 條目（`teams/commons/`：各部門團隊的上一層，全公司共用一份；五家各一份，不互通） | [commons.md](../../spec/team/commons.md)、[examples/commons](../commons/README.md) | 機械審通過率、叫模型判的比例 | 有 |
| 財務部 fin | —（純機械） | 沒有模型員工：帳本 `aos-team cost`＋公司帳戶 | — | — | 每部門／每單 token 與美元；超預算郵差停開新單 | [cost.md](../../spec/team/cost.md)、`lib/aos_team_cost.py` | 帳本覆蓋率、預算用了幾成 | 機械（設 `AOS_COST_HOME` 就記得到） |
| 總務／資安 | — | 機械：`aos up／down`、kernel 池、牆（bwrap）、郵差再驗 | — | — | — | [wall.md](../../spec/team/wall.md) | kernel health | 有 |

## 檔案

| 檔 | 是什麼 |
|---|---|
| [company.json](company.json) | 部門、兼任、上限（新創 10／20／5、擴張頂 100／200／20）、池、前台部門；格式見 [company.md §2](../../spec/team/company.md) |
| `teams/<部門>/team.json`、`routes.json` | 每個部門的名冊與門房規則（樣板：成員名不帶公司前綴，`new --prefix` 才加） |
| `persona/*.md` | 公司層人格，`up` 時接在內建模板人格後面：`_company.md`（每人都有：怎麼寫〔給 部門〕）、`hq-lead.md`（總裁的 SOP）、`mfg-writer1.md`／`mfg-reviewer.md`（抄自 arknights 的專案規矩）… |
| `llm.json` | LiteLLM `localhost:4000` 的模型代號（只走這個端點） |
| [company.py](company.py) | `new／up／down／status／order／mail／answer／relay／hr`（本體 `lib/aos_company.py`） |

成員一律用**內建模板**（`lead`／`worker`／`reviewer`）＋公司人格：門房落穿找的是 `template: lead` 的成員，自訂模板的領隊接不到落穿（arknights 樣板踩到的坑，見報告）。

## 跑一家

```sh
# 專案副本（絕不在本尊上跑；這裡不帶 .git）
mkdir -p ~/tmp/company-run/c1
rsync -a --exclude=.git --exclude=aos-runs ~/tmp/arknights-try/ ~/tmp/company-run/c1/proj/
ln -sfn ~/tmp/arknights-corpus ~/tmp/company-run/c1/arknights-corpus   # proj/corpus/raw 的相對連結要解得開

cd proto5/examples/company
python3 company.py new ~/tmp/company-run/c1 --prefix c1- --project ~/tmp/company-run/c1/proj
export AOS_COST_HOME=~/tmp/company-run/cost          # 可省；設了帳就記得到這家
python3 company.py up     -C ~/tmp/company-run/c1
python3 company.py order  -C ~/tmp/company-run/c1 "補人物 老財"
python3 company.py status -C ~/tmp/company-run/c1     # 正式 7/10、cpu 12/20、llm cpu 5/5＋各部門單子＋總機單
python3 company.py hr cap -C ~/tmp/company-run/c1     # HR 的名額（自動帶這家的 AOS_KERNEL_HOME／AOS_HR_HOME）
python3 company.py mail   -C ~/tmp/company-run/c1     # 董事收件匣
python3 company.py down   -C ~/tmp/company-run/c1
```

看某一個部門細節就用一般的 aos-team：`aos-team mail --target ~/tmp/company-run/c1/teams/mfg`、`task ls --all`、`score`。

**`aos-team` 在哪**：`proto5/cli/aos-team`（不在 PATH 上）。在這個資料夾就是 `python3 ../../cli/aos-team task ls --all --target ~/tmp/company-run/c1/teams/mfg`，或先 `export PATH=$PWD/../../cli:$PATH`。

**換模型**：成員用的模型寫在**實例**的 `teams/<部門>/team.json` 每個成員的 `"model"`（例 `~/tmp/company-run/c1/teams/mfg/team.json` 的 `c1-mfg-writer1`）；`new` 之後、`up` 之前改，`up` 不會蓋回去。`llm.json` 只放「模型代號 → LiteLLM 端點」的對照，不決定誰用哪個。改樣板（這個資料夾的 `teams/*/team.json`）＝以後 `new` 的每一家都換。

**怎麼知道單做完了**：董事收件匣（`mail`）出現**總裁**（`c1-hq-lead`）寄的 DONE／FAILED 才算結案。中途可能短暫看到某個部門寄給 human 的內部回覆（總機每 5 秒一輪，還沒搬走），幾秒後就不見了，不是總機壞了。`status` 的總機單全部 `done` 也是一個訊號。

**成本**：試玩 09-25 全用 deepseek-chat 跑一張「補人物 老財」＝126 次模型呼叫、**451 萬 token**、約 6 分鐘（gpt-5.5 是 34 次、89 萬 token）。開幾家同跑前先估一下帳；市場層的開辦費預設是 2500 萬 token（約 5 張單）。

**直接跑 `aos-team hr cap` 要帶這家的 kernel**：`AOS_KERNEL_HOME=~/tmp/company-run/c1/K AOS_HR_HOME=~/tmp/company-run/c1/K/hr aos-team hr cap`，不帶會說找不到 HR 家（真跑 09-25）。`status` 最後一行會印出這兩個值；`company.py hr cap` 自動帶。

**草稿不在也能下「補人物」**：製造部門房看 `aos-drafts/X/`，不在或是空的，單子就寫「無草稿、從原文起」，總裁的結案信不會說「依草稿」（規則的 `if_missing`，[route.md](../../spec/team/route.md)）。

**「補人物 X」換誰都能開單**：製造部、品管部的 `cmd_ok` 白名單用 `"pattern": true`，`lore/characters/{name}.md` 的 `{name}` 認任何一格檔名（不含 `/`、不是 `..`、不以 `-` 開頭），同一條裡的 `{name}` 要是同一個人（[roster.md](../../spec/team/roster.md)）。09-25 五家真跑前是照人名寫死六列，換第七個人就被郵差 `NotAllowed` 退件。

**帳戶花光了會怎樣**：部門郵差看到帳戶超支，新的開單直接退件（FAILED，信裡寫「財務擋單：超支」），總機把 FAILED 轉回總裁，總裁照 SOP 回董事——董事的單會結案（算失敗），不會永遠卡著（[cost.md](../../spec/team/cost.md) §4）。

**daemon 在哪**：`<公司>/D/`（company.json 的 `daemon`，預設 `D`；董事 09-25：一家一個 daemon＋kernel）。`down` 會把自家的 kernel 與 daemon 一起關，印「總機撤了」和 daemon 停了沒；之後 `status` 印 `kernel stopped（…）`。

## 擴張到 100 人時長什麼樣

上限 `limits_max`：正式 100、cpu 200、llm cpu 25（董事 09-25 14:20：五家滿編剛好 25，原 20 提高）。擴張的規則沿用 HR 部的兩條（積壓 ≥ 3 張、品管分 < 80 才加人），加法都是「名冊加一列」或「多開一支團隊」，不用新機制：

| 部門 | 新創（現在） | 擴張到頂 |
|---|---|---|
| 總裁辦 | 總裁 1（兼業務、HR） | 總裁 1＋幕僚 2（一個專管董事的題目彙整、一個管季度例行單）；業務、HR 各自獨立 |
| 業務部 | 門房規則 | 自己一支團隊：門房＋業務經理 1＋接單員 2～3（一條產品線一個，負責把客戶的話翻成製造部認得的句型）；`crystal` 把常落穿的句型固化成規則 |
| 製造部 | 經理 1、寫手 1、審查 1 | **一條產線一支團隊**（arknights、下一個 narratives…），每支：經理 1、寫手 4～6（其中一半降級成笨模型）、審查 2；總共約 40 人。寫手不夠用 spawn 臨時工補，不佔人頭 |
| 品管部 | 檢驗員 1＋eval 評審（臨時） | 每條產線檢驗員 2、校準員 1（造壞版本測評分器）；評審仍是臨時工；約 10 人 |
| 研發部 | 工具匠 1 | 工具坊 4、流程組 3（門房規則、`done_when` 樣板）、內核組 3；約 10 人 |
| HR | 機械＋總裁兼 | 自己一支團隊 3～4 人：試用（`hr trial`）、薪資表、名額；大半還是程式 |
| 圖書館 | 保留 1 名額 | 館員 2～3（笨模型；只判「像不像舊條目」） |
| 財務部 | 純機械 | 仍是純機械＋會計 1（看帳、寫週報給董事） |
| 其他 | — | 一條產線滿 40 人時拆成兩家公司（走 market 層），不在一家裡無限長 |

cpu 的算法不變：一家一個 kernel，`pools` 開多少顆就是多少（多的工作排隊，不會超）。llm cpu 25 是整台機器的頂，**幾家同跑時要分**（見 market）。

## 開幾家（市場層）

`new` 帶不同前綴就能在同一台機器開好幾家（`c1-hq-lead`…`c5-hq-lead` 不撞名），每家自己一個資料夾、自己的 kernel、自己的上限、自己的 commons（`<公司>/teams/commons/`，**各家不互通**——競爭對手不共用經驗；要共用就在名冊寫 `"commons": {"dir": "~/tmp/company-run/commons"}`，這題留給董事）。

- **五家同跑時每家維持 llm cpu 5 就好**（5×5＝25，剛好是整台機器的頂；董事 09-25 14:20 拍板把總額從 20 提高到 25，不用再降到 4）：`new` 不用帶 `--llm-cpu`。上限可調，市場層開戶時仍會擋總數。
- 經理人（Fable，aos 外）用 [market.py](market.py)：`open`（開戶＋開辦費）→ 每輪 `score`（品質）→ `rank`（品質 0.6、快 0.25、省 0.15 加權）→ `bankrupt`（花光倒閉）→ `grant`（照名次分這一輪的總額，可覆寫）→ 剩兩家 `merge`。
- **這輪沒有成功結案的拿 0**：成功＝品管判合格、總裁寄了結案信（`score` 自己從董事的單與結案信數；「快」就是董事等了幾秒）。這輪一家都沒 `score`，`grant` 拒絕（「本輪無分數」），不會多發一輪；同分的均分。
- **總池**：錢＝董事給的總量 − 各家已花 − 各家手上沒花的配額；名額＝機器上限 − 各家上限。倒閉／裁撤時沒花完的配額與它的名額全部回總池，經理人再撥（`grant`／`slots`）。只是歸零倒閉的，收回的通常只有名額。
- 規則與參數：[spec/team/market.md](../../spec/team/market.md)。

```sh
export AOS_COST_HOME=~/tmp/company-run/cost AOS_MARKET_HOME=~/tmp/company-run
for i in 1 2 3 4 5; do
  python3 company.py new ~/tmp/company-run/c$i --prefix c$i- --project ~/tmp/company-run/c$i/proj
  python3 market.py open c$i ~/tmp/company-run/c$i
done
python3 market.py pool          # 錢還剩多少、名額還剩多少
```

**用假資料走完一輪**（不 `up`、不叫模型；帳本、市場各開一個新資料夾，免得混到真的帳）：

```sh
export AOS_COST_HOME=~/tmp/market-demo/cost AOS_MARKET_HOME=~/tmp/market-demo
for i in 1 2 3; do
  python3 company.py new ~/tmp/market-demo/m$i --prefix m$i-
  python3 market.py open m$i ~/tmp/market-demo/m$i
done
python3 market.py score m1 --quality 85 --seconds 300     # 這一輪的表現（grant 之後要重記）；假資料沒有真的單，
python3 market.py score m2 --quality 70 --seconds 200     #   給 --seconds＝經理人認定這家成功結案一張
python3 market.py score m3 --quality 40 --done 0          # 做壞的：品質、快、省都算 0，撥 0
python3 market.py rank                                    # 品質 0.6、快 0.25、省 0.15（只在成功的幾家之間比）
python3 market.py bankrupt --dry-run                      # 先看有沒有花光的（有就先 bankrupt，再 grant）
python3 market.py grant --dry-run && python3 market.py grant
python3 market.py close m3 --dry-run && python3 market.py close m3    # 經理人裁撤一家：剩的收回總池
python3 market.py merge --dry-run && python3 market.py merge          # 剩兩家：排名高的併掉低的
python3 market.py ls
```

每個子命令都有 `--help`；中途崩了（或 `StopFailed`）就重跑同一個指令，會接著做、不會重撥（[market.md §5a](../../spec/team/market.md#5a-鎖與崩了怎麼辦astra-09-25)）。
