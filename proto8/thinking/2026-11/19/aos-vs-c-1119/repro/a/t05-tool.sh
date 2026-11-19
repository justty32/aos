#!/bin/bash
# t05: tool.py (tool_spec) as a compiler: repro, errors, header/impl drift
source ~/.aos/scratch/aos-vs-c-1119/env.sh
T=$HOME/.aos/scratch/aos-vs-c-1119/probe-a/w05; mkdir -p $T
new() { [ -e $T/$1 ] || cp -r $AOS_HOME/templates/tool-python $T/$1; }
for n in rep syn typ def drift failscan; do new $n; done
echo "== repro: compile twice, other AOS_HOME spelling"
cd $T/rep; python3 tool.py --compile >/dev/null; a=$(cat _tooldef.json _metainfo.json | sha256sum); python3 tool.py --compile >/dev/null; b=$(cat _tooldef.json _metainfo.json | sha256sum)
ln -sfn $AOS_HOME $T/otherhome; c=$(AOS_HOME=$T/otherhome python3 tool.py --dry-run | sha256sum); d=$(python3 tool.py --dry-run | sha256sum)
[ "$a" = "$b" ] && echo "twice: identical"; [ "$c" = "$d" ] && echo "other home: identical"
git diff --no-index --stat $AOS_HOME/templates/tool-python/_tooldef.json _tooldef.json && echo "same as shipped _tooldef.json"
echo "== syntax error"; cd $T/syn; sed -i "s/^def run(args):/def run(args)/" tool.py; python3 tool.py --compile 2>&1 | tail -3
echo "== type typo int"; cd $T/typ; sed -i "s/ts.param(\"a\", \"number\"/ts.param(\"a\", \"int\"/" tool.py; python3 tool.py --compile 2>&1 | tail -2; echo "exit ${PIPESTATUS[0]}"
echo "== default wrong type"; cd $T/def; sed -i "s/ts.param(\"b\", \"number\", \"the second number\")/ts.param(\"b\", \"number\", \"the second number\", default=\"x\")/" tool.py; python3 tool.py --compile 2>&1 | tail -2
echo "== header/impl drift: compile, then add required param c in tool.py, do not recompile"
cd $T/drift; python3 tool.py --compile >/dev/null
sed -i "s/^    ts.param(\"b\", \"number\", \"the second number\"),/    ts.param(\"b\", \"number\", \"the second number\"),\n    ts.param(\"c\", \"number\", \"a third number\"),/" tool.py
echo "-- _tooldef.json (what the model sees) params: $(python3 -c "import json;print(sorted(json.load(open(\"_tooldef.json\"))[\"parameters\"][\"properties\"]))")"
echo "-- call with the args the header promises:"; echo "{\"a\": 2, \"b\": 3}" | python3 tool.py; echo "exit $?"
echo "-- aos-tools get (from _tooldef.json):"; aos-tools --file /dev/null get $T/drift 2>&1 | head -3
echo "== fail() codes are found by scanning source text"
cd $T/failscan; cat >> tool.py.tmp <<PY
PY
python3 - <<PY
p="$T/failscan/tool.py"; s=open(p).read()
s=s.replace("    return args[\"a\"] + args[\"b\"]", "    # ts.fail(\"OnlyInComment\", \"x\")\n    code = \"Built\" + \"Dynamically\"\n    if args[\"a\"] < 0: ts.fail(code, \"neg\")\n    return args[\"a\"] + args[\"b\"]")
open(p,"w").write(s)
PY
rm -f tool.py.tmp; python3 tool.py --dry-run | python3 -c "import json,sys; print(json.load(sys.stdin)[\"_tooldef.json\"][\"errors\"])"
echo "{\"a\": -1, \"b\": 1}" | python3 tool.py; echo "exit $?"
