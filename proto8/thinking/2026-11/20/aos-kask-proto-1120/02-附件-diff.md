# 附件：原型對骨架的 diff 全文（乾淨複本 base 對 mine，只有 py/tools/aos/kernel 兩檔），以及實跑用的 hook 與量測小程式在哪

← [README](README.md)｜說明：[02-原型做法](02-原型做法.md)

原檔在公司 WSL `~/.aos/scratch/aos-kask-proto-1120/proto.diff`（`diff -ruN -x __pycache__ base/proto8/py/tools/aos/kernel mine/proto8/py/tools/aos/kernel`）。可以丟，不是提案。

```diff
diff -ruN base/proto8/py/tools/aos/kernel/kask.py mine/proto8/py/tools/aos/kernel/kask.py
--- base/proto8/py/tools/aos/kernel/kask.py
+++ mine/proto8/py/tools/aos/kernel/kask.py
@@ -0,0 +1,56 @@
+# 原型（線 aos-kask-proto-1120，可丟）：骨架的特殊信箱——每輪開頭把 <stack>/kask/ 裡的問句信用定義夾的 kask.json 回掉。
+# 問句信不進請求那條路：不排隊、不過三個 hook、不進帳本。名字 kask、kask.json、kernel_ask 都是示意。
+import json
+import os
+
+import letters
+
+BOX = "kask"          # 特殊信箱：站的 stack 底下、跟 requests/ 並排（示意名）
+DECL = "kask.json"    # 「另外一個 json」：跟 kernel.json 同一夾（示意名）
+KEY = "kernel_ask"    # 問句信 body 的鍵，值必須是 true（示意名）
+
+
+def _waiting(box):
+    """new/ 或 cur/ 有信才要動；沒有就不起任何子行程（每輪都會走到這裡）。"""
+    for part in ("new", "cur"):
+        try:
+            if any(not n.startswith(".") for n in os.listdir(os.path.join(box, part))):
+                return True
+        except OSError:
+            pass
+    return False
+
+
+def answer_of(cfg_dir, body):
+    """回信 body：形狀對就回那份 json（沒放＝null 加一句原因），不對回 AskBad。"""
+    if not isinstance(body, dict) or body.get(KEY) is not True:
+        return {"error": {"code": "AskBad", "msg": "a question letter must be {\"%s\": true}" % KEY}}
+    try:
+        with open(os.path.join(cfg_dir, DECL), encoding="utf-8") as stream:
+            return {KEY: json.load(stream)}
+    except FileNotFoundError:
+        return {KEY: None, "why": "this kernel gives no declaration"}
+    except (OSError, ValueError, UnicodeError) as error:
+        return {KEY: None, "why": "declaration unreadable: %s" % error}
+
+
+def answer_all(ctx, cfg_dir):
+    """建（沒有才建）特殊信箱、認領全部、逐封回信並收掉；回答了幾封。"""
+    box = os.path.join(ctx.stack, BOX)
+    if not os.path.isdir(os.path.join(box, "new")):
+        letters.init(box, ctx.die)
+    if not _waiting(box):
+        return 0
+    letters.take_all(box, ctx.die)
+    count = 0
+    for name in letters.names(box):
+        letter = letters.see(box, name, ctx)      # 信封壞＝warning、丟掉（讀不到 reply_to，回不了）
+        if letter is None:
+            continue
+        reply = json.dumps(answer_of(cfg_dir, letter["body"]), ensure_ascii=False)
+        code, _ = letters.post(["done", "--reply", box, name], reply)
+        if code != 0:
+            ctx.warn("question %s: could not send the answer, letter dropped" % name)
+            letters.post(["done", box, name])
+        count += 1
+    return count
diff -ruN base/proto8/py/tools/aos/kernel/round.py mine/proto8/py/tools/aos/kernel/round.py
--- base/proto8/py/tools/aos/kernel/round.py
+++ mine/proto8/py/tools/aos/kernel/round.py
@@ -7,6 +7,7 @@
 import letters
 import hold
 import hooks
+import kask
 from aos import hook_run
 from aos import tool_io
 
@@ -71,6 +72,8 @@
         except OSError as error:
             ctx.die("LockFailed", "cannot lock requests/.flock: %s" % error)
         try:
+            # 原型（aos-kask-proto-1120）：每輪開頭先回特殊信箱的問句信；它們不進下面這條請求路。
+            kask.answer_all(ctx, os.path.dirname(os.path.abspath(cfg_path)))
             ctx.previous = {}
             pack.collect(ctx, before_reply=lambda original, reply: hooks.before_reply(ctx, original, reply))
             incoming = pack.check(ctx)
```

## 實跑用的其他檔（都在暫存夾，不進 repo）

| 檔 | 是什麼 |
|---|---|
| `src/kask.py` | 上面那個新檔的原稿（`apply.sh` 抄進 `mine/`、重裝） |
| `ask.py` | 問的人與量測：`one`（問一次、數回信）、`median`（連問 N 次取中位數）、`burst`（灌 N 封＋一封普通請求）、`pair`（問句與普通請求一起寄）、`slow`（先寄一封讓這輪變慢的請求、0.3 秒後問）、`pile`（kernel 停著時堆 N 封、再起來） |
| `hooks/seen` | 試 hook：把看到的每一封記進站 stack 的 `seen.log`；body 有 `"slow": true` 就先睡 3 秒（造一輪很久） |
| `up.sh`、`run.sh`、`down.sh` | 起樹、整套實跑（輸出 `run.out`）、收樹 |
| `env.sh`、`install.sh`、`test.sh`、`apply.sh` | 清 `AOS_*`、裝乾淨複本、跑測試、套原型 |
