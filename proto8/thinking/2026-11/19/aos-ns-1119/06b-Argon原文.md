# Argon 審命名空間設計稿的原文（2026-11-19，Gemini 4 Argon (High)，plan 模式、不准用工具，稿 00～05 全文送審）

← [README](README.md)｜採納表：[06-Argon審與採納](06-Argon審與採納.md)

以下逐字照貼，沒改；文中的 [01]～[05] 指送審時的版本（採納後 03、05 已改）。

---

以下基於你提供的 00～05 六份設計稿進行審查與提案。

---

## (A) 審查：事實矛盾、推論漏洞、遺漏的邊緣狀況、推薦走向的風險

### 1. 【一定要改】推論漏洞（機制死結）：走向 B 維持 `$override`「借包」時，03 宣稱的兩種撞名解法在技術上均不成立
- **出處**：[03] 走向 B 稱生成時讀出每個包的鍵，「兩個來源同名就報 `SpecBad`，訊息教你用 `ag.tool("新名", my.tool("read"))` 改名或 `ag.no(...)` 拿掉一個」；同時生成的 `tools.json` 仍輸出 `"$override": [std的look包, my的包]`。
- **漏洞**：只要生成的 `tools.json` 仍用 `$override` 並排借這兩個包，執行期 `registry.py` 就會把兩個包裡的 `"read"` 疊在一起（後蓋前＋逐欄合併留殘渣）：
  1. **若寫 `ag.tool("my_read", my.tool("read"))`**：這只在 `tools.json` 自己的 `tools` 欄位多加一格 `"my_read"`，**但 `$override` 陣列裡那兩個包的 `"read"` 依然並存且相撞**！生成期檢查器既無從得知你加了 `"my_read"` 就算解掉底包的 `"read"` 衝突；就算放行，執行期腦看到的 `"read"` 已經變成後一個包的 `read`（還混了前一個包的殘留欄位）。
  2. **若搭配 `ag.no("read")`（輸出 `"read": null`）**：如 [05] 邊緣狀況第 9 條自己發現的，`null` 在最上層疊上去會**把兩個包的 `"read"` 一起刪掉**，`std` 的 `read` 也沒了。
- **結論**：在不改執行期 `$override` 機制、又不把包在生成期展開（抄）進 `tools.json` 的前提下，走向 B 的撞名解法是死路。

### 2. 【一定要改】架構矛盾：[05] 第 6 題選 a（「別的庫只在 `agent.py` 明寫、不進全域表」）與 [03] 第三刀（「`agent_def new` 收 `庫/名`」）互相矛盾
- **出處**：[03] 與 [05] 第 6 題推薦選 a：別的庫根只在用它的那支 `agent.py` 裡寫 `ag.lib("my", 路徑)`，不進任何全域表、也沒有固定庫夾。但 [03] 走向 B 與第三刀又規定 `agent_def new` 的 `template` 參數改收 `庫/名`（`/` 前是庫名）。
- **矛盾**：呼叫 `agent_def new {"template": "my/foo"}` 的當下，是要從範本抄出新定義夾，**此時根本沒有某支 `agent.py` 的 `ag.lib("my", ...)` 可供查詢**。若沒有固定庫目錄（第 6 題 b）或全域庫表（第 6 題 c），`agent_def new` 除了寫死的 `std/...` 外，看到任何第三方 `庫/名` 根本不知道去哪裡找那個庫的根路徑。

### 3. 【一定要改】推論漏洞：生成期無法解析執行期環境變數（`$env`），導致跨庫的「生成時查撞名」與「`hooks()` 生成時抄入」失效
- **出處**：[03] 與 [05] 第 6 題 a 示範第三方庫寫成 `my = ag.lib("my", ag.env("AOS_WS", "/lib/my"))`；[00] 裁定 `hooks` 是生成時讀檔「抄」進來；[03] 要求生成時讀每個包查撞名。
- **漏洞**：[05] 邊緣 12 只注意到 `AOS_HOME` 沒設時會跳過檢查，卻忽略了 `AOS_WS` 這類工作區／執行期環境變數（[01] 第 8 類：`.env` 每跳讀一層）在「跑 `agent.py` 生成 `.o`」的編譯當下，往往尚未設定或與執行期不同：
  1. **對 `pack`**：生成時解不出 `AOS_WS` 的真實路徑，就打不開 `my` 的包檔，跨庫撞名檢查直接失效。
  2. **對 `hooks`**：因為 `my.hooks(...)` 是**生成時抄入**而非留 `$env` 指示詞到執行期才解，生成期若解不出該環境變數，`agent.py` 會直接讀檔失敗崩潰。

