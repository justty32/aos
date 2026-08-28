#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
W=$LAB/w-smoke
mkworld "$W"
echo "--- after init ---"
ls -la "$W/.aos"
echo "--- deliver ---"
echo '[{"argv":["/bin/sh","-c","echo hello > out.txt"]}]' | "$AOS" deliver "$W"
echo "rc=$?"
ls -la "$W/.aos/inst.tempd"
echo "--- exec ---"
"$AOS" exec "$W"; echo "rc=$?"
echo "--- after exec ---"
ls -la "$W" "$W/.aos" "$W/.aos/inst.tempd"
cat "$W/out.txt" 2>/dev/null
echo "turn=$(cat "$W/.aos/turn")"
cat "$W/.aos/inst-head.json" 2>/dev/null
