← [入口](README.md)｜件 1：agent 給自己改 tool｜下一份 [02-endpoint-packs](02-endpoint-packs.md)

# 件 1：agent 給自己改 tool（fable 照原則定，可翻案）

使用者原文（11-05 午，逐字）：「讓agent給自己改tool」。前情：11-05 早起 `aos-agent tools add／rm` 改的是**這一隻的覆蓋層** `<stack>/tools.json`、只存差異、定義不動（[aos-agent docs/03](../../../../cmd/aos-agent/docs/03-tools覆蓋層.md#tools-覆蓋層)）；agent-fsm 的 brain／act 每格重讀「定義疊覆蓋層」。

## 已定（照原則推得出）

- **改的對象＝自己的覆蓋層，定義永遠不動**（P-15 跑起來時不寫定義、portable-flow「stack 不存定義副本」）。所以「agent 給自己改 tool」＝腦叫一個工具，那個工具跑 `aos-agent tools add／rm --target <自己>`。同一份定義掛的別隻不受影響；`aos-agent tools reset` 一刀回到定義。
- **腦怎麼知道工具變了**：不用通知——brain 每格現疊 `aos-tools --overlay ls`，下一題就看到新清單（已是現況）。工具的 stdout 回給腦一句 `added X; available from your next turn`（P-41 結果回腦）。
- **改壞了怎麼救**：`add` 經 aos-tools 檢查（`PathMissing`、`ToolDefMissing`、`ToolExists`）→ 寫不進壞東西，錯一行回給腦（P-41、lib 契約規則 3：參數錯也是錯、照樣退 1）。之後工具檔被人刪掉＝整隻停 `stopped`＋`reason`（11-05 edge-agent 已裁），人 `aos-agent tools reset` 再 `ctl start`——現有救法、不加新的。
- **不加白名單**：腦要加 `lib/base/bash` 給自己就加（10-15「濫用：先信任」；真要擋用 Linux 權限或 sandbox，C-64）。
- **工具的參數**（lib 契約規則 1、4）：stdin `{"op": "add"|"rm"|"ls", "name"?, "path"?}`；`path` 從 `$AOS_WS` 算、解開 `..` 後要還在工作區裡（`PathBad`），或 `lib/` 底下的絕對路徑（給腦「照抄庫的工具」用）。`ls` 印疊好的清單一行 JSON。

## 代定（照推薦定，可翻案）

1. **自己是誰＝問 daemon 的表**：新子命令 **`aos-agent ctl who [--stack S] [--json]`**——拿 `S`（預設 `$AOS_STACK`）在 `aos-daemon-ctl ls --json` 的列裡找「`stack` 是 S 本身或 S 的上層」那列，印名字（`--json` 印 `{"name","stack","ws","def"}`）。沒找到＝`InstanceMissing`；沒 daemon＝`DaemonMissing`。工具的小格是 `<agent stack>/tools/self_tools/`（P-17），所以用上層比對就找到那隻。這是「透過其他機制看上層」（C-52 加嚴允許的那種：機制＝daemon 表），不是工具自己 `../..` 偷爬。
2. **工具放 `lib/agent/self_tools/`**（高層：懂 aos、懂 agent），三件套 `_entry`（python3 純標準庫）、`_tooldef.json`、`_metainfo.json`（`side_effect: true`、`idempotent: false`、`resource: "cpu"`）。`_entry`＝`ctl who` → `aos-agent tools --target <名> add [--override] <name> <abs path>`／`rm`／`ls`；aos-agent 的 stderr 原樣往上、它退非 0 時把那行印到 stdout 給腦（lib 規則 3）。
3. **工具名 `self_tools`**（腦讀起來就是「我自己的工具」；C-54 主題在前：主題是 self）。`op` 用 aos-agent 同一套動詞 add／rm／ls，不造新詞。
4. **沒掛在 daemon 下跑的 agent（`aos-exec body.json`）不支援**：`ctl who` 報 `DaemonMissing`、工具把那行回給腦。理由：沒有表就沒有「我是誰」；要支援就得猜路徑（違 N-63 ②）。
5. **範本 agent-fsm 不內建**（留題 5）：demo 用人殼 `aos-agent tools add self_tools <repo>/proto8/lib/agent/self_tools` 當場塞進那隻，再讓腦自己加第二個。

## 衝突（哪條、在哪、各自後果）

- **C-52 巢狀切乾淨「被叫的只看到自己的 stack、不知道上面有誰」（P-17）**：`self_tools` 的本質就是對呼叫者動手，一定要知道「上面是誰」。(a) 推薦：靠 `ctl who` 查 daemon 表——走正式機制、工具程式裡沒有 `..`，付的代價是只在 daemon 下能用。(b) 工具用 `$AOS_STACK/../..` 推 agent 的 stack——哪都能跑，但把 P-17 的佈局寫死進工具、就是 10-15 深夜說的「偷看一層」。(c) act 格把 agent 名或 stack 傳給工具——aos 只訂六個環境變數（C-69），要傳只能塞進 arguments，等於腦得知道自己的路徑。選 (a)。
- **C-46「bob 呼叫時不變、是可重複使用的函數」**：這條沒撞——改的是 stack 裡的差異，定義（函數本體）不變；但同一隻跑久了行為會跟定義漂移，`aos-agent tools ls` 的 stderr 已會說「定義疊覆蓋層」，`ctl state` 建議多印一行 `tools overlay: N added, M removed`（代定、順手）。
