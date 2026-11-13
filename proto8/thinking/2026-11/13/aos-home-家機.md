# 家機也住 `~/aos-home`（11-13 晚，線家）：從零照十七步搭好根＋領班＋opus `eca_main`＋工作區是 `~/repo/aos` 的 opus `repo-aos`，真腦、互寄信、停起、存檔都過，驗完樹停著

← [11-13 日索引](README.md)｜搭法十七步：[ops-notes-to-aos § 從零搭一棵小樹](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)｜公司機那次：[aos-home](aos-home.md)｜`repo-aos` 為什麼存在：[main-session-in-aos 第 2 題](main-session-in-aos.md#第-2-題家機的主-session-要不要也改成樹裡的一隻)

## 使用者原文（11-13 晚，家機，選項框）

- 「今天的優先目標是幫我架起aos」
- 住哪：「~/aos-home 從零搭」（`~/code/playground` 那棵舊試驗樹原樣留著）
- repo：「直接放~/repoaos」「~/repo/aos」
- 陣容：「eca_main ＋ repo-aos」
- 舊 MCP 那行（`~/.claude.json` 的 aos 外掛）：「搭好就拿掉」
- 舊位置 `~/repo/simple_tools/aos`：「不用刪」

## 結論

- **家機 `~/aos-home` 搭好、能用，現在停著**（main `42a5e704c`；起樹留給使用者自己下）。
- 陣容：根（`_clock`、`_sweeper`、`foreman`）＋領班（`_sweeper`）＋兩隻 eca-claude：
  - `eca_main`：定義 `~/aos-home/agents/eca_main`、opus、`print_flags []`（不設花費上限）、`system.txt` 指 `../knowledge`（照公司機那棵的寫法）、工作區 `~/aos-home/ws`。
  - `repo-aos`：定義 `~/aos-home/agents/repo-aos`（自己一份，不跟別隻共用）、opus、`print_flags []`、`--tools default`、工作區 `~/repo/aos`（`ctl add -w ~/repo/aos --auto-restart`）、stack `~/aos-home/ws/.stack/procs/repo-aos`、`system.txt` 指 `/home/lorkhan/aos-home/knowledge`（工作區不在 `ws/`，相對路徑算不到）。
  - 沒建問腦總機（`.env` 只寫時鐘那行；公司機同）。
- 驗收（20:14～20:18）：
  - 起樹三列 running，根 daemon 的 cwd 是 `~/aos-home/root`、`AOS_STACK=~/aos-home/.stack/`；兩隻 `ctl add` 後都 running。
  - aos 工具各 **34 支**（範本八包含 jsonx）；hooks 各兩格 `mail_notify`、`timer`。
  - `eca_main`（`aos-agent chat` 管線送一句）：`index_view` 看 `../knowledge/aos` 答 **20 項**；Bash 回 `AOS_STACK=…/procs/eca_main/`、`AOS_HOME=~/aos-home`、`AOS_WS=~/aos-home/ws`。約 6 秒。
  - `repo-aos`（同上）：Bash `pwd`＝`/home/lorkhan/repo/aos`、`AOS_STACK=…/procs/repo-aos/`、`AOS_HOME=~/aos-home`；讀得到工作區 `AGENTS.md` 第一行（`# aos — AI agent 專案備忘`）；用 `mailbox_send` 寄一封給 `eca_main` 成功。約 7 秒。
  - 互寄信：信落在 `eca_main` 的 `mailbox/new/`，一分鐘內 `mail_notify` 往它的 queue 放一則 `[aos] new_mail: 1 new letter from repo-aos…`，它讀了、判斷只是 ping、沒回。
  - `repo-aos` 在 `~/repo/aos` 跑完，`git status` 仍乾淨。
  - 停樹 `3 procs asleep`，沒有 cwd 在 `~/aos-home` 底下的行程、沒有 `aos-*` 行程殘留（Claude Code 自己掛的舊 `aos-mcp` 不算、沒動）；再起一次兩隻自己醒、history 都在（4 行、2 行），再停。
  - 存檔 `~/aos-saves/aos-home-1113-home`（5.6M，停樹後 `cp -a`）。
- 使用者 `.zshrc` 新寫法（第 93 行 `[[ -z $AOS_STACK && -f ~/aos-home/env.sh ]] && source ~/aos-home/env.sh`）三項實測都對：
  - (a) `env -i HOME PATH zsh -ic` 拿到 `AOS_HOME=/home/lorkhan/aos-home`，`AOS_*` 只有它；
  - (b) 帶 `AOS_STACK=x AOS_WS=y` 開，兩個都沒被洗掉（這時 `AOS_HOME` 是空的，因為整份 env.sh 都跳過；樹裡的 agent 本來就帶 `AOS_HOME`，不受影響）；
  - (c) 樹裡兩隻 claude 身的 Bash 工具裡 `AOS_STACK`／`AOS_HOME` 都在、指自己那格（見上）。
  - 順帶：`env -i … zsh -ic` 會印兩行 `can't change option: zle`（非終端機開互動 zsh 的正常雜訊，不是 `.zshrc` 的錯）。

## 十七步跟 main 現況對不上的地方（已改進 ops-notes-to-aos）

- ⑩、⑫ 工具支數 26 → **34**（範本 11-13 加了 jsonx 包）。
- ⑮ 補一句：工作區不在 `ws/` 的那隻（像 `repo-aos`）`ctl add` 加 `-w`、`system.txt` 的 knowledge 路徑改絕對路徑。
- 其他步照抄就過；`aos-agent tools … ls` 會多印一行 stderr warning「using the definition's …/tools.json」，`wc -l` 不受影響。

## 沒驗

- `aos-agent open`（畫面）：從程式叫沒有終端機。而且家機 `~/.claude.json` 對 `~/aos-home/ws` 與 `~/repo/aos` **都還沒按過信任**（唯讀查 `hasTrustDialogAccepted`：兩個路徑都沒有那一項）——chat 不受影響（已驗），開畫面前要照十七步 ⑧ 在這兩個資料夾各開一次 claude 按信任。
- 子 agent（Agent 工具）實叫、外部 MCP（⑰）、讀檔（從存檔換回來）。
- 兩句話花多少錢：沒查。

## 代定

- `repo-aos` 的定義放 `~/aos-home/agents/repo-aos`、自己一份（公司機是 `ws/defs/agent` 跟 `me-agent` 共用；家機沒有別隻要共用）。
- `repo-aos` 的 `--tools` 寫 `default`（CLI 自己的工具全開），照公司機那隻的實況，不照範本的八支清單；其他旗標照範本（`dontAsk`、`--allowedTools Write,Edit,Bash`、`--strict-mcp-config`、`tools_sub`）。
- `repo-aos` 用 `--auto-restart` 掛（公司機那列是 `auto_restart: true`）；`eca_main` 照十七步不加。
- `repo-aos` 的 `loop.json` 照範本 `--on-busy yield`（公司機那份定義是 `answer`；畫面開著時信走收件口，這個開關只管貼字那條路）。
- `repo-aos` 的 `system.txt` 用絕對路徑 `/home/lorkhan/aos-home/knowledge`（樹整個搬家要改這一行）。
- 不抄 `kernel/`（十七步只抄四夾；沒有問腦總機用不到）。
- 測試時起樹的殼另外清掉了 `CLAUDE*` 全部變數（見下一節），使用者自己開的終端機沒有這些，照十七步 `source env.sh` 就好。

## 要注意的

- **`env.sh` 只清三個 Claude Code 變數**（`CLAUDECODE`、`CLAUDE_CODE_ENTRYPOINT`、`CLAUDE_CODE_SSE_PORT`）。從 Claude Code 的 shell 裡起樹（例如 agent 代起），還會帶著 `CLAUDE_CODE_SESSION_ID`、`CLAUDE_CODE_MESSAGING_SOCKET`、`CLAUDE_CODE_CHILD_SESSION` 等，樹裡的 claude 會繼承；有沒有實際影響沒驗（這次起樹前全清掉了）。
- 這個 Claude Code session（與它掛的舊 `aos-mcp`）是舊 `.zshrc` 時開的，環境裡 `AOS_HOME` 還是 `~/repo/simple_tools/aos/proto8`；新開的終端機才是 `~/aos-home`。
