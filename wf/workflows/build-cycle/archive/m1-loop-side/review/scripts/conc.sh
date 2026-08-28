#!/bin/bash
# conc.sh — aos 併發彙整「重複執行率」基準線量測（重現審查報告 t9b.sh 的 19%）
#
# 量的東西（照報告的定義）：
#   一回合 = 全新世界 + 恰好一批投遞 + WORKERS 支併發 `aos exec` + 跑完 drain。
#   若「這一輪投遞的批」最後總共被執行超過一次 → 這回合算重複。
#   DUP_PCT = 重複回合數 / 總回合數。
#
# 為什麼一定要 drain：重複不是在併發期間發生的。A、B 各自發布一次，A 先 claim
# 執行，B 撞 .runi 回 3，B 那份重複的 inst.json 留在原地 —— 下一次 exec 才會把它
# 再跑一遍。只看併發期間會量到 0%，誤判成沒事。
#
# 用法：
#   AOS=/path/to/aos LAB=/path/to/lab ./conc.sh [ROUNDS] [WORKERS]
#   環境變數（都可覆寫）：
#     AOS          aos 執行檔（預設：主 repo 的 build/bin/aos，同 env.sh）
#     LAB          實驗場地（預設 /tmp/aos-conc-lab-$USER）；會被清空重建
#     ROUNDS       回合數（預設 200）
#     WORKERS      併發 exec 支數（預設 2）
#     BATCH        每回合投遞幾份（預設 1）
#     DELIVER_MODE direct（直接寫進 inbox，等同 t9b）｜cli（走 aos deliver）。預設 direct
#     DRAIN_MAX    drain 階段再跑幾次 exec（預設 5，無條件跑滿）
#     EXEC_TIMEOUT 單支 exec 的 timeout 秒數（預設 30，0 = 不設）
#     KEEP_LAB     1 = 結束後保留實驗場地（預設 1）
#
# 相依：bash、coreutils、grep/sed/awk、timeout。不需要 strace/ltrace/python。

set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}"
LAB="${LAB:-/tmp/aos-conc-lab-${USER:-u}}"
ROUNDS="${1:-${ROUNDS:-200}}"
WORKERS="${2:-${WORKERS:-2}}"
BATCH="${BATCH:-1}"
DELIVER_MODE="${DELIVER_MODE:-direct}"
DRAIN_MAX="${DRAIN_MAX:-5}"
EXEC_TIMEOUT="${EXEC_TIMEOUT:-30}"
KEEP_LAB="${KEEP_LAB:-1}"

if [ ! -x "$AOS" ]; then
  echo "conc.sh: 找不到可執行的 aos：$AOS" >&2
  echo "         用 AOS=/path/to/aos 覆寫。" >&2
  exit 2
fi

# --- 實驗場地：每次跑之前清乾淨 -------------------------------------------
rm -rf "$LAB"
mkdir -p "$LAB" || { echo "conc.sh: 建不出 LAB=$LAB" >&2; exit 2; }
W="$LAB/world"
OUT="$LAB/out"          # 每支 worker 的 stdout/stderr
ERRALL="$LAB/stderr.txt"
DETAIL="$LAB/detail.txt"
mkdir -p "$OUT"
: > "$ERRALL"; : > "$DETAIL"

RUN=""
if [ "$EXEC_TIMEOUT" != "0" ]; then RUN="timeout ${EXEC_TIMEOUT}"; fi

mkworld() {
  rm -rf "$W"
  mkdir -p "$W"
  "$AOS" init "$W" >/dev/null 2>&1 || echo "INIT_FAIL round=$1" >> "$ERRALL"
}

# 一份投遞 = 一條會把唯一 token append 進 run.log 的指令
put_delivery() {  # $1=round $2=seq $3=token
  local r="$1" s="$2" tok="$3"
  local body='[{"argv":["/bin/sh","-c","echo '"$tok"' >> '"$LOG"'"]}]'
  if [ "$DELIVER_MODE" = "cli" ]; then
    printf '%s\n' "$body" | "$AOS" deliver "$W" >/dev/null 2>>"$ERRALL"
  else
    printf '%s\n' "$body" > "$W/.aos/inst.tempd/$((100000 + r * 100 + s))-0.json"
  fi
}

