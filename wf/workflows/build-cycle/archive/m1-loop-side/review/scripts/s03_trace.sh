. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
cd "$S" || exit 1
gcc -shared -fPIC -O0 -o fstrace.so fstrace.c -ldl || exit 1
echo "built"

W="$S/w1"
rm -rf "$W" ; mkdir -p "$W"
rm -f "$S/trace.log"

export FSTRACE_LOG="$S/trace.log"
export FSTRACE_FILTER=".aos"

echo "=== aos init ==="
LD_PRELOAD="$S/fstrace.so" "$AOS" init "$W"

cat > "$S/batch.json" <<'EOF'
[{"argv":["/bin/sh","-c","echo RAN >> /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/ran.log"]}]
EOF
rm -f "$S/ran.log"

echo "=== aos deliver ==="
LD_PRELOAD="$S/fstrace.so" "$AOS" deliver "$W" -f "$S/batch.json"

echo "=== aos exec ==="
LD_PRELOAD="$S/fstrace.so" "$AOS" exec "$W"
echo "exec rc=$?"

echo "=== ran.log ==="
cat "$S/ran.log"
echo "=== world ==="
find "$W" | sort
echo "=== header ==="
cat "$W/.aos/inst-head.json" 2>/dev/null
echo "=== turn ==="
cat "$W/.aos/turn"