### 4. 【一定要改】事實與結構矛盾：`std` 的 `tools/<類>/<名>/` 兩層結構讓 `std.tool("read")` 在無搜尋路徑下無法定位
- **出處**：[01] 第 1 類指出工具裝在 `lib/tools/<類>/<名>`（`<類>` 為 `base`、`agent`、`aos`），工具名不含類名；[01] 結論 4 強調「沒有搜尋路徑」。[03] 走向 B 的庫結構圖規定 `<庫根>/tools/<類>/<名>/（std 留 base／agent／aos 三類）`，API 卻設計為 `std.tool("read")`（不傳類名）。
- **矛盾**：
  1. `std.tool("read")` 要生成 `{"$env":"AOS_HOME","$path":"/lib/std/tools/??/read"}` 時，若不在生成期依序搜尋 `base`、`agent`、`aos` 三個子夾（這就是隱性搜尋路徑，且沒設 `AOS_HOME` 時連搜尋都做不到），根本拼不出路徑。
  2. 若 `std` 的 `tools/` 有 `<類>` 這一層，而第三方庫 `my` 的 `tools/` 只有一層 `tools/<名>/`（或分類不同），「一個庫＝一個長相固定的資料夾」就不成立，`ag.lib` 無法用同一套規則拼出工具路徑。

### 5. 【一定要改】推薦走向的風險：推薦組合（B ＋ 第 2 題 a ＋ 第一刀不搬家）實質上做出了使用者明確拒絕的「前者」
- **出處**：[00] 使用者原話在二選一中明確拒絕「前者：只是 Python 這邊寫起來像標準庫」，指定要「後者：連 aos 本身的東西都要分命名空間——**定義夾、工具名本身就帶前綴**，不同來源的同名東西不會撞」。
- **風險**：[03] 與 [05] 推薦「走向 B ＋ 第 2 題選 a（腦看到短名，即 `tools.json` 鍵名不帶前綴）＋ 第一刀不搬檔」：
  1. 第一刀做完，生成的 json 與目錄結構半個字都沒變，**100% 就是使用者拒絕的「前者」**（[05] 邊緣 27 隊長補註也承認第一刀是假象）。
  2. 就算走到第三刀，選了第 2 題 a 後，`tools.json` 裡的鍵名（工具名）與定義夾名依然不帶前綴；且只要走 `$override` 借包，在手寫 json、kit、`tools_sub.json`、或庫事後更新時（邊緣 6、13、23），不同來源的同名工具在執行期**照樣悄悄相撞**。這與使用者拍板的「後者」核心訴求嚴重脫節。

### 6. 【建議】事實矛盾：第一刀／[05] 第 4 題 b「不搬家」時，`std` 根本沒有單一庫根
- **出處**：[01] 現況中，`tools` 與 `packs` 在 `$AOS_HOME/lib/` 下，但 `templates` 在 `$AOS_HOME/templates/`（不在 `lib/` 下）。[05] 第 4 題 b 卻寫「不搬：`$AOS_HOME/lib` 與 `templates` 就算 std 的根」。
- **矛盾**：[03] 定義一個庫是一個固定長相的資料夾（`<庫根>` 下並列 `tools/`、`packs/`、`templates/`、`hooks/`）。不搬家時，`std` 的 `tools` 與 `templates` 分屬不同層級的目錄，根本不是一個資料夾，程式碼裡必須為 `std` 寫死特判路徑，無法與 `ag.lib()` 共用邏輯。