# 這一輪的 token 在 run.log 裡出現幾次 = 這一輪的批被執行幾次。
# 注意：grep -c 沒命中時印 0 但回 exit 1，不能寫成 `grep -c ... || echo 0`
# （那會印出兩行 0，後面的 $(( )) 會炸掉整支腳本）。
count_tok() {
  local n
  n=$(grep -c -- "^$TOK\$" "$LOG" 2>/dev/null)
  case "$n" in ''|*[!0-9]*) n=0 ;; esac
  echo "$n"
}

# 用 bash glob 數，不 fork（fork 會改變下一回合開跑時的機器狀態，
# 實測會壓低量到的重複率）。
shopt -s nullglob
count_suffix() {  # $1=dir $2=後綴  → 印出數量
  local f n=0
  for f in "$1"/*"$2"; do n=$((n + 1)); done
  echo "$n"
}

DELIVERED=0
EXECUTED=0
DUP_ROUNDS=0
LOST=0
CONC_DUP=0        # 只看併發期間就已經跑超過一次的回合（報告量到 0）
RESIDUE_INST=0    # 併發結束、drain 之前殘留 .aos/inst.json 的回合數（報告 29/200）
RESIDUE_RUNI=0
RESIDUE_TEMP=0
RESIDUE_BAD=0
RESIDUE_INBOX=0
RESIDUE_INST_AFTER=0   # drain 之後仍殘留 inst.json 的回合數（.runi 卡住時會有）
TURN_SUM=0
TURN_LAST=0
RC3=0             # 併發期間有 worker 回 3（撞 .runi）的回合數
RENAME_FAILED=0   # stderr 裡 RenameFailed 的總次數（修補前 ext4 每回合都有）

START=$(date +%s)

for r in $(seq 1 "$ROUNDS"); do
  mkworld "$r"
  LOG="$W/run.log"; : > "$LOG"
  TOK="R${r}X"

  for s in $(seq 1 "$BATCH"); do
    put_delivery "$r" "$s" "$TOK"
    DELIVERED=$((DELIVERED + 1))
  done

  # --- 併發階段 ---
  # 這一行的形狀會影響量到的重複率，不要「順手」改。subshell 裡只能有一個
  # simple command：多一個指令（例如 `; echo $? > rc`）bash 就得多 fork 一層，
  # 兩支 worker 反而更同步，雙方互踩同一個固定名 .temp，只有一份活下來 ——
  # 實測重複率會從 ~11% 掉到 ~5%。rc=3 改用 stderr 文字判定，不要用 $?。
  for k in $(seq 1 "$WORKERS"); do
    ( $RUN "$AOS" exec "$W" > "$OUT/w$k.txt" 2>&1 ) &
  done
  wait

  conc=$(count_tok)
  cat "$OUT"/w*.txt >> "$ERRALL" 2>/dev/null
  if grep -ql 'runi already exists' "$OUT"/w*.txt 2>/dev/null; then RC3=$((RC3 + 1)); fi

  # --- C：併發結束當下的 inst.json 殘留（重複的真正載體）---
  [ -e "$W/.aos/inst.json" ] && RESIDUE_INST=$((RESIDUE_INST + 1))

  # --- drain：把世界跑乾淨（無條件跑 DRAIN_MAX 次，同 t9b）---
  # 不做「還有沒有事做」的前置檢查：那些檢查會 fork，改變下一回合開跑時的
  # 機器狀態，實測會把量到的重複率壓低約一半。exec 對空世界是 no-op，很便宜。
  for d in $(seq 1 "$DRAIN_MAX"); do
    $RUN "$AOS" exec "$W" >> "$ERRALL" 2>&1
  done

  tot=$(count_tok)
  EXECUTED=$((EXECUTED + tot))
  [ "$conc" -gt "$BATCH" ] && CONC_DUP=$((CONC_DUP + 1))
  if [ "$tot" -gt "$BATCH" ]; then
    DUP_ROUNDS=$((DUP_ROUNDS + 1))
    echo "round $r: 併發階段 $conc 次，drain 後總共 $tot 次" >> "$DETAIL"
  fi
  [ "$tot" -lt "$BATCH" ] && LOST=$((LOST + BATCH - tot))

  # --- drain 後的殘留 ---
  [ -e "$W/.aos/inst.json.runi" ] && RESIDUE_RUNI=$((RESIDUE_RUNI + 1))
  [ -e "$W/.aos/inst.json" ]      && RESIDUE_INST_AFTER=$((RESIDUE_INST_AFTER + 1))
  t=$(count_suffix "$W/.aos" ".temp");            RESIDUE_TEMP=$((RESIDUE_TEMP + t))
  b=$(count_suffix "$W/.aos/inst.tempd" ".bad");  RESIDUE_BAD=$((RESIDUE_BAD + b))
  i=$(count_suffix "$W/.aos/inst.tempd" ".json"); RESIDUE_INBOX=$((RESIDUE_INBOX + i))

  if [ -f "$W/.aos/turn" ]; then
    tv=$(tr -dc '0-9' < "$W/.aos/turn")
    [ -n "$tv" ] && { TURN_SUM=$((TURN_SUM + tv)); TURN_LAST="$tv"; }
  fi
done

END=$(date +%s)
DUR=$((END - START))

# RenameFailed：修補前批發布走共用固定 `.temp`，ext4 上每回合都有輸家撲空。
# 修補後發布直接以每行程唯一的 `.temp` 為來源、且排他，輸家拿 EEXIST 靜默放棄，
# 這個數字應該歸零。
RENAME_FAILED=$(grep -c 'RenameFailed' "$ERRALL" 2>/dev/null)
case "$RENAME_FAILED" in ''|*[!0-9]*) RENAME_FAILED=0 ;; esac

DUP_PCT=$(awk -v a="$DUP_ROUNDS" -v b="$ROUNDS" 'BEGIN{ if (b==0) print "0.0"; else printf "%.1f", a*100.0/b }')
RES_INST_PCT=$(awk -v a="$RESIDUE_INST" -v b="$ROUNDS" 'BEGIN{ if (b==0) print "0.0"; else printf "%.1f", a*100.0/b }')

echo
echo "== conc.sh：$WORKERS 支併發 exec × $ROUNDS 回合（每回合新世界、$BATCH 份投遞、跑完 drain）=="
echo "  AOS            : $AOS"
echo "  LAB            : $LAB   （$(df -PT "$LAB" 2>/dev/null | awk 'NR==2{print $2}')）"
echo "  投遞方式        : $DELIVER_MODE"
echo "  耗時            : ${DUR}s"
echo "  併發階段就跑超過一次 : $CONC_DUP / $ROUNDS"
echo "  drain 後總共超過一次 : $DUP_ROUNDS / $ROUNDS  ← 真正的重複執行率 ${DUP_PCT}%"
echo "  完全沒跑（遺失）     : $LOST"
echo "  併發後殘留 inst.json : $RESIDUE_INST / $ROUNDS  (${RES_INST_PCT}%)  ← 重複的載體"
echo "  併發期間有人回 rc=3  : $RC3 / $ROUNDS"
echo "  stderr 的 RenameFailed : $RENAME_FAILED 次"
echo "  drain 後殘留 .runi   : $RESIDUE_RUNI ；.temp : $RESIDUE_TEMP ；.bad : $RESIDUE_BAD ；inbox .json : $RESIDUE_INBOX ；inst.json : $RESIDUE_INST_AFTER"
echo "  turn（最後一回合 / 全部加總）: $TURN_LAST / $TURN_SUM"
echo "  stderr 統計（前 10）:"
sed "s#${LAB}#<LAB>#g; s/[0-9]\{3,\}/<N>/g" "$ERRALL" 2>/dev/null | sort | uniq -c | sort -rn | head -10 | sed 's/^/    /'
echo "  重複明細（前 8 行）:"; head -8 "$DETAIL" 2>/dev/null | sed 's/^/    /'
echo

# 機器可讀摘要
echo "ROUNDS=$ROUNDS WORKERS=$WORKERS BATCH=$BATCH MODE=$DELIVER_MODE DELIVERED=$DELIVERED EXECUTED=$EXECUTED DUP_ROUNDS=$DUP_ROUNDS DUP_PCT=$DUP_PCT CONC_DUP=$CONC_DUP LOST=$LOST RESIDUE_INST=$RESIDUE_INST RESIDUE_RUNI=$RESIDUE_RUNI RESIDUE_TEMP=$RESIDUE_TEMP RESIDUE_BAD=$RESIDUE_BAD RESIDUE_INBOX=$RESIDUE_INBOX RESIDUE_INST_AFTER=$RESIDUE_INST_AFTER RC3=$RC3 RENAME_FAILED=$RENAME_FAILED TURN=$TURN_LAST TURN_SUM=$TURN_SUM SECS=$DUR"

if [ "$KEEP_LAB" != "1" ]; then rm -rf "$LAB"; fi
