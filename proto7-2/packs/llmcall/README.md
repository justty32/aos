# llmcall 任務包

問 AI 一次，留下原文與花費，斷掉重跑能接續。

進階、契約與退出碼 → [ADVANCED.md](ADVANCED.md)

## 先懂這幾個詞

1. **node**：這次工作的資料夾，例子會自動建一個暫存 node。
2. **預算與 grant**：可花的額度，以及誰可以花的固定許可。
3. **帳任務（ledger）**：常駐替你記帳的程序。call 要它在跑才會送出；第一次跑會在背景替你起一個，跑完收掉。
4. **call**：同一道題的名字；重跑沿用名字與請求，不會再送一次。
5. **回條**：原文與用量、結帳結果；status 可以查看證據。

## 第一次跑

整段貼上就能跑（用假 AI，不連網、不花錢，約 5 秒）。它會建一個暫存 node、開一本 1000 的帳、在背景起帳任務，問同一題兩次，最後印帳；跑完自動收掉帳任務，檔案留著給你看。

```sh
cd "$(git rev-parse --show-toplevel)"
P="$(pwd)/proto7-2"
LLMCALL_DEMO="$(mktemp -d /tmp/aos7-llmcall-demo.XXXXXX)"
mkdir -p "$LLMCALL_DEMO/.aos" "$LLMCALL_DEMO/budget/llm"
cp "$P/packs/llmcall/examples/fake/grant.json" "$LLMCALL_DEMO/budget/llm/grant.json"
printf '%s\n' '{"round":5,"open":false}' > "$LLMCALL_DEMO/.aos/round.json"
(
  cd "$LLMCALL_DEMO"
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
  LLMCALL_LEDGER_PID=$!
  trap 'kill "$LLMCALL_LEDGER_PID" 2>/dev/null || true; wait "$LLMCALL_LEDGER_PID" 2>/dev/null || true' EXIT
  python3 "$P/packs/budget/bin/aos7-budget" init budget/llm
  python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call demo-c1 --logical author/demo --request "$P/packs/llmcall/examples/fake/req-ok.json" --reserve 623 --out result.json
  python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call demo-c1 --request "$P/packs/llmcall/examples/fake/req-ok.json" --reserve 623
  python3 "$P/packs/budget/bin/aos7-budget" status budget/llm
)
printf '資料保留於 %s\n' "$LLMCALL_DEMO"
```

看到這些就成功了：

- 兩次 call 印出**一模一樣**的一行回條：`"outcome": "answered"`、`"used": 623`、`"billing": "final"`。第二次沒有再問 AI，只是把第一次的回條重印。
- 帳的 status：`"initial": 1000`、`"available": 377`、`"used": 623`（花多少扣多少）。
- 最後一行告訴你資料留在哪；`result.json` 是回條的另存一份。

帳任務沒在跑時，call 一秒內印一行「帳任務沒在跑」並退出、什麼都不送；照那行說的另開終端起帳任務、讓它開著，再跑一次。

## 想做更多

想看某一題留下的全部證據：在印出的資料夾裡跑 `python3 "$P/packs/llmcall/bin/aos7-llmcall" status budget/llm --holder author --call demo-c1`。真模型、人工接回與界線見 [ADVANCED.md](ADVANCED.md)；測試：`systemd-run --user --scope -p TasksMax=300 python3 proto7-2/tests/run_all.py packs/llmcall/tests`。