### 7. 【建議】推論漏洞：「自己那格蓋底下＝故意（不報錯）」會讓跨庫替換工具踩中「逐欄合併殘渣」bug
- **出處**：[04] 與 [05] 邊緣 7、8 規定「並排兩個底同名＝碰巧（報錯）；自己那格蓋底下＝故意（放行）」，並稱逐欄合併殘渣「在繼承是特性、在撞名是 bug」。
- **漏洞**：當使用者在 `agent.py` 用了 `std.pack("look")`（含 `read`），又在自己那格寫 `ag.tool("read", my.tool("read"))` 時，意圖是**整支換成 `my` 庫的 `read`**（跨庫替換），而非「繼承 `std` 的 `read` 並微調一欄」。但按上述規則，生成期會當成「故意蓋」放行，執行期 `$override` 卻會把 `std/read` 與 `my/read` 逐欄合併，導致前者的 `env` 等欄位殘留到 `my/read` 上。

### 8. 【建議】判準缺失：菱形繼承「指的是同一支工具就不算撞」未定義何謂「同一支」
- **出處**：[05] 邊緣 7 稱兩個包疊同一個底包（菱形）時，以「指的是同一支工具就不算撞」排除。
- **漏洞**：若中繼包 A 與中繼包 B 都疊了底包 C 的 `read`（`path` 相同），但包 A 覆寫了 `env: {"X": "1"}`、包 B 覆寫了 `env: {"X": "2"}`，兩包並排時算不算同一支？
  - 若只比對 `path` 相同就不報錯，執行期兩包的 `env` 仍會悄悄後蓋前；
  - 若比對整格 JSON 完全相等才不算撞，那只要任一中繼包微調過欄位就會報錯。稿中缺乏明確判準。

### 9. 【建議】遺漏與不對稱的邊緣狀況（共 4 點）
1. **`std.fsm()` 無參數 vs `std.hooks("agent-fsm")` 有組名**：[03] 與 [05] 直接定死 `std.fsm()` 不收參數（固定指 `templates/agent-fsm/*.py`），假設一個庫永遠只有一組 FSM 格程式。若 `std` 或第三方庫有第二組 FSM（或如 `reviewer` 範本要借特定組），API 立刻卡死，且與 `std.hooks(組名)` 不對稱。
2. **`tools_sub.json` 被排除在 `agent.py` 之外**：[05] 邊緣 23 稱 `tools_sub.json` 不經 `agent.py`。但 `tools_sub.json` 同屬定義夾產物，若同一定義夾裡 `tools.json` 是 `.o`、`tools_sub.json` 卻得手寫且無撞名檢查，違反「定義夾由 `agent.py` 生成」的一致性。
3. **執行期 stack 動態加工具（`aos-agent tools add` / `self_tools add`）的行為未定義**：[01] 提到執行期可在 stack 疊加工具，但 [03]～[05] 完全沒交代走命名空間後，stack 動態加入異庫同名工具時如何命名、以及是否也會觸發與定義層工具的逐欄合併殘渣。
4. **現有 `$prefix` 指示詞未盤點**：[01] 第 4 類提及系統已有 `$prefix` 指示詞，但全文未說明其現有作用，以及是否與路徑／命名空間前綴重疊。

### 10. 【小事】刀次工作清單前後不一致
- [03] 在「不只工具」表格寫道：`hook 組：進（第三刀後有自己的位置）`（即拆到 `<庫根>/hooks/<組>.json`），但在 [03]「要動的程式」第一、二、三刀具體清單中，完全漏列「把 hook 組從範本拆出並處理與範本 `hooks.json` 雙份同步（邊緣 16）」這項工作。

---

## (B) 提案：我會怎麼做不一樣（附理由與代價）

為了同時滿足使用者的**「C 與 .o」定調**與**「後者：定義夾、工具名本身帶前綴，不同來源不撞」**，並解開上述 (A)1～(A)4 的技術死結，建議調整如下：

### 1. 真正的「C 與 .o」：生成期將 Pack 靜態展開寫入 `tools.json`（包在編譯期展開、工具路徑維持借用）
- **做法**：
  在 `agent.py` 呼叫 `std.pack("look")` 或 `my.pack("net")` 時，生成 `tools.json`（`.o` 檔）**不再輸出 `"$override": [".../look.json"]`，而是由生成器直接讀取包檔，將裡面的工具清單展開寫入 `tools.json` 的 `tools` 表**（每支工具的 `path` 依然是 `{"$env": ..., "$path": ...}` 指向庫的工具夾）。`$override` 留給執行期「stack 蓋定義（C-52）」專用。
  同時在 Python API 提供包級操作：`my.pack("net", prefix="my_", exclude=["read"], rename={"ping": "net_ping"})`。
