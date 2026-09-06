# identity：daemon 時鐘的身份與環境。

identity_make_world() {
  mkdir -p "$1/.aos"
  printf 'env | sort > env.txt\n' > "$1/.aos/inst"
}

identity_wait_env() {
  local path="$1"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -f "$path" ] && return 0
    sleep 0.1
  done
  return 1
}

identity_has() {
  grep -q "^$2=" "$1/env.txt" 2>/dev/null
}

identity_value() {
  sed -n "s/^$2=//p" "$1/env.txt" 2>/dev/null | head -1
}

identity_finish() {
  kill_clocks "$1"
  sleep 0.2
  rm -rf "$2"
}

# 1. 不寫設定時就是乾淨環境；kernel 的普通變數與金鑰不會漏進時鐘。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"interval": 0.1}\n' > "$IDENTITY_TMP/clock.json"
DEEPSEEK_API_KEY=不該看到 IDENTITY_UNKEPT=不該看到 AOS_LLM_DIR="$IDENTITY_TMP/llm" \
  "$DAEMON" register "$IDENTITY_TMP/w" --config "$IDENTITY_TMP/clock.json" \
  --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
DEEPSEEK_API_KEY=不該看到 IDENTITY_UNKEPT=不該看到 AOS_LLM_DIR="$IDENTITY_TMP/llm" \
  "$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
identity_wait_env "$IDENTITY_TMP/w/env.txt" || true
IDENTITY_PATH=$(identity_value "$IDENTITY_TMP/w" PATH)
if ! identity_has "$IDENTITY_TMP/w" DEEPSEEK_API_KEY \
   && ! identity_has "$IDENTITY_TMP/w" IDENTITY_UNKEPT \
   && [ "$(identity_value "$IDENTITY_TMP/w" AOS_DAEMON_DIR)" = "$IDENTITY_AOSD" ] \
   && [ "$(identity_value "$IDENTITY_TMP/w" AOS_LLM_DIR)" = "$IDENTITY_TMP/llm" ] \
   && [ -n "$(identity_value "$IDENTITY_TMP/w" HOME)" ] \
   && [ -n "$(identity_value "$IDENTITY_TMP/w" LANG)" ] \
   && case ":$IDENTITY_PATH:" in *":$HERE:"*) true;; *) false;; esac; then
  ok "identity：legacy_env 預設 false，金鑰不會漏進時鐘"
else
  fail "identity：乾淨環境不對（env=$(cat "$IDENTITY_TMP/w/env.txt" 2>/dev/null)）"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

# 2. config 的 env 會進時鐘；--env K=V 可以重複給，也能蓋同名值。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"legacy_env": false}\n' > "$IDENTITY_AOSD/config.json"
printf '{"env": {"IDENTITY_ONE": "設定檔", "IDENTITY_BASE": "保留"}}\n' \
  > "$IDENTITY_TMP/clock.json"
"$DAEMON" register "$IDENTITY_TMP/w" --config "$IDENTITY_TMP/clock.json" \
  --env IDENTITY_ONE=命令列 --env IDENTITY_TWO=二 \
  --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
"$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
identity_wait_env "$IDENTITY_TMP/w/env.txt" || true
if [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_ONE)" = "命令列" ] \
   && [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_BASE)" = "保留" ] \
   && [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_TWO)" = "二" ]; then
  ok "identity：config env 與重複 --env 會合併，命令列蓋同名值"
else
  fail "identity：config env 與 --env 沒正確合併"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

# 3. env_keep 只從 kernel 當下的環境抄指定名字。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"legacy_env": false}\n' > "$IDENTITY_AOSD/config.json"
printf '{"env_keep": ["IDENTITY_KEEP"], "interval": 0.1}\n' > "$IDENTITY_TMP/clock.json"
"$DAEMON" register "$IDENTITY_TMP/w" --config "$IDENTITY_TMP/clock.json" \
  --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
