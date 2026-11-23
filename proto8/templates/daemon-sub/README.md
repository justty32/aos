# daemon-sub：子 daemon 定義（掛在別的 daemon 底下，不帶時鐘，只帶清道夫）

← [templates](../README.md)｜根用的是 [daemon-root](../daemon-root/README.md)

給「在一台已經在跑的 daemon 底下再開一台 daemon」的用法：它是上層表上的一列，起它＝起一台子 daemon，表上只有 `_sweeper`（每 10 分鐘清這台自己的 stderr 封存、寫 `sweeper_report.json`）；agent 不寫進 `daemon.json`，由 `aos-agent ctl add` 經 `procs_requests` 掛上、記在它自己 stack 的表裡。要起的是一整棵樹最上面那台（沒有上層）就用 `daemon-root`，不是這份。

除了 `daemon.json` 少了 `_clock` 那列、`.env` 只留 `AOS_HOME`、`_entry` 與 `daemon.json` 的說明句、這份 README，其餘跟 `daemon-root` 一樣（`tests/test_daemon_sub.py` 比對）。

| 檔 | 做什麼 |
|---|---|
| `_entry` | `aos-daemon --enable-logs daemon.json`（狀態變化印到 stdout；掛在上層底下時子項的 stdout 接 `/dev/null`，所以看不到，要看狀態用 `ls`；跟 `daemon-root` 同一行，只有說明句不同） |
| `daemon.json` | `procs_requests` 信箱＋`_sweeper` 一列，沒有鐘列、沒有身體 |
| `.env` | 只有最後一行 `AOS_HOME=${AOS_HOME}`＝必填檢查（上層傳下來的有值就過）；`AOS_CLOCK`、`AOS_LLM_KERNEL` 故意不寫，由上層傳下來 |

## 為什麼不帶鐘列、`.env` 只留 `AOS_HOME`

- **鐘只在根**：根的 `_clock` 每秒寫根 stack 裡的 `clock`，根的 `.env` 把 `AOS_CLOCK` 指過去；子 daemon 是根的子項，照繼承拿到同一個 `AOS_CLOCK`，再傳給自己底下每一隻，整棵樹聽同一個鐘。子 daemon 自己再帶 `_clock`，只會多寫一份自己 stack 裡的 `clock`，底下的 agent 照樣聽根的（上層傳下來的 `AOS_CLOCK` 贏過 `.env`），那份沒人讀。
- **`AOS_LLM_KERNEL` 也從上層來**：`daemon-root` 那行 `AOS_LLM_KERNEL=${AOS_WS}/../llms/stacks/llm` 是給根用的擺法；放在子 daemon 裡，上層有傳就被蓋掉、沒傳就指到一個多半不存在的地方，留著只會讓人誤會。想讓這台底下用別的 llm kernel：上層沒傳時在這份 `.env` 加一行就好；上層有傳，`.env` 蓋不過它。
- 有特殊需求（這台底下要聽另一個鐘）才自己加 `_clock` 列與 `AOS_CLOCK`（[CONVENTION](../../docs/CONVENTION.md)「時鐘」那條）。

## 用法

下面的 `<上層 stack>`、`<名>`、`<子定義>`、`<ws>` **只是佔位**：定義放哪、叫什麼名字都可以，範本與程式都不假設。

```sh
cp -r $AOS_HOME/templates/daemon-sub <子定義>              # 例 ~/aos-home/guanyu
aos-daemon-ctl -d <上層 stack> add --auto-restart -n <名> -w <ws> <子定義>
aos-daemon-ctl -d <上層 stack> ls                          # <名> 是 running
aos-daemon-ctl -d <上層 stack>/procs/<名> ls               # 只有 _sweeper
```

- **上層 stack**：要掛在哪台 daemon 底下，就給那台的 stack（根的就是起根時 `aos-exec --stack` 給的那個）。
- **stack**：不給 `-s` 就是預設的 `<上層 stack>/procs/<名>/`，跟上層的 stack 一起搬、一起睡醒，通常照預設。要放別處才給 `-s <路徑>`。
- **ws**：這台子 daemon 的工作區，一般是它負責的那個專案資料夾；之後掛在它底下的 agent 不給 `-w` 就用這個。不給 `-w` 就跟上層 daemon 同一個。
- **路徑寫法**：絕對路徑原樣記在表上；相對路徑從下指令的地方算、記成相對上層 stack 的，整棵搬走照樣對。
- `--auto-restart`：子 daemon 是常駐的，退了上層就重起它。

底下掛 agent（`-d` 給子 daemon 的 stack，不是上層的）：

```sh
aos-agent -d <上層 stack>/procs/<名> ctl add --auto-restart -n <agent 名> -w <agent 的 ws> $AOS_HOME/templates/eca-claude
aos-daemon-ctl -d <上層 stack>/procs/<名> ls               # _sweeper、<agent 名> 都是 running
```

子項的 stack 在 `<上層 stack>/procs/<名>/procs/<agent 名>/`。

- **停**：`aos-daemon-ctl -d <上層 stack> stop <名>`（上層那列留 `stopped`、不會被 `--auto-restart` 拉起來；底下子項全睡下、記在子 daemon 的表上），回來用 `aos-daemon-ctl -d <上層 stack> start <名>`，睡下的子項自己醒。不要對子 daemon 自己下 `shutdown`：它退了，`--auto-restart` 會馬上再起它。整棵收掉照舊是對根 `shutdown`，子 daemon 跟著睡下、下次起根一起醒。
- **拿掉**：`aos-daemon-ctl -d <上層 stack> rm <名>`（stack 留著，之後 `add` 同一個名字接著用）。
- **起之前**：上層要有 `AOS_HOME`（這份 `.env` 最後一行檢查它）；`AOS_CLOCK`、`AOS_LLM_KERNEL` 看上層有沒有給，子 daemon 只是原樣往下傳。