- **理由**：
  1. **一舉解開 (A)1 死結**：因為包在生成期已在 Python 內展開成 dict，單獨拿掉某庫的 `read`、或將某庫的 `read` 改名，產出的 `tools.json` 就是乾乾淨淨的扁平表。
  2. **一舉消滅 (A)7（跨庫逐欄合併殘渣）與邊緣 13（包事後偷加工具導致執行期悄悄蓋）**：在 `agent.py` 裡用 `ag.tool("read", my.tool("read"))` 替換工具時，是在 Python 內**整格替換**，不經執行期 `$override` 逐欄合併，絕無殘渣；且 `.o` 一旦生成，工具集合就定死（如同 Lisp read-time intern 與 C 的 `.o`），事後庫的 pack 增刪工具不會暗中改變已編譯 agent 的行為。
- **代價**：
  - 當某個 pack 新增工具時，使用它的 agent 需重跑 `agent.py` 重生 `.o` 才會獲得新工具（但若工具夾內的程式碼修 bug，因工具 `path` 仍是借的，無須重生即生效）。
  - 生成的 `tools.json` 從幾行 `$override` 變成展開後的幾十行工具表（但既然 `tools.json` 是給機器讀的 `.o`，展開反而讓 `aos-tools` 與 `defs check` 一目了然）。

### 2. 工具名採「`std` 短名、非 `std` 庫預設冠 `<庫名>_` 前綴」（即 05 第 2 題選 b），搭配「生成期展開」零執行期改動
- **做法**：
  - `std` 庫的工具進 `tools.json` 預設維持短名（`read`、`ls`）。
  - 透過 `my = ag.lib("my", ...)` 引入的第三方庫，其 `my.pack()` 與 `my.tool()` 在展開進 `tools.json` 時，**鍵名預設自動冠上 `my_` 前綴（如 `my_read`）**（除非寫 `agent.py` 的人顯式寫 `prefix=""` 或指定新名）。
  - 生成期最後檢查展開後的 `tools.json` 鍵名，若仍有同名（例如 `std` 裡剛好有 `my_read` 與 `my` 庫的 `read` 撞成同一鍵，即邊緣 1），當場報 `SpecBad`。
- **理由**：
  - 真正落實使用者要的「後者：工具名本身就帶前綴，不同來源的同名東西不會撞」，也與現有 MCP 凍結工具 `<server>_<tool>` 慣例一致。
  - 保留 `std` 短名則省下 62 支基礎工具的 token（顧及 C-92 小模型限制），且免改現有範本的 `system.txt` 與知識庫。
  - 因為配合提案 1 在生成期展開，冠前綴只是生成 `tools.json` 時改 key，**執行期（`registry.py`、`brain.py`、`act.py`）一行都不用改**。
- **代價**：
  - 腦看到的第三方工具名會帶 `<庫名>_`（平均多 3～8 個字元）。

### 3. 庫的定址改為「固定庫夾 `$AOS_HOME/lib/<庫名>` 為主、標準環境變數 `AOS_LIB_<庫名大寫>` 為輔」（融合 05 第 6 題 a 與 b）
- **做法**：
  - 規定庫名 `<name>` 預設對到 `$AOS_HOME/lib/<name>`（`std` 就是 `$AOS_HOME/lib/std`）。
  - 若第三方庫放在別處（如工作區或外部 repo），由環境變數 `AOS_LIB_<NAME>`（如 `AOS_LIB_MY=/path/to/my`）定錨；在 `agent.py` 寫 `my = ag.lib("my")`（自動用 `$AOS_LIB_MY` 或 `$AOS_HOME/lib/my`），生成進 json 的指示詞為 `{"$env": "AOS_LIB_MY", "$path": "/tools/foo"}`。
