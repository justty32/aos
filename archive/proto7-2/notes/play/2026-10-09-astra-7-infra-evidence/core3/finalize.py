"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/finalize.py

Read-only final process/worktree audit, writes only core3 evidence reports.
Does not signal processes or remove directories.
"""
import sys
sys.dont_write_bytecode = True
from common import *
import re
import hashlib

scoped()
records=[]
for p in sorted(HERE.glob('*.json')):
    v=read(p,{})
    if isinstance(v,dict) and 'scenario' in v:
        records.append((p,v))
roots=[v['root'] for _,v in records]
residue=[]
unreadable=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
    try:
        env=(proc/'environ').read_bytes().split(b'\0')
    except (FileNotFoundError,ProcessLookupError):continue
    except PermissionError:
        unreadable.append(int(proc.name));continue
    matches=[r for r in roots if any(e==('AOS7_ROOT='+r).encode() or e.startswith(('AOS7_ROOT='+r+'/').encode()) for e in env)]
    if matches:
        residue.append({'identity':ident(int(proc.name)),'roots':matches})
namespace_paths=[str(p) for p in Path('/tmp').glob('astra7-core3-*')]
tmp_left=[r for r in roots if Path(r).exists()]
tracked=subprocess.run(['git','diff','--exit-code','HEAD','--'],capture_output=True,text=True,cwd=REPO)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
(HERE/'ps-final.txt').write_bytes(subprocess.check_output(['ps','-eo','pid,ppid,pgid,lstart,args']))
cleanup={'scenario_count':len(records),'head':head,'owned_root_count':len(set(roots)),
         'remaining_owned_processes':residue,'remaining_core3_tmp_roots':tmp_left,
         'unowned_namespace_paths_preserved':[p for p in namespace_paths if p not in roots],
         'every_case_cleanup_clean':all(not v['cleanup']['remaining'] and v['cleanup']['tmp_removed'] for _,v in records),
         'tracked_diff_exit_code':tracked.returncode,'tracked_diff':tracked.stdout,
         'process_scan_scope':'AOS7_ROOT exact or beneath every recorded own root; inaccessible other-user environ skipped',
         'other_user_environ_unreadable_count':len(unreadable),
         'ps_before':'ps-before.txt','ps_final':'ps-final.txt',
         'snapshot_excludes_as_residue':'current finalizer and its systemd-run scope exit after this audit',
         'pass':not residue and not tmp_left and tracked.returncode==0}
write(HERE/'cleanup.json',cleanup)
write(HERE/'results-index.json',{'head':head,'cases':[{'scenario':v['scenario'],'pass':v['pass'],
      'result':p.name,'snapshot':v['snapshot_archive'],'assertions':len(v['assertions']),
      'failed':[a['assertion'] for a in v['assertions'] if not a['pass']],
      **({'observation':v['observation']} if 'observation' in v else {})} for p,v in records]})
findings={'findings':[{'id':'NEW-core3-1','classification':'B','severity':'低',
 'title':'重起 daemon 後尚未完成的 node 回收顯示 idle，未保留 missing',
 'contract':['proto7-2/spec.md:95','proto7-2/spec.md:97','proto7-2/notes/component-contracts.md §2.1'],
 'reproduction':'python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/new_core3_1.py',
 'steps':['真 daemon 起 keep 任務，ready 且 timeline running',
          '對該任務 /proc/<pid>/stat 注入 EIO；搬走 node 並放同 id 新目錄',
          '確認 missing 與持久化 reaping 後 SIGKILL daemon',
          '同 root 重起並維持 EIO；40 次連續樣本全為 idle，reaping 仍在、旧任務仍活、無新 round',
          '撤 EIO，確認舊任務已死才新任務 ready'],
 'observed':'初次邊角案＋三次獨立確認均成立；各確認 40/40 為 idle',
 'impact':'status 使用者將回收阻塞看成閒置；實測未雙開、無漏收，故障撤除後恢復正常',
 'cause':'load_state 只恢復 reaping，未恢復 missing；check_nodes 遇 reaping 直接 continue；write_status 無時間線且不在 missing 就報 idle',
 'implementation':['proto7-2/lib/aos7_daemon.py:142','proto7-2/lib/aos7_daemon.py:516','proto7-2/lib/aos7_daemon.py:639'],
 'suggestion':'由已登記且仍有 reaping 義務的狀態推導 missing，直到確認收乾淨才解除',
 'known_limit_relation':'不是 daemon 停機時才替換 node 的已知限制：替換及 missing/reaping 均在舊 daemon 活著時已確認',
 'evidence':['edge-restart-unknown.json','new-core3-1-confirm-1.json','new-core3-1-confirm-2.json','new-core3-1-confirm-3.json'],
 'fixed':False}]}
write(HERE/'findings.json',findings)
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='manifest.json'}
write(HERE/'manifest.json',manifest)
print(json.dumps({'cleanup':cleanup,'case_count':len(records),'failed_cases':[v['scenario'] for _,v in records if not v['pass']],
                  'max_file_bytes':max(v['bytes'] for v in manifest.values())},ensure_ascii=False))
if not cleanup['pass']:raise SystemExit(1)