IDENTITY_KEEP=留下來 IDENTITY_DROP=別留下來 \
  "$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
identity_wait_env "$IDENTITY_TMP/w/env.txt" || true
if [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_KEEP)" = "留下來" ] \
   && ! identity_has "$IDENTITY_TMP/w" IDENTITY_DROP; then
  ok "identity：env_keep 只抄指定的 kernel 環境變數"
else
  fail "identity：env_keep 抄錯了"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

# 4. --env-from 讀 600 的 KEY=VALUE 檔；金鑰只給明確指定的鐘。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"legacy_env": false}\n' > "$IDENTITY_AOSD/config.json"
printf 'DEEPSEEK_API_KEY=只給這顆鐘\nIDENTITY_FILE=檔案值\n' > "$IDENTITY_TMP/llm.env"
chmod 600 "$IDENTITY_TMP/llm.env"
"$DAEMON" register "$IDENTITY_TMP/w" --env-from "$IDENTITY_TMP/llm.env" \
  --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
"$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
identity_wait_env "$IDENTITY_TMP/w/env.txt" || true
if [ "$(identity_value "$IDENTITY_TMP/w" DEEPSEEK_API_KEY)" = "只給這顆鐘" ] \
   && [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_FILE)" = "檔案值" ]; then
  ok "identity：env_from 的 600 檔會把金鑰給指定時鐘"
else
  fail "identity：env_from 沒讀進來"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

# 5. env_from 不是 600 就拒絕，錯誤留在 done 請求裡。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"legacy_env": false}\n' > "$IDENTITY_AOSD/config.json"
printf 'DEEPSEEK_API_KEY=太鬆了\n' > "$IDENTITY_TMP/llm.env"
chmod 644 "$IDENTITY_TMP/llm.env"
"$DAEMON" register "$IDENTITY_TMP/w" --env-from "$IDENTITY_TMP/llm.env" \
  --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
"$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
if [ ! -f "$IDENTITY_AOSD/clocks/$(clock_id "$IDENTITY_TMP/w").json" ] \
   && case "$(last_result "$IDENTITY_AOSD")" in fail\|*"權限要是 600"*) true;; *) false;; esac; then
  ok "identity：env_from 不是 600 會拒絕並記清楚錯誤"
else
  fail "identity：644 的 env_from 沒被拒絕（$(last_result "$IDENTITY_AOSD")）"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

# 6. legacy_env=true 保留舊行為：kernel 的整包環境照舊交給時鐘。
IDENTITY_TMP=$(mktemp -d); IDENTITY_AOSD="$IDENTITY_TMP/aosd"
identity_make_world "$IDENTITY_TMP/w"; mkdir -p "$IDENTITY_AOSD"
printf '{"legacy_env": true}\n' > "$IDENTITY_AOSD/config.json"
"$DAEMON" register "$IDENTITY_TMP/w" --daemon "$IDENTITY_AOSD" >/dev/null 2>&1
DEEPSEEK_API_KEY=相容模式看得到 IDENTITY_LEGACY=整包留下 \
  "$DKERNEL" tick "$IDENTITY_AOSD" >/dev/null 2>&1
identity_wait_env "$IDENTITY_TMP/w/env.txt" || true
if [ "$(identity_value "$IDENTITY_TMP/w" DEEPSEEK_API_KEY)" = "相容模式看得到" ] \
   && [ "$(identity_value "$IDENTITY_TMP/w" IDENTITY_LEGACY)" = "整包留下" ]; then
  ok "identity：legacy_env=true 仍把 kernel 整包環境交給時鐘"
else
  fail "identity：legacy_env=true 沒保留舊行為"
fi
identity_finish "$IDENTITY_AOSD" "$IDENTITY_TMP"

unset IDENTITY_TMP IDENTITY_AOSD IDENTITY_PATH
unset -f identity_make_world identity_wait_env identity_has identity_value identity_finish
