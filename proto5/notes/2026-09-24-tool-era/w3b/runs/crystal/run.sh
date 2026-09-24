# T-crystal 對照：訓練組跑完之後（train.py），機械版一次＋模型版三次，各拿測試組評（eval.py）。
# 用法：. ~/tmp/w3b-crystal/env.sh; export AOS_LLM_CONFIG=$W/llm.json; bash run.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/out
mkdir -p $OUT
cp $AOS_TEAM_HOME/team/route.log $OUT/route.log
python3 $HERE/timeit.py $OUT/mech-time.json -- aos-team crystal --json --out $OUT/mech.json > $OUT/mech-report.json
aos-team crystal --out $OUT/mech-text.json > $OUT/mech-report.txt
for i in 1 2 3; do
  python3 $HERE/timeit.py $OUT/llm-$i-time.json -- aos-team crystal --suggest-with-llm --json --out $OUT/llm-$i.json \
    > $OUT/llm-$i-report.json
done
cd $HERE
python3 eval.py - $OUT/mech.json $OUT/llm-1.json $OUT/llm-2.json $OUT/llm-3.json
