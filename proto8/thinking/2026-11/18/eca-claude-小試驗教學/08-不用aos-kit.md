這份教你不叫 `aos-kit`，只用 cp、編輯檔案和別的 aos 指令，做出 `aos-kit` 做的事（試驗 08，11-18 在公司 WSL 實跑過）。

← [目錄](README.md)

# 試驗 08：不用 aos-kit 達成 aos-kit 的功能

使用者原話：「8.不使用aos-kit來達成aos-kit的功能」

## 結論

- **`aos-kit` 只動兩個檔**：定義夾裡的 `system.txt`、`tools.json`。被換掉的舊檔先另存一份 `檔名.before-kit`。它不碰 `llm.json`、`hooks.json`，不叫別的 aos 指令，也不重起 agent。
- 所以手動做就是兩行 `cp`（外加兩行備份）。實測手動做和 `aos-kit add` 做出來的定義夾 `diff -r` 一模一樣，兩隻 agent 送給腦的 system 文字、26 支工具也完全一樣。
- **現在出廠的 kit 用 `aos-kit` 裝反而裝不起來**：`templates/kits/kits.json` 還沒有 `make` 區塊，所以 `make`、`check`、`add` 都報 `MakeMissing`，只有 `ls` 能用。要拿 `aos-kit` 比對，得借測試用的那份 kits 夾（下面第 1 步）。手動 cp 不受這個限制。
- **只支援 agent-fsm**，不支援 eca-claude（細節見最後一節）。
- **不用重起**：agent-fsm 每次問腦前都會重讀 system 和 tools，換了檔，下一題就生效（pid 不變）。

## aos-kit 四個子指令各做哪幾件事

| 子指令 | 實際做的事 | 手動對應 |
|---|---|---|
| `ls` | 讀 `kits.json` 的 `kits`，一個 kit 印一行 | `aos-json ls $AOS_HOME/templates/kits/kits.json#/kits` |
| `make KIT` | 照 `make.layers` 的順序接起來：general → 你的 site 檔（有給才接）→ role。把 `<NAME>` 換掉，每層之間空一行 | `sed` 換字，加 `cat`／`echo` 接起來（第 5 步） |
| `check KIT` | 用預設值接一次，跟出廠的 `system.txt` 逐字比；再看有沒有留下 `<NAME>`、有沒有超過 3000 字、tools 是不是合法 JSON | `cmp`、`grep`、`wc -m`、`python3 -m json.tool`（第 6 步） |
| `add KIT DEF` | 1. DEF 要有 `interfaces.json`；2. 現有的兩個檔要跟 `$AOS_HOME/templates/agent-fsm` 那份一樣，不一樣就拒絕（`--force` 例外）；3. 兩個都檢查完才開始寫；4. 舊檔另存 `.before-kit`（名字被占了就用 `.before-kit.2`、`.3`）；5. 寫入 `system.txt`（make 的結果）和 `tools.json`（從 kit 抄來） | 第 2～4 步 |
| （移除） | **沒有這個子指令** | 把 `.before-kit` 搬回去（第 7 步） |

## 手動步驟

先做：`cd ~/aos-home && source env.sh`（樹是從 `templates/start-api` 抄出來的，`agents/ann` 用假腦）。

**1. 先準備兩份一樣的乾淨定義（只是為了比對，自己用的時候可以跳過）**

```sh
cp -r agents/ann agents/kitted && cp -r agents/ann agents/hand
aos-kit --kits $AOS_HOME/py/tests/apps/kit/fixtures/kits add gather agents/kitted
```

會看到：`saved agents/kitted/system.txt.before-kit (the old system.txt)` … `wrote agents/kitted/tools.json (1354 bytes)`，最後一行是 `not touched: hooks.json, llm.json …`。
卡點：`--kits` 沒給的話，會報 `aos-kit: error: MakeMissing kit gather has no "make" block in kits.json`。

**2. 確認現在的檔還是出廠的（就是 aos-kit 的「沒被改過」那道檢查）**

```sh
D=agents/hand; cmp $D/system.txt $AOS_HOME/templates/agent-fsm/system.txt && cmp $D/tools.json $AOS_HOME/templates/agent-fsm/tools.json && echo STOCK
```

會看到：`STOCK`。如果 cmp 印出 `differ`，表示有人改過，先想清楚要不要蓋掉。這就是 aos-kit 報 `FileChanged`、要你加 `--force` 的情況。

**3. 備份（順序要對：先備份，再蓋）**

```sh
cp $D/system.txt $D/system.txt.before-kit && cp $D/tools.json $D/tools.json.before-kit
```

卡點：`.before-kit` 已經存在的話不要直接蓋，改用 `.before-kit.2`。aos-kit 從來不覆蓋備份。

**4. 抄 kit 的兩個檔進來**

```sh
cp $AOS_HOME/templates/kits/gather/system.txt $D/system.txt && cp $AOS_HOME/templates/kits/gather/tools.json $D/tools.json
diff -r agents/kitted agents/hand && echo IDENTICAL
```

會看到：`IDENTICAL`。
卡點：review 這個 kit 的工具是借 gather 的。也就是 system 從 `kits/review/system.txt` 拿、tools 從 `kits/gather/tools.json` 拿（`kits.json` 裡 review 的 `tools` 寫的就是這個）。權限位不用管：兩邊都是 `-rw-r--r--`，`_entry` 是 JSON，不用 x 位元。