- **理由**：
  - **解開 (A)2 死結**：`agent_def new {"template": "my/agent-x"}` 不必依賴某支 `agent.py`，直接查 `$AOS_LIB_MY` 或 `$AOS_HOME/lib/my` 就能找到 `templates/agent-x`，且 `lineage` 可統一記 `{"template": "my/agent-x"}`。
  - **解開 (A)3 死結**：把「找庫的變數（`AOS_LIB_*` / `AOS_HOME`）」與「執行期實例變數（`AOS_WS`）」分離，要求編譯期（跑 `agent.py` 時）庫的環境變數即已就位，確保生成期能讀包展開、能抄 `hooks`。
- **代價**：
  - 外部庫若不放進 `$AOS_HOME/lib/<庫名>`（或建 symlink），則在跑 `agent.py` 生成與執行時都需設定 `AOS_LIB_<NAME>`。

### 4. 拍平庫內 `tools/` 的 `<類>` 層，並讓 `fsm` 與 `hooks` 對稱獨立
- **做法**：
  將每個庫的目錄結構嚴格統一為：
  ```text
  <庫根>/_metainfo.json
         tools/<工具名>/        ← 拍平 base/agent/aos（原始碼 py/tools/<類>/<名> 可留分類，install.py 安裝時拍平並檢查不撞名）
         packs/<包名>.json
         templates/<範本名>/    ← 支援單層或子夾（如 kernel/llm-kernel）
         hooks/<組名>.json      ← 獨立出來，範本若要用也從這裡抄
         fsm/<組名>/<格>.py     ← 獨立出來，API 改為 std.fsm("agent-fsm")（可預設 default="agent-fsm"）
  ```
- **理由**：
  - **解開 (A)4 死結**：`std.tool("read")` 與 `my.tool("foo")` 都能無歧義、免搜尋地直接對到 `<庫根>/tools/<名>`，所有庫長相 100% 一致。
  - **解開 (A)9-1 與邊緣 16、19**：`std.hooks("agent-fsm")` 與 `std.fsm("agent-fsm")` 完全對稱，不再寄居於 `templates/` 底下，消除雙份抄本同步問題。
- **代價**：
  - `install.py` 需把 `py/tools/{base,agent,aos}/*` 拍平裝入 `lib/std/tools/*`（因 [01] 已確認現有 91 支工具在三類間無同名，拍平無衝突）。

### 5. 重新分刀：用 Linux Symlink 一步到位建立 `lib/std`，不做「第一刀不搬家」的假動作
- **做法**：
  - **第一刀（立 `lib/std` 真結構＋相容 Symlink＋生成期展開）**：
    1. 修改 `install.py` 直接裝進 `$AOS_HOME/lib/std/{tools,packs,templates,hooks,fsm}`；同時在舊路徑（`$AOS_HOME/lib/tools/<類>/<名>`、`$AOS_HOME/lib/packs`、`$AOS_HOME/templates`）自動建立指向 `lib/std/...` 的 **symlink**。
    2. 修改 `agent_spec.py` 支援 `ag.std`、`ag.lib`、生成期展開 pack、非 `std` 庫冠前綴與撞名檢查（連同 `tools_sub.json` 一起支援）。
  - **第二刀（遷範本、CLI 與 `defs check`）**：
    把 repo 內所有範本、包內路徑、`agent_def new`（收 `<庫>/<範本>`）、`defs check` 全面切向 `/lib/std/...`。
  - **第三刀（拔除舊路徑 Symlink）**：
    待活樹（跑著的 agent stack）重啟或遷移完畢後，移除 `install.py` 裡的舊路徑 symlink。
- **理由**：
  - 避免原稿第一刀「不搬家、在 `agent_spec` 寫假路徑特判，第二刀又打掉重寫」的虛功，第一刀產出的 `.o` 就是最終真實路徑 `/lib/std/...`。
  - 透過舊路徑 symlink，**正在跑的活樹（stack 裡存著 `/lib/tools/base/read` 舊路徑的 agent）在 `install.py` 後完全不會斷（徹底解掉邊緣狀況 4）**，可平順過渡。
- **代價**：
  - 第一刀需多改 `install.py` 約 30～50 行以建立 `lib/std` 與舊路徑 symlink。
