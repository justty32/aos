順序（都在 ~/.aos/scratch/aos-base-audit-1119/e-upper 下跑）：
  ../bin/clean bash repro/up.sh        # 起暫存樹（根＋llm kernel，假腦）
  ../bin/clean bash repro/mkdefs.sh    # 建 defs/d1、defs/d4
  e1 需要 a1 不必在跑；其他腳本自己 add／rm 各自的 agent：
  ../bin/clean python3 repro/e1_regen_race.py 80
  ../bin/clean bash repro/e2_fsm_rename.sh
  ../bin/clean bash repro/e3_shared_def.sh      # 先 ctl add -n a1 -w . defs/d1
  HOLD=60 ../bin/clean python3 repro/e4_long_hold.py
  ../bin/clean bash repro/e5_setdef_old_tools.sh
  ../bin/clean python3 repro/e6_watcher_target_life.py
  ../bin/clean bash repro/e7_own_copy_orphaned.sh
  ../bin/clean python3 repro/e8_setdef_while_held.py
  ../bin/clean python3 repro/e9_regen_between_think_and_act.py
  ../bin/clean python3 repro/e10_regen_drops_hooks.py
  ../bin/clean bash repro/down.sh      # 收樹
