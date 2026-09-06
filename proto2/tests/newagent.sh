# aos-user new 與模板。

test_newagent_template() {
  local root world out rc run_rc missing step
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-template.XXXXXX")
  world="$root/world"
  out=$("$AUSER" new "$world" --template chat 2>&1); rc=$?
  "$AOS" "$world" >/dev/null 2>&1; run_rc=$?
  missing=""
  for f in .aos/inst .gitignore agent/tools.json agent/system-prompt.json \
           agent/prompts.json agent/llm.json; do
    [ -f "$world/$f" ] || missing="$missing $f"
  done
  for d in agent/inbox agent/outbox; do
    [ -d "$world/$d" ] || missing="$missing $d"
  done
  step=$(field "$world/agent/state.json" step)
  if [ "$rc" = 0 ] && [ "$run_rc" = 0 ] && [ -z "$missing" ] && [ "$step" = 1 ] \
     && printf '%s' "$out" | grep -q '建好了：'; then
    ok "newagent：chat 模板建出合法世界，aos-exec 推得動"
  else
    fail "newagent：chat 世界不完整（new=$rc exec=$run_rc step=$step 少=$missing）"
  fi
  rm -rf "$root"
}

test_newagent_packs() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-packs.XXXXXX")
  "$AUSER" new "$root/world" --template chat --packs kids,fs >/dev/null 2>&1
  got=$(python3 -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["packs"]))' \
        "$root/world/agent/tools.json")
  if [ "$got" = "kids,fs" ]; then
    ok "newagent：--packs 覆蓋模板"
  else
    fail "newagent：--packs 沒有覆蓋模板（$got）"
  fi
  rm -rf "$root"
}

test_newagent_persona_file() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-persona.XXXXXX")
  printf '你是檔案裡的人格。\n' > "$root/persona.txt"
  "$AUSER" new "$root/world" --persona-file "$root/persona.txt" >/dev/null 2>&1
  got=$(field "$root/world/agent/system-prompt.json" content)
  if [ "$got" = "你是檔案裡的人格。" ]; then
    ok "newagent：--persona-file 覆蓋人格"
  else
    fail "newagent：人格檔沒有生效（$got）"
  fi
  rm -rf "$root"
}

test_newagent_prompts() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-prompts.XXXXXX")
  printf '[{"role":"user","content":"先做這件事"}]\n' > "$root/start.json"
  "$AUSER" new "$root/world" --prompts "$root/start.json" >/dev/null 2>&1
  got=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d[0]["role"]+":"+d[0]["content"])' \
        "$root/world/agent/prompts.json")
  if [ "$got" = "user:先做這件事" ]; then
    ok "newagent：--prompts 覆蓋起手對話"
  else
    fail "newagent：起手對話沒有生效（$got）"
  fi
  rm -rf "$root"
}

test_newagent_unknown_pack() {
  local root out rc
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-unknown.XXXXXX")
  out=$("$AUSER" new "$root/world" --packs no_such_pack 2>&1); rc=$?
  if [ "$rc" = 2 ] && [ ! -e "$root/world" ] \
     && printf '%s' "$out" | grep -q '認不得的工具包' \
     && printf '%s' "$out" | grep -q '可用的工具包：'; then
    ok "newagent：不認得的包當場報錯並列可用包"
  else
    fail "newagent：不認得的包處理不對（rc=$rc out=$out）"
  fi
  rm -rf "$root"
}

test_newagent_questions() {
  local root out rc got
  root=$(mktemp -d "$TEST_RUN_DIR/newagent-questions.XXXXXX")
  out=$(printf 'chat\nmailbox,self\n你是問答人格\n先等我\ndeepseek-flash\nn\ny\n' | \
        "$AUSER" new "$root/world" 2>&1); rc=$?
  got=$(python3 - "$root/world/agent" <<'PYEOF2'
import json, os, sys
h = sys.argv[1]
p = json.load(open(os.path.join(h, "system-prompt.json"), encoding="utf-8"))["content"]
m = json.load(open(os.path.join(h, "prompts.json"), encoding="utf-8"))[0]["content"]
e = json.load(open(os.path.join(h, "llm.json"), encoding="utf-8"))["engine"]
print("|".join((p, m, e)))
PYEOF2
)
  if [ "$rc" = 0 ] && [ "$got" = "你是問答人格|先等我|deepseek-flash" ] \
     && printf '%s' "$out" | grep -q '將要建這些：'; then
    ok "newagent：沒有旗標時，問答與最後確認能建世界"
  else
    fail "newagent：問答模式不對（rc=$rc got=$got out=$out）"
  fi
  rm -rf "$root"
}

test_newagent_templates_list() {
  local out
  out=$("$AUSER" templates 2>&1)
  if printf '%s' "$out" | grep -q '^chat ' \
     && printf '%s' "$out" | grep -q '^coder ' \
     && printf '%s' "$out" | grep -q '^manager '; then
    ok "newagent：templates 列出三個模板與說明"
  else
    fail "newagent：templates 列表不全（$out）"
  fi
}

test_newagent_packs_list() {
  local out
  out=$("$AUSER" packs 2>&1)
  if printf '%s' "$out" | grep -q '^kids ' \
     && printf '%s' "$out" | grep -q '^mailbox ' \
     && printf '%s' "$out" | grep -q '^self ' \
     && printf '%s' "$out" | grep -q '^fs ' \
     && ! printf '%s' "$out" | grep -q '^shell '; then
    ok "newagent：packs 列出現有工具包與一句說明"
  else
    fail "newagent：packs 列表不全（$out）"
  fi
}

test_newagent_template
test_newagent_packs
test_newagent_persona_file
test_newagent_prompts
test_newagent_unknown_pack
test_newagent_questions
test_newagent_templates_list
test_newagent_packs_list
