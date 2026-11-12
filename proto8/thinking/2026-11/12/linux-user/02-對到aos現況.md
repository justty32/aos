# linux user 初步調查之二：對到 aos 現況——aos 怎麼認「誰」、哪裡已經用到 linux user、哪裡完全沒有（11-12 晚查條文與程式說明）

← [linux-user](../linux-user.md)｜上一份 [01-linux這邊的事實](01-linux這邊的事實.md)｜下一份 [03-各念頭的讀法與後果](03-各念頭的讀法與後果.md)

## 逐項

| 事情 | 現在 | 跟 linux user 的對應 |
|---|---|---|
| aos 怎麼認一隻 agent | 靠名字（daemon 表上的一列）與它的 stack 路徑；[no-pid](../../05/no-pid/README.md) 之後不靠 pid | **沒有對應**：不看 uid |
| 「我是哪隻」怎麼認 | 工具拿自己的 `AOS_STACK` 去 daemon 表上對（`aos-agent ctl who`）；對不到＝`DaemonMissing` | 沒有對應 |
| 人的信箱 | `~/.aos/stack/mailbox`；順序是 `-s` ＞ `$AOS_LINUX_USER_STACK` ＞ `~/.aos/stack`（[aos-mailbox](../../../../cmd/aos-mailbox/README.md)、[P-48](../../../../docs/CONVENTION/02-題目stack停錯腦/10-P-48.md)） | **已經是**：路徑在家目錄，天然一個 linux user 一個；環境變數的名字就叫「linux user 的 stack」 |
| 信上的寄件人 | 信封 `sender`＝寄件人 stack 的絕對路徑、`reply_to`＝寄件人信箱路徑；內文 `from` 沒給＝`$USER` | `from` 的預設值**已經是** linux user 的名字；但那只是一個字串，誰都能填別的 |
| 一個 linux user 有幾個「人的 stack」 | 預設一個（`~/.aos/stack`），用 `-s` 或環境變數可以指到任何地方 | 一個 user 一個只是預設、不是規定 |
| root daemon 以誰的身分跑 | 誰起它就是誰；家機、公司機都是那個登入的帳號 | 「掛在一個 linux user 底下」現在就成立 |
| 一棵樹底下的 agent | 全部同一個 uid（繼承） | agent 之間、agent 與人之間，**在 linux 眼中沒有界線**：同一個號碼，誰都能寫誰的檔、殺誰的行程 |
| eca 的 claude／codex | 樹裡起的 CLI，同一個 uid；讀的是這個 linux user 家目錄下的登入檔（`~/.claude`、`~/.codex`） | 同一個 linux user；它們自己的「帳號」是 Anthropic／OpenAI 那邊的，另一回事（見下） |
| 一個 user 有幾棵樹 | 不限。家機現在：試驗場一棵（停著）、測試留下的幾棵（活著，在 `/tmp`） | 沒有「這個 user 的那一棵」這種東西 |
| daemon 替 proc 換帳號 | **機制已寫好**：daemon 表上 proc 的 `limits.user`＝帳號名，daemon 在起它時換過去；daemon 不是 root 就報 `LimitBad … switching users needs the daemon to run as root`（[aos-daemon 份額](../../../../impls/aos-daemon/docs/09-份額.md)） | 這就是「root user 的 root daemon」能做而別人不能做的那件事；有沒有在真 root 下跑過，這次沒查到紀錄 |
| 沙箱的另一個帳號 `aos-run` | 腳本寫好（[aos-sandbox](../../../../cmd/aos-sandbox/README.md) 的 `root/setup.sh`：建不能登入的系統帳號、開 `/srv/aos-run`、sudoers 只准換成它）；**家機沒跑過**：帳號不存在、`/srv/aos-run` 不在、`s6-setuidgid` 不在 PATH；等使用者用 root 親手跑（wait-user 02） | 目前唯一一條「兩個 linux user」的線，還沒通 |
| 跨帳號寄信 | 只做了問腦信箱那一種：`setup.sh --mailbox`＝信箱擁有者是我、群組是 `aos-run`、權限 2770（同群組可寫、其他人進不來）＋預設 ACL（不管誰建的信兩邊都讀得到）；信箱要放在家目錄以外 | agent 之間的 mailbox 沒有跨帳號版；人的信箱在 700 的家目錄裡，別的帳號寄不進來 |
| 主 session（Claude Code） | 不在任何 daemon 表上，信箱工具報 `DaemonMissing`；只能用人的指令 `aos-mailbox`，用的就是人的信箱（[wf-to-aos 02](../wf-to-aos/02-寄信給人與主session.md)） | 它實際上是「以這個 linux user 的身分做事的一個行程」，不是 aos 的一隻 agent |

## 「帳號」有好幾種，別混

| 哪一種 | 例子 | 誰在管 |
|---|---|---|
| linux 帳號（本題講的） | 家機 uid 1000；沙箱的 `aos-run` | 這台機器的 linux |
| AI 服務的帳號 | Claude 主帳號與 `CLAUDE_CONFIG_DIR=~/.claude-alt` 那個；公司 WSL 的 claude 是公司帳號 | Anthropic／OpenAI；決定的是額度 |
| aos 的名字 | daemon 表上的 `eca_bob`、信上的 `from` | aos 自己 |

家機現在是**一個 linux 帳號底下有兩個 Claude 帳號**（換一個設定資料夾就換一個）；這兩個對 linux 來說完全是同一個人。

## 使用者以前講過的（跟這題直接相關）

- 11-05 晚（[no-pid](../../05/no-pid/README.md)）：「關於root daemon，我覺得不用限制他一定要怎樣怎樣，他就是一個普通daemon，只是說因爲他頭上沒daemon了，所以使用者要保証他能正常運行。硬要說的話，以後搞不好會是弄一個linux user，然後這個linux user有一個root daemon，掛在沙盒下，並且可以透過一些手段進行使用者切換(可能搭配一隻有root權限的小程式)。大概是這樣。但也可以就只是一個普通的linux user proc，壞了就壞了。」接著：「喔不是，應該說一個agent一個賬號。」——定成遠期、沒排（[C-64](../../../../docs/CONCEPTS/01-設計理念/05-布局成長與檔案權限.md) 有註）。
- 10-24（沙箱）：「只要我們預先設定好使用者，設定好權限，一切都好說」。
- 11-10（mailbox）：「使用者這邊需要把自己當agent，自己指定自己的stack」。
- 11-12（[wf-to-aos](../wf-to-aos.md) D4）：「把人類這個linux user作爲agent，寄信過去就是了。」
- 名詞表的 daemon 那列：「Linux 那邊的事（許可權、身份、記憶體、硬碟、行程）全在這層」。
