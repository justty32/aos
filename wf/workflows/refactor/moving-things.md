# 搬移與改名

[refactor](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

適用於檔案換位置、目錄改名與專案拆 repo（aos 現在是獨立 repo，拆 repo 那幾條是當時拆 repo 的經驗）；以下列出六類常見斷裂與偵測程序。

```text
Done when: <逐檔比對已落地、六類斷裂已掃、工具冒煙測試過、連結歸零、建置指令實跑過（本專案沒有 CI）>
```

## 鐵律：複製，不要搬移，直到驗證完

`cp -a` 進新位置 → 驗證 → 最後才清掉舊的。這樣不需要靠 tar 當救命繩，
而且中途出錯不會兩邊都沒有。清舊的之前先確認**來源已 commit 且已 push**。

## 六類會斷的東西

**只 grep 連結是不夠的。** 依實際踩到的頻率排序：

### 1. 硬編碼絕對路徑

```sh
grep -rn '<舊路徑>' --include='*.py' --include='*.sh' --include='*.json'
```

常見目標：腳本裡的資料根目錄、設定檔的路徑欄位、多支腳本共用的預設路徑常數。

### 2. `__file__` 相對推導——**語意會變**

```sh
grep -rn '__file__' --include='*.py'
```

程式碼與相對路徑文字都沒變，**基準點仍會變**。
例：某支工具用 `Path(__file__).parent.parent / "backups"` 當備份目錄，搬進版控範圍之後每次備份都把大檔提交進版控。

判準：`parents[n]` 指向**跟著一起搬的東西**就安全，指向**沒跟著搬的東西**就要改。

### 3. package import

```sh
grep -rn '^from \|^import ' --include='test_*.py'
```

`from scripts import x` 在 `scripts/` 消失後死掉；主程式可能仍能執行，只有依賴 package 佈局的測試失敗。
改成從自身位置推導。

### 4. 相對 markdown 連結

跨 repo 拆分後**原本的兄弟變成別的 repo**。`git ls-files` 走到**子 repo 的指標**就停，所以檢查器預設看不到子 repo 內部。本專案現在沒有子 repo：aos 是獨立 clone，`simple_tools` 的 submodule 11-13 晚起不再是工作 repo（[dev-env](../dev-env.md)），這條留給真的要拆 repo 時。

修法：拿目標的 basename 去整個工作區找實體，再算相對路徑。
同名多候選要手工指定。

### 5. CI 與外部設定

```sh
grep -rn '<舊路徑>' .github/ *.yml *.json <agent 工具的設定檔>
```

常見目標：CI workflow 裡跑的指令、agent 工具的 hook／設定檔。本專案沒有 CI（repo 沒有 `.github/`，驗證都由 agent 跑，見 [dev-env](../dev-env.md)），這類只剩 agent 工具的設定檔要查（例 `.claude/settings.json`）。

### 6. 執行期資料目錄

不進版控的東西（鎖、投遞區、DB 快照）不能跟著搬進 repo，但它們的路徑常寫在跟著搬的程式裡。

路徑指向已經不存在的目錄時，**「已釋放／不存在」的檢查會恆真通過**。
例：某個鎖檔檢查指著一個已被刪掉的目錄，於是每次收尾檢查都在檢查一個不可能存在的路徑。

## 驗證程序

```sh
# 1. 逐檔比對有沒有東西掉在半路（size + basename）
#    刻意不搬的要明確列出來，不要靠「應該沒漏」
# 2. 六類掃描（上面）
# 3. 每支搬過的工具冒煙測試
for f in <moved>/*.py; do python3 -c "import ast;ast.parse(open('$f').read())"; done
python3 <tool>.py --help
# 4. 連結檢查（可選，預設不跑；大量搬檔後擔心連結壞掉再跑），並確認檢查器涵蓋新位置
python3 wf/tools/check_anchors.py <root>   # 或該專案的連結檢查器
# 5. 本專案沒有 CI：改跑 testing.md 的建置指令一次
```

## 改名時額外注意

- **名字會不會跟別的東西撞。** 例：某個設定集一度改叫 `main`，與分支名和目錄名相撞，使 `git log main` 報 ambiguous；加前綴解掉。
- **分支只有一個 `main`**（[common/user](../common/user.md)「分支慣例」），改名改這一個就好；交件走 `wf/tools/commit-request`。以前「所有分支都要改、用 worktree 在別的分支上做」的情境已不在。
- **區分「同一個東西的路徑」與「當時的紀錄」。** 驗收報告、歷史 log 這類**當時的紀錄**裡的舊路徑**不要改**——那些記的是當時實際用的路徑，改了就是竄改紀錄。
  只改「還會再跑」的東西：活工具、spec、CI、現役文件。
