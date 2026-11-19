# 測 aos-exec 型 proc 起不來的各種情形（程式不存在、沒執行權、argv 壞、envs 壞、cwd 不存在、exec 失敗）在 daemon 表上與 stderr.txt 怎麼顯示。
source $(dirname $0)/common.sh
R=$RUN/execfail; rm -rf $R; mkdir -p $R/t
cd $R/t
echo "hello" > noexec.txt                                   # 不可執行、不是 JSON
printf "#!/bin/sh\necho hi\n" > nox.sh                      # 腳本但沒 +x
echo "[\"/no/such/prog\"]" > missingprog.json               # argv[0] 不存在
echo "{\"argv\": []}" > emptyargv.json
echo "{\"argv\": [1, 2]}" > numargv.json
echo "{\"argv\": [\"true\"], \"envs\": {\"A\": 5}}" > badenvs.json
echo "{\"argv\": [\"true\"], \"envs\": [\"A=1\"]}" > badenvs2.json
echo "{\"argv\": [\"sh\", \"-c\", \"pwd\"], \"cwd\": \"/no/such/dir\"}" > badcwd.json
echo "{\"argv\": [\"nosuchcmd-xyz\"]}" > nocmd.json
echo "{\"argv\": [\"sh\", \"-c\", \"exit 3\"]}" > exit3.json
echo "{\"argv\": [\"true\"], \"stdout\": \"no/dir/out.txt\"}" > badstdout.json
cd - >/dev/null
start_daemon $R || exit 1
for n in noexec nox missingprog emptyargv numargv badenvs badenvs2 badcwd nocmd exit3 badstdout; do
  f=$(ls $R/t/$n.* | head -1); out=$(ctl $R add --name $n $f 2>&1); [ $? -ne 0 ] && echo "add $n -> $out"
done
ctl $R add --name nofile $R/t/does-not-exist.json 2>&1 | sed "s/^/add nofile -> /"
sleep 2
ctl $R ls
echo "== rows"
python3 - $R <<"P"
import json,sys,os
d=json.load(open(sys.argv[1]+"/stack/procs_state.json"))
for n,r in d["procs"].items():
    st=os.path.join(r.get("stack",""),"stderr.txt")
    err=open(st).read().strip().splitlines()[-1:] if os.path.exists(st) else ["(no stderr.txt)"]
    print(n, r.get("phase"), "code=",r.get("code"), "reason=",r.get("reason"), "| stderr:", err)
P
stop_daemon $R
