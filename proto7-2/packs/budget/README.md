# budget 任務包

每次用資源先預留、再使用、後結帳，讓花費記得準，斷掉也不多扣。

進階、契約與退出碼 → [ADVANCED.md](ADVANCED.md)

## 先懂這幾個詞

1. **node**：工作的資料夾，這段會自動建一個暫存 node。
2. **grant**：誰可以用多少資源的固定許可；預算名須與資料夾名相同。
3. **帳任務（ledger）**：常駐記帳的程序。init 只是開一本空帳；要有帳任務在跑，call 才會處理。第一次跑會在背景替你起一個，跑完收掉。
4. **holder**：許可上的持有人，例子是 api。
5. **request**：同一次工作的名字；重跑用同一名字與內容，就不多扣。

## 第一次跑（不用 daemon）

整段貼上就能跑（假 API，不連網，約 3 秒）。它建一個暫存 node、開一本額度 3 的帳、在背景起帳任務，同一個請求送兩次，最後印帳；跑完自動收掉帳任務，檔案留著。

```sh
cd "$(git rev-parse --show-toplevel)"
P="$PWD/proto7-2"
BUDGET_DEMO="$(mktemp -d /tmp/aos7-budget-demo.XXXXXX)"
mkdir -p "$BUDGET_DEMO/.aos" "$BUDGET_DEMO/budget/demo"
cp "$P/packs/budget/examples/fakeapi/grant.json" "$BUDGET_DEMO/budget/demo/grant.json"
printf '%s\n' '{"round":5,"open":false}' > "$BUDGET_DEMO/.aos/round.json"
(
  cd "$BUDGET_DEMO"
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/demo &
  BUDGET_LEDGER_PID=$!
  trap 'kill "$BUDGET_LEDGER_PID" 2>/dev/null || true; wait "$BUDGET_LEDGER_PID" 2>/dev/null || true' EXIT
  python3 "$P/packs/budget/bin/aos7-budget" init budget/demo
  python3 "$P/packs/budget/bin/aos7-budget" call budget/demo --holder api --request r1 --payload "$P/packs/budget/examples/fakeapi/payload.json"
  python3 "$P/packs/budget/bin/aos7-budget" call budget/demo --holder api --request r1 --payload "$P/packs/budget/examples/fakeapi/payload.json"
  python3 "$P/packs/budget/bin/aos7-budget" status budget/demo
)
printf '資料保留於 %s\n' "$BUDGET_DEMO"
```

## 看到什麼算成功

- 兩次 call 印出相同的一行：`"outcome": "accepted"`、`"used": 1`。第二次沒有再做，只重印結果。
- 帳：`"initial": 3`、`"available": 2`、`"used": 1`——送了兩次只扣 1。

帳沒在跑時 call／settle 會一秒內說「帳任務沒在跑」並退出。

## 想做更多

接 step、人手結算與界線見 [ADVANCED.md](ADVANCED.md)；測試：`systemd-run --user --scope -p TasksMax=300 python3 proto7-2/tests/run_all.py packs/budget/tests`。
