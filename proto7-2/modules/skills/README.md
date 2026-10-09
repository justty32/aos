# skills 包（幫 AI 挑工具說明書）

← [modules](../README.md)

**一句話（ELI5）**：一個資料夾裡有個 `skills/` 抽屜，每本說明書是一個子資料夾；`index` 把每本的書名和一句簡介抄成目錄，`pick` 照你的題目挑一本、告訴你它放哪。

## 要懂的三個詞

| 詞 | 一句白話 |
|---|---|
| skill（說明書） | 一個資料夾，裡面的 `SKILL.md` 開頭寫 `name`（＝資料夾名）和 `description`（什麼時候用），後面是做法。 |
| 目錄（索引行） | `- 名字: 簡介`，一本一行。挑的時候只看這一行。 |
| pick（挑一本） | 給一句題目，回最合適那本 `SKILL.md` 的完整路徑；都不合回 `none`。 |

文中的 **node** 就是「裝著 `skills/` 的那個資料夾」，不用另外學。

## 第一次跑（照抄，約 1 分鐘，不花錢、不連網、不寫進 repo）

先 `cd` 進 repo（任何一層都行，第一行會自己找 repo 根；人在 repo 外就把第一行改成 `S=<repo 路徑>/proto7-2/modules/skills`），整段貼上：

```sh
S="$(git rev-parse --show-toplevel)/proto7-2/modules/skills"
N="$(mktemp -d /tmp/skills-demo.XXXXXX)"; mkdir "$N/skills"
ln -s "$S"/library/* "$N/skills/"
python3 "$S/aos7-skills" index "$N"
python3 "$S/aos7-skills" pick "$N" "看看信箱，把別的 agent 寄來的信辦掉"
```

逐行在做什麼：① `$S` 是工具所在處；② 開一個空資料夾 `$N` 當 node、在裡面放空抽屜 `skills/`；③ 把工具附的三本說明書（放在 `library/`）連進抽屜；④ `index` 抄目錄；⑤ `pick` 照題目挑一本。

看到這些就跑通了：

```text
- aos-inbox: Read and handle the agent mailbox …
- aos-test: Run the proto7-2 test suite …
- wf-lint: Check the wf/ documentation tree …
/tmp/skills-demo.XXXXXX/skills/aos-inbox/SKILL.md
```

最後一行就是挑到的那本說明書，打開照著做。這裡沒問 AI：它數題目和每本簡介有幾個字相同，挑相同最多的那本；一本都對不上時印 `none`，下面多一行說怎麼辦。資料都在 `$N`，不要了 `rm -rf "$N"`。

**第一次跑到這裡就夠了。** 讓 AI 挑、借給 aos 任務、出錯時各種情況，見 [ADVANCED.md](ADVANCED.md)。
