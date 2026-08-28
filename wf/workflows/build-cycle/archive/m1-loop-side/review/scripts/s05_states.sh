. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
PROBE="$S/probe"
LOG="$S/ran.log"

mkinst() { # $1 = tag  -> stdout: 一筆 instruction 的 JSON 陣列
  printf '[{"argv":["/bin/sh","-c","echo %s >> %s"]}]\n' "$1" "$LOG"
}

fresh() { # $1 = world dir
  rm -rf "$1"; mkdir -p "$1"; "$AOS" init "$1" >/dev/null || exit 1
  : > "$LOG"
}

show() { # $1 = world
  echo "  -- files:"; (cd "$1/.aos" && ls -A | sed 's/^/     /')
  echo "  -- inbox:"; (cd "$1/.aos/inst.tempd" && ls -A | sed 's/^/     /')
  echo "  -- head:  $(cat "$1/.aos/inst-head.json" 2>/dev/null)"
  echo "  -- turn:  $(cat "$1/.aos/turn" 2>/dev/null)"
  echo "  -- ran.log: [$(tr '\n' ',' < "$LOG")]"
}

echo "#################### 案例 C：崩在 header rename 與批 rename 之間（roll-forward）"
W="$S/wc"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
cp "$W/.aos/inst.tempd/1000-0.json" "$S/D1.json"
"$PROBE" aggregate "$W/.aos/inst.json"
cp "$W/.aos/inst.json" "$S/published1.json"
# 手工回捲成崩潰狀態：header 已是新 id、批退回 .temp、投遞還在收件匣
mv "$W/.aos/inst.json" "$W/.aos/inst.json.temp"
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec rc=$?"
show "$W"

echo
echo "#################### 案例 D：崩在批 rename 與刪投遞之間（無新投遞）"
W="$S/wd"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$PROBE" aggregate "$W/.aos/inst.json" >/dev/null
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"   # 投遞復活
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec#1 rc=$?"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
show "$W"

echo
echo "#################### 案例 E：崩在批 rename 與刪投遞之間 ＋ 期間有新投遞到達"
W="$S/we"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$PROBE" aggregate "$W/.aos/inst.json" >/dev/null
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"   # 投遞復活
mkinst B > "$W/.aos/inst.tempd/2000-0.json"        # 新投遞到達
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec#1 rc=$?"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
"$AOS" exec "$W"; echo "  exec#3 rc=$?"
show "$W"

echo
echo "#################### 案例 K：刪投遞刪到一半就崩（部分殘留）"
W="$S/wk"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
mkinst B > "$W/.aos/inst.tempd/2000-0.json"
cp "$W/.aos/inst.tempd/2000-0.json" "$S/D2.json"
"$PROBE" aggregate "$W/.aos/inst.json" >/dev/null
cp "$S/D2.json" "$W/.aos/inst.tempd/2000-0.json"   # 只有第二份沒刪成功
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec#1 rc=$?"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
"$AOS" exec "$W"; echo "  exec#3 rc=$?"
show "$W"

echo
echo "#################### 案例 H：claim 的 rename(base→runi) 沒 fsync，崩潰後復活"
W="$S/wh"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W"; echo "  exec#1 rc=$? （正常一回合）"
show "$W"
cp "$S/published1.json" "$W/.aos/inst.json"        # rename 沒落盤 → inst.json 復活
echo "  [佈置完成：inst.json 復活、.runi 不存在、投遞已刪、header 仍是這一批的 id]"
show "$W"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
show "$W"

echo
echo "#################### 案例 I：release 的 unlink 沒 fsync，崩潰後 .runi 復活"
W="$S/wi"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W" >/dev/null; echo "  exec#1 rc=$?"
cp "$S/published1.json" "$W/.aos/inst.json.runi"   # unlink 沒落盤 → .runi 復活
echo "  [佈置完成]"; show "$W"
mkinst B > "$W/.aos/inst.tempd/2000-0.json"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
"$AOS" exec "$W"; echo "  exec#3 rc=$?"
show "$W"

echo
echo "#################### 案例 J：同名同內容的**新**批被去重誤殺（丟批）"
W="$S/wj"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W"; echo "  exec#1 rc=$?"
show "$W"
echo "  [第二次：完全獨立的新請求，只是 pid 被重用、內容一樣]"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
show "$W"

echo
echo "#################### 案例 G：header id 對得上，但 .temp 裡是別批"
W="$S/wg"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$PROBE" aggregate "$W/.aos/inst.json" >/dev/null
rm -f "$W/.aos/inst.json"
mkinst EVIL > "$W/.aos/inst.json.temp"             # .temp 是別批的殘骸
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec rc=$?"
show "$W"
