# 疑難排解
<!-- verified: 11-14 v2, section 1 (shutdown both, cd ~, /proc loop prints nothing) and the restart line were run literally -->

先停樹、確認沒有殘留；其他問題都是「症狀、原因、一行解法」。

<!-- source: 以上三種表現依 templates/agent-fsm/README.md 整理，未重現；ref/get-started.sh step 7; 03-計劃.md 4.1; 08-批0實測.md #3,#13; proto8/templates/daemon-root/README.md、.env; proto8/templates/agent-fsm/README.md; proto8/impls/cmake/settings.cmake -->

標「待驗」的條目是依程式與文件整理，還沒有實際重現過，歡迎回報。

## 1. 停樹與清殘留

**症狀**：試完不確定樹有沒有關乾淨；或想重來。
**為什麼**：根 daemon 與 llm kernel 是兩個獨立的 daemon，各自起停，兩個都要收。
**解法**：

```bash
aos-daemon-ctl -d ~/aos-demo/tree/stacks/root shutdown
aos-daemon-ctl -d ~/aos-demo/llms/stacks/llm shutdown
```

再用下面這段檢查：列出 cwd 在示範夾底下的行程。先 `cd ~`，不然你自己這個殼（如果正站在示範夾裡）也會被列出來。

```bash
cd ~
for p in /proc/[0-9]*; do c=$(readlink "$p/cwd" 2>/dev/null); case "$c" in "$HOME/aos-demo"*) echo "${p#/proc/} $c";; esac; done
```

什麼都沒印，代表示範夾底下沒有行程了。有印的話，先用 `aos-daemon-ctl -d <那個 stack 的絕對路徑> shutdown` 收它。

- 接著玩：在同一個示範夾把開始用第 3 步的兩行 `nohup aos-exec …` 再跑一次，樹和 ann 會接著醒來。
- 重來：停樹後換一個新的示範夾，不必刪舊的；`stacks/` 只是檔案。
- 殘留了而 `shutdown` 打不通：用上面那段指令找出 pid，確認該行程的 cwd 在你的示範夾裡再收它；不要用按名字殺（`pkill`、`killall`），以免誤傷別棵樹。
- lock 檔的殘留處理：待驗，還沒實測。

## 2. command not found（aos-exec、aos-agent…）

**症狀**：`aos-exec: command not found`，或 `No module named aos_...`。
**為什麼**：「開始用」第 2 步只改「當下那個殼」的 `PATH` 與 `PYTHONPATH`；開新的殼就沒了；或還沒建置，`impls/*/bin` 是空的。
**解法**：在同一個殼重貼第 2 步三行 export；要每個殼都有就跑 `install.sh`（見[安裝總覽](../setup/index.md)）。

## 3. 找不到 nlohmann-json（待驗）

**症狀**：cmake 設定階段說找不到 nlohmann_json（確切字樣未重現）。
**為什麼**：建置依序找 `CMAKE_TOOLCHAIN_FILE`、`VCPKG_ROOT`、`~/dev/vcpkg`；三個都沒有就不設 vcpkg，之後要靠系統套件。
**解法**：指定 vcpkg：`export VCPKG_ROOT=<你的 vcpkg 位置>` 後重跑 cmake；或裝發行版的 nlohmann-json 開發套件（這條路線未實跑）。

## 4. static 連結失敗（待驗）

**症狀**：建置在連結階段失敗，與 `-static-pie` 或靜態程式庫有關。
**為什麼**：執行檔全用 `-static-pie` 連結，系統要有能做靜態連結的 C 程式庫；Manjaro 上連結成功，其他發行版沒有實測。
**解法**：先確認你的系統裝了靜態 libc 開發檔（套件名依發行版而異，未實跑）；仍不行就回報，附上連結錯誤。

## 5. 殼裡殘留 AOS_* 變數

**症狀**：根 daemon 起來行為怪，或以為自己是別台的下屬。
**為什麼**：殼裡留著 `AOS_DAEMON`、`AOS_STACK`、`AOS_CLOCK` 等；根範本說明：殘留 `AOS_DAEMON` 時，根會以為自己是那台的下屬，且 `.env` 清不掉殼裡已有的值。
**解法**：用乾淨的 bash，起根之前先清：

```bash
for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
```

清完再重貼第 2 步的 export（這段請用 bash，不要用 zsh；未實跑）。

## 6. agent 一直不回

**症狀**：`say` 之後 `listen` 等到逾時，什麼都沒有。
**為什麼**：腦的請求要送到 llm kernel；kernel 沒起，或 `AOS_LLM_KERNEL` 指錯。`tree/defs/.env` 預設指向 `${AOS_WS}/../llms/stacks/llm`，所以 llms 必須在 tree 旁邊。
**解法**：先看 `aos-daemon-ctl -d ~/aos-demo/llms/stacks/llm ls`，有它在跑就對；擺法不同就 `export AOS_LLM_KERNEL=<llm kernel 的 stack 絕對路徑>` 後重掛 agent。

<details>
<summary>agent 這邊的三種表現</summary>

- `AOS_LLM_KERNEL` 沒設或只有空白：agent 報 `LlmKernelMissing` 後停下，要帶變數重掛。
- 有設，但那個資料夾不存在：`SendFailed`，冷卻後重試。
- kernel 在但還沒回：agent 一直等、不設期限，每滿 10 分鐘在 stderr 印一行 `no reply from the brain for N minutes …; still waiting`，並說明信卡在哪一格。

以上依範本說明整理；這些錯誤還沒實際重現過。

</details>

下一步：[常見問題](../faq.md)。
