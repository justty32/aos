#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

# 情境：第一輪正常發布 → 手動改壞 header → 把同名同內容投遞放回去（模擬「發布成功
# 但沒刪投遞」的殘留）→ 看去重還認不認得（誤判＝重複執行，或吃掉新投遞）
hcase() {
  local tag="$1"; local hdr="$2"
  W=$LAB/w13-$tag; mkworld "$W"
  cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo R >> $W/log"]}]
EOF
  timeout 10 "$AOS" exec "$W" >/dev/null 2>&1
  local before="$(cat "$W/.aos/inst-head.json")"
  printf '%s' "$hdr" > "$W/.aos/inst-head.json"
  cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo R >> $W/log"]}]
EOF
  echo "--- $tag: header 被改成 [$(head -c 90 "$W/.aos/inst-head.json" | tr -d '\n')] ---"
  timeout 10 "$AOS" exec "$W" 2>&1 | sed 's/^/    /'
  local n=$(wc -l < "$W/log")
  echo "    執行次數=$n （1=去重生效／2=重複執行）  inbox=[$(ls -A "$W/.aos/inst.tempd")]"
  echo "    header 現在: $(cat "$W/.aos/inst-head.json")"
}

echo "############ 13 inst-head.json 損壞 ############"
GOOD='{"version":1,"id":"0000000000000000","origin":"aggregated","result":null}'
hcase truncate  '{"version":1,"id":"abc'
hcase idchanged '{"version":1,"id":"deadbeefdeadbeef","origin":"aggregated","result":null}'
hcase idnumber  '{"version":1,"id":12345,"origin":"aggregated","result":null}'
hcase idnull    '{"version":1,"id":null,"origin":"aggregated","result":null}'
hcase idempty   '{"version":1,"id":"","origin":"aggregated","result":null}'
hcase garbage   $'\x00\x01\x02\xff\xfe rubbish'
hcase emptyfile ''
hcase idinvalue '{"version":1,"origin":"the \"id\" of a batch","id":"REPLACE","result":null}'
hcase noid      '{"version":1,"origin":"aggregated","result":null}'
hcase deleted   'DELETE_ME'
