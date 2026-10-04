#!/usr/bin/env python3
"""astra-4 靜態契約核對：只寫自己的 evidence，不改受測文件。"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / 'wf/tools'))
from tabledb import Table


def line(path, n):
    raw = (REPO / path).read_text().splitlines()[n - 1]
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '[%s](%s)' % (
        m[1], m[2] if '://' in m[2] else os.path.relpath((REPO/path).parent/m[2], HERE)), raw)


core = 'proto7-2/notes/component-contracts.md'
spec = 'proto7-2/spec.md'
rows = []


def add(id_, claim, card_line, spec_sections, spec_lines, note='對得上'):
    rows.append(dict(id=id_, claim=claim, card=f'{core}:{card_line}',
                     card_text=line(core, card_line), spec_sections=spec_sections,
                     spec_evidence=[dict(location=f'{spec}:{n}', text=line(spec, n)) for n in spec_lines],
                     result=note))


add('2.1-a', '只跑登記 node、一 node 一時間線', 50, '1、2.1', [26, 37])
add('2.1-b', '路徑登記檢查與 O_NOFOLLOW', 50, '1、2.5', [27, 28, 89])
add('2.1-c', 'missing 與 I/O、proc 未知時保留', 50, '0、2.6', [18, 94, 95, 97])
add('2.1-d', 'SIGTERM stop+kill、守門檔', 50, '2.7（SIGTERM 同見 2.3）', [74, 101, 102])
add('2.1-e', 'status 最終 stopped', 50, '2.8', [106, 116])
add('2.1-f', '重開 gen+1、自有檔讀不到拒開', 50, '2.5', [85])
add('2.1-g', '清已死寫者暫存檔', 50, '0', [19])
add('2.2-a', '動作互斥、世代', 57, '2.5', [86])
add('2.2-b', '回合未知退避、不開下回', 57, '2.2', [51, 52])
add('2.2-c', 'tock 補一次、非0/3失敗不扣回合', 57, '2.1', [43, 46])
add('2.2-d', '逾時與舊動作接管', 57, '2.5', [87, 88])
add('2.2-e', 'pause、owner 各自 rounds', 57, '2.4', [78, 79, 80])
add('2.2-f', 'wake/resume、例外0.5秒', 57, '2.1', [42, 44, 47])
add('2.3-a', '只在確定已關後開', 65, '3', [123, 124])
add('2.3-b', '單槽一次、只空/結束、reaped', 66, '5.3、5.4、4.2', [158, 159, 214, 224, 227])
add('2.3-c', '壞單項跳過、表未知或鎖逾時不起', 67, '4.1、4.2', [146, 148, 157])
add('2.3-d', 'once 最多一次、birth先於移項', 68, '4.4', [170, 172, 173, 174, 176, 180])
add('2.3-e', '加掛 U 保留、B 拒收', 69, '0、4.5', [11, 12, 186, 187])
add('2.3-f', '未知槽不起不lost、tick不刪槽', 70, '5.4、5.1', [205, 225, 233])
add('2.4-a', '先總結讀回確認才通知', 78, '7', [257, 258])
add('2.4-b', '未知不lost不刪、列不出不關', 79, '5.4、7', [225, 233, 256, 262])
add('2.4-c', '已報結束下一tock才刪、表未知不刪', 80, '5.1', [181, 205, 259])
add('2.4-d', '同回合重播補通知', 81, '7', [262])
add('2.4-e', 'F47不跨回合補送', 82, '7', [258, 263])
add('2.5-a', 'runner交接、失敗127、壞fd2、exit', 89, '5.3', [216, 218])
add('2.5-b', '環境傳遞與runner被殺判定', 89, '5.3、5.4；環境清單在5.5', [218, 233, 237],
    '行為與責任一致；環境原樣傳遞的節號較粗，精確清單在5.5，非新的B/G')
add('2.6-a', 'daemon請求回條或留、接受不等於生效、例外不重做', 97, '2.3', [68, 70, 71])
add('2.6-b', '非一般daemon請求B例外；I/O保留', 98, '0、2.3', [13, 70])
add('2.6-c', 'kill run必填、換run拒收、未知保留', 99, '6', [243, 245])
add('2.6-d', 'kill成功條件與Q1、防pgid重用', 100, '6', [246, 247])
add('2.7', '模組檔案接入、總結先於通知、x透傳', 105, '9、7、4.1', [142, 258, 271])
add('2.8-a', '環境、cwd、PATH', 123, '5.5', [237])
add('2.8-b', '同槽state保存', 123, '5.1、8', [195, 267])
add('2.8-c', 'tock最新可漏、Q1、keep無雙開', 123, '5.5、6、5.4', [238, 246, 233])
add('2.9', '狀態可讀、回條、停點恢復', 130, 'S-01、卡2.6、12', [19, 68, 243, 298])

Table(str(HERE / 'core-guarantees.json'), columns=list(rows[0]), rows=rows,
      meta={'contract': 'wf-table/1', 'source': 'summary.md', 'extracted': '2026-10-04'}).save()

packs = [
 ('control', 'modules/control/README.md', 'modules/control/aos7_control.py', '17-25', '85-93,107-131',
  '鎖內重讀birth、same req/run changed回done、先append再kill、G1拒寫、去重期限與目前birth/pending once一致'),
 ('subd', 'modules/subd/README.md', 'modules/subd/aos7-subd', '17-24,55-56', '36-52,98-145',
  '位置/認領/stopped拒起、守門檔、同群組、外部stop留stopped的靜態分支一致；README55的下一daemon掃描收尾承諾被G3動態探針推翻，見../stress/summary.md'),
 ('once_retry', 'modules/once_retry/README.md', 'modules/once_retry/retry_lost.py', '17-22', '19-30,34-63,66-72',
  'lost+never_started+同run+once+retry_lost選候選、retry_of去重、G1 pending、漏取樣/槽已刪排除一致'),
 ('audit', 'modules/audit/README.md', 'modules/audit/audit_site/sitecustomize.py', '17-23', '52-75,89-121,123-154',
  '判定需用登記邊界時每次重讀nodes、只記不擋、Python audit hook範圍一致；A4-05動態探針由模組線驗'),
 ('diag', 'modules/diag/README.md', 'modules/diag/aos7-diag', '17-20,66', '44-70,73-91',
  '只調judge/fact重算、不寫檔/kill/身分掃描；F47操作手冊已改不補送'),
 ('tools', 'modules/tools/README.md', 'modules/tools/aos7_ctl.py', '17-24', '50-70,93-129,168-198',
  '編碼/長名hash、kill讀birth補run、add表鎖rename、restart委派control一致；不把hash理論碰撞當新bug'),
 ('step', 'packs/step/README.md', 'packs/step/aos7_step.py', '17-33', '106-139,184-191,293-313,317-321,480-526,542-592,599-691',
  '型別預檢、有效選項、起始since、同attempt不重派、unknown與timeout界線一致；wrapper原子發布使用link，不影響卡的完整/不覆寫保證'),
]
pack_rows = [dict(name=n, card='proto7-2/'+d, code='proto7-2/'+c, card_lines=dl, code_lines=cl,
                  result='已對照，未確認新B/G', notes=note) for n,d,c,dl,cl,note in packs]
pack_rows[1]['result'] = '靜態分支已核；G3動態反例由壓測線記A5-01，不能判全包一致'
Table(str(HERE / 'pack-review.json'), columns=list(pack_rows[0]), rows=pack_rows,
      meta={'contract':'wf-table/1','source':'summary.md','extracted':'2026-10-04'}).save()

grep = subprocess.run(['grep','-n',r'ctl-seen\|ctl_id\|uid\|G2',core], cwd=REPO, capture_output=True, text=True)
headers = {m.group(1) for m in re.finditer(r'^#{2,3} (\d+(?:\.\d+)?)(?:\.|\s)', (REPO/spec).read_text(), re.M)}
refs = set(re.findall(r'§(\d+(?:\.\d+)?)', (REPO/core).read_text()))
four_fields = {p[0]: all(k in (REPO/'proto7-2'/p[1]).read_text() for k in ('職責','前置條件','保證','明確不管')) for p in packs}
result = {'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          'grep': {'argv':grep.args,'returncode':grep.returncode,'stdout':grep.stdout,'stderr':grep.stderr,'matches':len(grep.stdout.splitlines())},
          'core_guarantee_groups_checked': len(rows), 'spec_sections_missing':sorted(refs-headers),
          'seven_readmes_have_contract_section': {p[0]:'契約卡' in (REPO/'proto7-2'/p[1]).read_text() for p in packs},
          'seven_readmes_have_four_fields':four_fields,
          'A4-08':'修好：舊責任與控制檔例外已同步，packs測試入口已改',
          'A4-10':'文件界線修好；手改frame缺pc仍屬M，不計bug',
          'new_findings':[], 'cross_line_findings':['G3動態反例A5-01推翻subd README55的收尾承諾，見stress/summary.md'],
          'scope':'靜態契約核對；動態驗收由其他線提供'}
(HERE/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
