# 2026-09-29 使用者裁定（六）：cgroup 通用規則、直連、投遞

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第十五批。全部裁定後批優先，見[裁定索引](README.md)。

## 第十五批：回答落 spec 隊的七點（同日晚，已落進 spec）

落第十三、十四批與 B1／B2 進 spec 時，落 spec 隊提了七點要使用者看；以下逐條是使用者的回答。以下皆為〔使用者方向 2026-09-29 晚〕。

1. **「初版不用 systemd」的寫法照現在的**〔使用者方向 2026-09-29 晚〕：spec 裡那句措辭可以，不改。
2. **cgroup 改成一條通用規則**〔使用者方向 2026-09-29 晚〕：
   - daemon 啟動時一定要有一棵已經準備好的 cgroup，沒有就報錯。
   - 另給一個開關（CLI flag，設定檔也有對應欄位），讓使用者選「沒有時 daemon 自己建一個」。
   - **取代**：B1 那一整套分情況的寫法（sudo 開時自己建、偵測到 systemd 沒劃子樹就報錯、沒 systemd 時 sudo 自建、不用 sudo 時使用者事先建好），以及追加第 5 條「sudo 開時 daemon 自己建、不用 sudo 時使用者事先建好」。
   - `systemd-run --scope -p Delegate=yes …` 與 service 範例裡的 `Delegate=yes` 仍可留著，當「怎麼準備 cgroup」的做法範例。
   - 文件加一句提醒：在有 systemd 的機器上用這個開關讓 daemon 自己建，會違反 systemd「單一寫入者」約定；不保證能用，也不擋。
3. **LLM 三檔的「不管」改名「直連」**〔使用者方向 2026-09-29 晚〕：避開跟 kernel 份額路線的「kernel 不管」撞名。spec、schema 描述、範例、cli 全部跟著改。notes 裡的歷史裁定（第十三批等）不改原文，只在這裡記改名。
4. **直連是什麼**〔使用者方向 2026-09-29 晚〕：agent 自己打 endpoint，aos 完全不管。endpoint、key 放哪是 agent 自己的事，spec 不定義。
5. **投遞**〔使用者方向 2026-09-29 晚〕：
   - 投件時只檢查目標資料夾是不是一個 node，不是就報錯；之後都不管。
   - 可選的「鬧鐘」：投件者可以設一個逾時，時間到了去看請求有沒有被處理，沒被處理就報錯。
   - **取代**：第十三批「沒有池怎麼辦」與上一輪落 spec 時「目標 node 不存在時每格重試、印錯、待送檔留著」的寫法；也取代「目標 node 存在但沒人處理就堆著、不等、不逾時」裡的「不逾時」（不設鬧鐘時仍是不等）。
6. **「交給 endpoint」只轉發**〔使用者方向 2026-09-29 晚〕：
   - 池 node 的轉發任務只轉發：429、限流、重試全交給 endpoint，aos 不重試。**取代**上一輪 P-405 那句「429 仍照 S-303 有限重試」。
   - 三檔照舊，不合併。
   - 串流中斷後重試怎麼寫檔不另外規定，讓任務自然處理。**取代**上一輪「每次 HTTP 嘗試從頭寫串流檔」。
   - 上一輪其他標「建議預設，未拍板」的，照建議定案：node 還沒有 cgroup 框時 daemon 開格前自己建；範例 unit 用 `KillMode=mixed`；欄名用 `stream_path`；要求 provider 最後附 usage；串流檔在送出前開不了就不送（記 not_sent）。這些拿掉「未拍板」標記。
7. **git 最低版本與 token 預算**〔使用者方向 2026-09-29 晚〕：
   - git 最低版本 2.35，跟 kernel 5.14、Python 3.9 並列，daemon 啟動時自檢。
   - token 預算先不做。第十三批第 4 條「預算首版只算 token」的意思變成：以後做預算時只算 token，首版先不做。

## 落 spec 時的取名與補充

以下是落 spec 隊依上面裁定補的細節，不是使用者逐字裁定；有疑問以使用者後續裁定為準。

- 開關取名 `--create-cgroup`，設定檔欄位 `create_cgroup`（布林，預設 false）；開了就要寫 `cgroup_root`，daemon 在那個位置建。
- 「是一個 node」照找 inst 的規則：目標是資料夾，且有 `.aos/inst.json` 或 `inst.json`。不是就在 stderr 印 `target_not_node`，這封待送檔移除、不重投。
- 鬧鐘寫在待送封套的 `alarm_ms`（投出後幾毫秒）；投出後發件 node 在自己的 `.aos/alarms/`（ignore）記一筆。「被處理」以對方收件區的原件已被取走為準。到期後發件 node 的下一格去看，原件還在就在 stderr 印 `request_not_handled`；不寫待辦、不重投。aos 不為鬧鐘另外叫醒 node。
- 用詞「報錯」一律照第十三批的態度：在 stderr 印一行，不寫待辦。
- 落點：cgroup 在 [B-605](../../spec/daemon.md) 與 [P-101](../../spec/protocol/daemon/startup-and-ipc.md)；直連、只轉發、token 預算在 [S-301～S-305](../../spec/scheduling/llm.md)、[P-405～P-406](../../spec/protocol/llm-work.md)；投遞與鬧鐘在 [P-206](../../spec/protocol/node.md)。
