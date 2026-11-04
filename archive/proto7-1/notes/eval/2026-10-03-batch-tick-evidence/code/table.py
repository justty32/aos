import json,glob,os
NAMES={("base",0,1):"A 原樣（每線每次一程序）",("btick",0,1):"B1 只批 tick，一次一批不限條數",("bboth",0,1):"B2 tick＋tock 都批，一次一批",("bboth",16,4):"B3 tick＋tock 都批，每批 ≤16 條、最多 4 批並行",("cheap",0,1):"C1 不批，python3 -S -I",("cfloor",0,1):"C2 不批，極小 C tick／tock（下限）"}
order=list(NAMES)
for w in ("empty","each3"):
  print("\n#### 工作量：%s\n"%("空任務（只有 5 條線各一個 keep sleeper）" if w=="empty" else "每回合 3 個 each `/bin/sleep 0.01`（同 astra-4）＋5 條線各一個 keep sleeper"))
  print("| 線數 | 形狀 | 全 daemon 回合／秒 | 每線完成 tick 最少／中位／最多 | 回合間隔 P50／P95／最大 ms | daemon ctl 回條 P50／最大 ms | 任務 kill 回條 P50／最大 ms | 全組 CPU（核，rusage） | 系統 CPU（核） | 批大小 P50／最大（tick） | 批程序 wall P50 ms（tick） |")
  print("|---:|---|---:|---|---|---|---|---:|---:|---|---:|")
  for c in (50,100,200):
    for key in order:
      f="ev/m-%s-k%dp%d-%s-%d.json"%(key[0],key[1],key[2],w,c)
      if not os.path.exists(f): continue
      r=json.load(open(f)); b=r["batch"].get("aos7-tick")
      iv=r["interval_ms"]; tp=r["ticks_per_node"]; dc=r["daemon_ctl_ms"]; tc=r["task_ctl_ms"]
      print("| %d | %s | %s | %s／%s／%s | %s／%s／%s | %s／%s | %s | %s | %s | %s | %s |"%(c,NAMES[key],r["rounds_per_s"],tp["min"],tp["p50"],tp["max"],iv.get("p50"),iv.get("p95"),iv.get("max"),dc.get("p50"),dc.get("max"),
        ("%s／%s"%(tc.get("p50"),tc.get("max"))+("（%d 筆沒回）"%r["task_ctl_unanswered"] if r["task_ctl_unanswered"] else "")) if tc.get("n") else "—",
        r["cpu_cores_rusage"],r["cpu_cores_system"],("%s／%s"%(b["size"]["p50"],b["size"]["max"])) if b else "—",b["ms"]["p50"] if b else "—"))
