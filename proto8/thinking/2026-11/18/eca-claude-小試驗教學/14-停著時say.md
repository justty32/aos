這份教你 agent 停著（暫停、停下、睡著、不在表上）的時候對它 `say` 會怎樣（試驗 14，11-18 晚在家機用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「停著的時候 aos-say」。**沒有 `aos-say` 這支指令**，正確是 `aos-agent say`（收的人看 [13](13-aos-loop控制停止與繼續.md)）。

## 結論

- **只要 agent 還在 daemon 表上，say 一定寄得進去**：信放進 `<stack>/queue/new/`，指令印出信件名稱、退 0，只在 stderr 多一行 warning 告訴你它為什麼不會馬上答。
- 之後 `ctl resume`／`start`／`wake` 起來，**信照樣被答**，不會掉。`listen` 在停著時等不到答案，報 `AnswerMissing`。
- **agent 不在表上**（打錯名字、或 `ctl rm` 掉了）就寄不進去：`InstanceMissing`，退 1，沒有信。
- 要看是哪一種停，讀 warning 那句就知道該下哪個指令。

## 一步一步

前提同 [13](13-aos-loop控制停止與繼續.md)（樹起好、ann 掛上、haiku），都在 `~/aos-home` 打。

**1. 暫停中**

```sh
aos-agent -d .stack ctl pause ann
aos-agent -d .stack --target ann say "reply with the single word: paused-test"
```

會看到信件名稱（例 `000000000002.0179…`）加 stderr 一行：`aos-agent: warning: queued in …/.stack/procs/ann/queue/new/; ann is paused and will not answer until resumed: aos-agent ctl resume --target ann`。`listen --timeout-s 8` 先印 `… Still waiting, Ctrl-C to leave`，8 秒後 `AnswerMissing waited 8 s; … is not answered yet (the letter is in queue/new/)`，退 1。`ctl resume ann` 之後 `listen` 拿到 `paused-test`。

**2. 停下（stop）**

```sh
aos-agent -d .stack ctl stop ann
aos-agent -d .stack --target ann say "reply with the single word: back"
aos-agent -d .stack --target ann listen --timeout-s 5
ls .stack/procs/ann/queue/new
```

會看到 `say` 退 0、warning：`queued in …/queue/new/; nothing is running ann now; it is stopped on the daemon table (ann is stopped); start it: aos-agent ctl start --target ann`。`listen` 的 warning：`… is still in queue/new/, but nothing is running ann now; … start it: …`，5 秒後 `AnswerMissing`。`ls` 看得到那封信。

```sh
aos-agent -d .stack ctl start ann
```

會看到：`started (same stack); 1 queued letter(s) will be answered next`（它說有幾封排著）。如果停之前是暫停的，還會多一句 `it was paused when it went down, so it comes back paused: aos-agent ctl resume --target ann`（我就是這樣），要再 `resume`；之後 `listen --letter <信名>` 拿到 `back`。

**3. 睡著（sleep）**

```sh
aos-agent -d .stack ctl sleep ann
aos-agent -d .stack --target ann say "reply with the single word: woke"
```

warning：`… nothing is running ann now; it is asleep on the daemon (ann is sleeping); wake it: aos-agent ctl wake --target ann (if the daemon itself is down, restarting it wakes ann too: …)`。`ctl wake ann` 說 `1 queued letter(s) will be answered next`，`listen` 拿到 `woke`。

**4. 不在表上**

```sh
aos-agent -d .stack --target nope say hi; echo rc=$?
```

會看到：`aos-agent: error: InstanceMissing nope is not on the daemon table (removed with rm, exited 0, or an adopted body ended with unknown status; known nonzero exits stay stopped with a reason; the stack may still be there: aos-agent ctl add with the same name to pick it up again)`，`rc=1`。對剛 `ctl rm ann` 掉的 ann 一樣，不會幫你排信。`ctl add --auto-restart -w . agents/ann` 同名加回來，stack 還在、對話接得上。

## 沒實測的

- daemon 整台沒在跑時 say：未實測。上面 sleep 那句 warning 提到「daemon 停了，重起也會叫醒它」，但信有沒有寫得進去這份沒試。
- `ctl start --on-queued fail|ok`（`start`、`wake` 碰上排著的信時的態度）沒動。
- say 加畫面開著（`open`）的情況。

## 發現的問題

1. **停著時 `say` 退 0**，不看 stderr 的人會以為已經回了；要靠 warning 或 `listen` 才知道。程式要的是「信不掉」，這是設計，但腳本裡串 `say && listen` 時要把 `listen` 設 `--timeout-s`，不然會一直等。
2. 停下後 `listen` 的等待 warning 裡寫的 `start it: aos-agent ctl start --target ann` 可以直接照打。
