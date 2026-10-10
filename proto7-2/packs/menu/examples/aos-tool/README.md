# 一層一層交出 aos 工具

這份選單讓學徒一次只交一個檔，交齊才跑三關檢查。  
沒過就選要改的檔，只把那一檔內容交回學徒。  
先用附帶的練習用 AI 做 mailcount；不連網、不花模型額度。

## 第一次跑

從 repo 根目錄貼上這段。會留一個暫存 node，方便看交件與記錄。

```sh
cd proto7-2
MENU_TOP="$PWD"
MENU_NODE="$(mktemp -d /tmp/aos7-menu-aos-tool.XXXXXX)"
MENU_REQUEST="$MENU_TOP/packs/author/examples/aos-tool-mailcount/request.json"
python3 -B packs/menu/examples/aos-tool/build.py brief "$MENU_REQUEST" > "$MENU_NODE/brief.txt"
systemd-run --user --scope -q -p TasksMax=300 env AOS7_AOS_TOOL_NO_SCOPE=1 \
  python3 -B packs/menu/bin/aos7-menu run "$MENU_NODE" \
  "$MENU_TOP/packs/menu/examples/aos-tool/menu.json" \
  --var name=mailcount --var request="$MENU_REQUEST" --var review=rules \
  --brief "$MENU_NODE/brief.txt"
python3 -B packs/menu/bin/aos7-menu status "$MENU_NODE"
```

實跑時 run 與 status 都印出：

```text
選單 aos-tool：做完，寫了 out/packs/mailcount/README.md、out/packs/mailcount/bin/aos7-mailcount、out/packs/mailcount/aos7_mailcount.py、out/packs/mailcount/tests/test_mailcount.py、out/row、out/report
```

練習腳本會故意回錯一句，讓選單重問；第一次主程式把版本號印成布林值，第二關會擋住。接著選主程式、交正確版，第二次三關全過。已交的檔會藏起，所以選項編號會變。

`--var name=` 填工具名字；`request=` 填需求檔絕對路徑；`review=rules` 用離線規則審查。`build.py brief` 把需求壓成摘要，交給 `--brief`；超過 1500 字會退 2，請先把需求寫得更精簡。這些值第一次建立 run 就固定了；要換題或換模型，換 node 或加新的 `--run 名字`。

| 層 | 在問什麼 |
|---|---|
| which | 下一個交哪個檔？交齊後才出現「都交齊了」。 |
| readme／bin／code／test | 交選中檔的全文，寫進 out/。 |
| row／report | 交索引一列，再交 REPORT 全文。 |
| gates | 自動組 candidate.txt，跑三關；這層不問 AI。 |
| fix | 看失敗摘要，選主程式、測試、文件或交件尾段。 |
| fixdoc／fixtail | 選 README／入口，或索引列／REPORT；也可回上一層重選。 |
| fixcode／fixdocw | 看選中程式／測試，或 README／入口的目前內容，交改好的全文，再跑三關。 |
| fixrow／fixreport | 看索引列／REPORT 的目前內容，交改好的全文，再跑三關。 |

候選在 `$MENU_NODE/menu/aos-tool/candidate.txt`，原始交件在同層 `out/`，每步記錄在 `log.jsonl`。每層出口都是最後一個編號；退出碼與接續方式見 [spec §1、§5](../../spec.md)。

## 換真 AI

先在自己的 node 配好 `budget/llm/grant.json`，把 gateway 設成 `llm.litellm`，並起好 [budget 帳任務](../../../budget/README.md)。init 只開帳；要有 `aos7-budget ledger budget/llm` 常駐在跑，學徒與審查才會送出。審查的 `aos7-author propose` 預設 `--reserve 1000000`，所以 grant 的 `amount` 至少要有 **1,000,000**；學徒也會用額度，帳上可用額度須足以供審查預留。帳額度不足或審查模型沒交回審查時，工具退 3、停在 gates；處理好帳或模型後照原樣重跑，就會重驗同一份候選。這裡不啟動真 AI。

用新 node 或新 `--run`，把上面 run 指令加上 `--llm chatgpt-gpt-6-luna`，並將審查那項換成 `--var review=chatgpt-gpt-6-astra-high`。其餘 `name`、`request`、`--brief` 照題目填；三關通過只完成候選，發布仍由人處理。

註：測試可用 `AOS7_AOS_TOOL_GATES`／`AOS7_AOS_TOOL_AUTHOR` 換成假的 Python 入口，驗證壞輸出等錯誤；也可用 `AOS7_AOS_TOOL_TIMEOUT` 縮短子程序逾時秒數；這些覆寫只供測試，正式使用不要設。`AOS7_AOS_TOOL_NO_SCOPE=1` 只供已在 systemd scope 內的測試／上述練習，避免重複開 scope；bwrap 沙箱仍照常使用。