**5. 要自己的 site 層或換掉預留字的時候（make 的手動版）**

跟 `aos-kit make gather --site site.txt --set KNOWLEDGE=$AOS_HOME/knowledge --set BOARD_LINE= --set OWN_BOARD=` 結果一樣的寫法：

```sh
G=$AOS_HOME/templates/kits
{ sed -e "s#<KNOWLEDGE>#$AOS_HOME/knowledge#g" -e "/<BOARD>/d" -e "/<OWN_BOARD>/d" $G/general.A.txt; echo; cat site.txt; echo; cat $G/roles/gather.txt; } > $D/system.txt
```

會看到：跟 `aos-kit make … -o made.txt` 做出來的檔 `cmp` 不出差別（1948 字）。
卡點：
- `site.txt` 最後只能有**一個**換行。aos-kit 會把每層尾巴多的空行剪掉，手動 `cat` 不會剪。
- 不加 `--set` 時，aos-kit 用的不是 `<KNOWLEDGE>` 換字，而是 kits.json 預設值裡的**整行**（例如第 2 行會變成 `2. Read the aos knowledge base: …`）。想要出廠那份，直接 cp `gather/system.txt` 最省事。
- 空值的意思是**整行拿掉**，不是留一行空白。

**6. 自己檢查（check 的手動版）**

```sh
wc -m < $G/gather/system.txt; grep -c "<[A-Z][A-Z0-9_]*>" $G/gather/system.txt; python3 -m json.tool $G/gather/tools.json >/dev/null && echo JSON-OK
aos-tools --file $D/tools.json ls | wc -l
```

會看到：`2156`（要 ≤ 3000）、`0`（沒有留下預留字）、`JSON-OK`、`26`（出廠的 agent-fsm 是 40 支）。

**7. 移除 kit（aos-kit 沒有這個功能）**

```sh
mv $D/system.txt.before-kit $D/system.txt && mv $D/tools.json.before-kit $D/tools.json
```

會看到：再 `cmp` 跟出廠的比，沒有差別；agent 下一題送的工具回到 40 支。
卡點：裝過好幾次的話，**最早那份是 `.before-kit`**（沒有數字的那份），`.2`、`.3` 是後面才存的。

**8. 讓 agent 用上新定義**

```sh
aos-agent -d .stack ctl add --auto-restart -w . agents/hand
aos-agent -d .stack --target hand say hello && aos-agent -d .stack --target hand listen --timeout-s 20
```

會看到：`FAKE ANSWER to: hello (tool said: …)`。
已經在跑的 agent，換完檔直接問下一題就生效，**不用重起，也不用 `ctl set-def`**。實測 pid 沒換，system 換成新的，工具 40 → 26。
卡點：**這隻 agent 自己有一份 system 的話，定義換了它也看不到。** 用過 `aos-agent system set` 的 agent，stack 裡會有 `system.txt`，整份蓋過定義那份。實測：裝了 kit 之後，腦收到的還是那份自訂文字。用 `aos-agent -t hand system reset -y` 刪掉才回到定義那份。tools 的自有那份只記差異，會疊在新定義上（`tools rm math` 之後是 25 支）。不想留差異就 `tools reset -y`。

**怎麼確認兩隻真的一樣**：看 `.stack/procs/<名>/think/request.json`，這是送給腦的那份。實測 kitted 跟 hand 的 system 文字 md5 一樣、工具 26 支的 md5 一樣，兩隻假腦的回答也一樣。

## 發現的問題（沒修程式）

1. **出廠的 kit 不能用 aos-kit 裝**：`templates/kits/kits.json` 沒有 `make` 區塊，所以 `make`、`check`、`add` 一律 `MakeMissing`。程式的 README「Known limits」有寫這點，但錯誤訊息沒告訴你該怎麼辦。只有 `tests/fixtures/kits` 那份可以用。
2. **`add` 最後一行叫人去「run agent_def check」**：`agent_def` 是給 agent 用的工具，人沒有對應的指令可以打（`bin/` 裡沒有）。
3. **eca-claude 的情況**：說明寫只給 agent-fsm 用，但程式只檢查有沒有 `interfaces.json`，沒檢查身體是哪一種。在 eca-claude 的定義上，預設會報 `FileChanged … is not the stock agent-fsm tools.json (someone edited it)`。這句話誤導人，其實沒人改過，它本來就不是 agent-fsm。加 `--force` 照樣會寫進去：多出一個 `system.txt`（eca 會附加在 claude 的 system 後面），`tools.json` 被換成 gather 那份（eca 原本的 events、def、jsonx 包都不見了，換來跟 claude 內建工具重複的 look、change）。但 `cli.json` 裡 claude 自己的 `Bash` 等工具還開著，**kit 說的「沒有 shell」在 eca 上不成立**。這次只看了檔案，沒有用真模型跑。
4. **`add` 不知道 agent 自己那份 system 存不存在**：裝完不會提醒「這隻有自訂 system，看不到新的」（第 8 步的卡點）。
5. **小雜訊**：`aos-agent tools ls` 每次都會在 stderr 印一行 `using the definition's … (this agent has no file of its own)`。
6. 從一個 kit 換到另一個（gather 換 review）一定要 `--force`，因為已經不是出廠檔了。這是設計如此，但說明沒有講。

## 沒驗的

- eca-claude 加了 kit 之後用真模型跑（只看了檔案的變化）。
- `--site` 搭配 `add`（只驗了 `make`，`add` 用的是同一段接法）。
