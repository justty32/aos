"""Render validated decision data as a self-contained offline HTML page."""
import hashlib
import html
import json
from pathlib import Path
import re

from model import shown_source


WEB = Path(__file__).parent / 'web'


def esc(value):
    return html.escape(str(value), quote=True)


def inline(value):
    """Escape text while preserving only inline code and bold spans."""
    parts = re.split(r'(`[^`\n]+`|\*\*[^\n]+?\*\*)', str(value))
    return ''.join('<code>' + esc(p[1:-1]) + '</code>' if i % 2 and p.startswith('`')
                   else '<strong>' + esc(p[2:-2]) + '</strong>' if i % 2
                   else esc(p) for i, p in enumerate(parts))


def quote(item):
    return ('<blockquote class="quote"><p>' + inline(item['text']) + '</p><cite>'
            + inline(item['cite']) + '</cite></blockquote>')


def figure(svg, caption, cls=''):
    return (f'<figure class="{cls}">' + svg + '<figcaption class="muted">'
            + inline(caption) + '</figcaption></figure>')


def fallback(row):
    return row.get('recommend') or (row['options'][0]['key'] if row['options'] else '-')


def overview(data):
    if data.get('overview_svg'):
        return figure(data['overview_svg'], data.get('overview_caption', ''), 'overview')
    counts = [sum(r['section'] == s['id'] for r in data['rows']) for s in data['sections']]
    maximum = max(counts, default=1) or 1
    svg = [f'<svg viewBox="0 0 640 {max(50, len(counts) * 48 + 16)}" role="img" aria-label="各節題數">']
    for i, (section, count) in enumerate(zip(data['sections'], counts)):
        y = i * 48 + 32
        svg.append(f'<text x="8" y="{y}" class="t14 s-ink">{esc(section["title"])}</text>'
                   f'<rect x="320" y="{y - 19}" width="{230 * count / maximum:g}" height="26" rx="5" class="s-ask"/>'
                   f'<text x="630" y="{y}" text-anchor="end" class="t14 s-ink">{count} 題</text>')
    svg.append('</svg>')
    n = len(data['rows'])
    missing = sum(not r.get('recommend') for r in data['rows'])
    caption = f'共 {n} 題；每題都有推薦（★），不想細看就全照推薦。'
    if missing:
        caption = f'共 {n} 題；{missing} 題只收意見，其餘可照推薦（★）。'
    return figure(''.join(svg), caption, 'overview')


def card(row, data_path):
    qid = esc(row['id'])
    selected = fallback(row)
    out = [f'<article class="card" id="q-{qid}" data-qid="{qid}"><header><span class="num">{qid}</span>'
           f'<h3 id="heading-{qid}">{inline(row["question"])}</h3></header>']
    if row.get('eli5'):
        out.append('<p class="muted">' + inline(row['eli5']) + '</p>')
    quotes = row.get('quotes', [])
    if quotes:
        out.append(quote(quotes[0]))
    if row['options']:
        out.append(f'<ul class="opts is-interactive" role="radiogroup" aria-labelledby="heading-{qid}">')
        for option in row['options']:
            key = esc(option['key'])
            checked = option['key'] == selected
            rec = option['key'] == row.get('recommend')
            classes = ('rec ' if rec else '') + ('is-selected' if checked else '')
            out.append(f'<li class="{classes}"><label class="option-label"><input type="radio" name="q-{qid}" value="{key}"'
                       + (' checked' if checked else '') + '><span class="option-content"><span class="option-title">'
                       + f'<b>{key}</b> {inline(option["label"])}'
                       + (' <span class="star">★ 推薦</span>' if rec else '') + '</span>'
                       + '<span class="option-consequence">' + inline(option.get('consequence', ''))
                       + '</span></span><span class="option-check" aria-hidden="true">✓</span></label></li>')
        out.append('</ul>')
    if row.get('why'):
        out.append('<p class="concl">推薦 ' + esc(row.get('recommend', '')) + '：' + inline(row['why']) + '</p>')
    out.append(f'<label class="review-note">備註（選填）<textarea rows="2" placeholder="想補一句話？" aria-label="{qid} 備註"></textarea></label>'
               '<div class="button-row"><button class="read-mark" type="button" aria-pressed="false">看過，先照這個</button></div>'
               '<details><summary>細節・原話・來源</summary>')
    out.extend(quote(q) for q in quotes[1:])
    if row.get('details'):
        out.append('<ul>' + ''.join('<li>' + inline(s) + '</li>' for s in row['details']) + '</ul>')
    source = shown_source(data_path, row.get('source_path', '')) if row.get('source_path') else ''
    lines = row.get('source_lines', '')
    out.append('<p class="files">來源：<code>' + esc(source + (':' + lines if lines else '')) + '</code></p>')
    if row.get('source_excerpt'):
        out.append('<details><summary>來源原文（逐字）</summary><pre class="source-excerpt">'
                   + esc(row['source_excerpt']) + '</pre></details>')
    out.append('</details></article>')
    return ''.join(out)


def render(data, data_path):
    """Return static HTML with bundled styles, interaction code, and safe JSON."""
    rows = data['rows']
    n = len(rows)
    identity = [[r['id'], [o['key'] for o in r['options']]] for r in rows]
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:12]
    payload = {'batch': data['batch'], 'storage_key': f'aos-decide-{data["batch"]}-{digest}',
               'rows': [{'id': r['id'], 'keys': [o['key'] for o in r['options']],
                         'recommend': r.get('recommend', ''), 'fallback': fallback(r)} for r in rows]}
    initial = '[' + data['batch'] + '] ' + '、'.join(
        r['id'] + ':' + fallback(r) + ('*' if r['options'] and fallback(r) != r.get('recommend') else '') + '?'
        for r in rows)
    recommended = '[' + data['batch'] + '] ' + '、'.join(r['id'] + ':' + fallback(r) for r in rows)
    css = (WEB / 'page.css').read_text(encoding='utf-8')
    js = (WEB / 'page.js').read_text(encoding='utf-8')
    out = ['<!doctype html><html lang="zh-TW"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<meta name="color-scheme" content="light dark"><title>' + esc(data['title'])
           + '</title><style>' + css + '</style></head><body>'
           '<button id="theme" type="button" aria-label="切換淺色深色">淺／深</button><main class="wrap">']
    if data.get('kicker'):
        out.append('<p class="muted">' + inline(data['kicker']) + '</p>')
    out.extend(['<h1>' + inline(data['title']) + '</h1>', overview(data), '<ul class="lead">'])
    out.extend('<li>' + inline(s) + '</li>' for s in data['lead'])
    out.append('</ul><nav class="toc" aria-label="跳到各節">')
    for section in data['sections']:
        count = sum(r['section'] == section['id'] for r in rows)
        out.append(f'<a href="#sec-{esc(section["id"])}">{inline(section["title"])} {count}</a>')
    out.append('<a href="#reply">怎麼回覆</a></nav><details><summary>怎麼用</summary><p>'
               '每題點一個選項，想補充就寫備註。點選項、寫備註、打開細節或按「看過」都算看過；'
               '沒看過的題在回覆裡會帶「?」，代表照推薦先代定、不算你裁過。右下「我的回覆」會組好一行字，'
               '按「複製」後貼回對話，或貼到看板「待你裁」裡這批那題的意見框送出。選擇會存在這個瀏覽器。</p></details>')
    for section in data['sections']:
        out.append(f'<section><h2 id="sec-{esc(section["id"])}">{inline(section["title"])}</h2>')
        if section.get('intro'):
            out.append('<p class="muted">' + inline(section['intro']) + '</p>')
        if section.get('figure_svg'):
            out.append(figure(section['figure_svg'], section.get('caption', '')))
        out.extend(card(r, data_path) for r in rows if r['section'] == section['id'])
        out.append('</section>')
    for appendix in data.get('appendix', []):
        out.append('<details><summary>' + inline(appendix['title']) + '</summary><ul>'
                   + ''.join('<li>' + inline(s) + '</li>' for s in appendix['items']) + '</ul></details>')
    out.append('<h2 id="reply">怎麼回覆</h2><p>在「我的回覆」按「複製」，貼回對話或看板這批的意見框。</p>'
               '<details><summary>全照推薦時等於回這一行</summary><pre>' + esc(recommended) + '</pre></details></main>')
    out.append('<aside class="reply-dock"><button class="reply-toggle" type="button" aria-expanded="true" aria-controls="reply-body">'
               f'<strong>我的回覆</strong><span class="reply-compact">已看過 0／{n} 題</span><span class="reply-toggle-action">收合</span>'
               '</button><div class="reply-body" id="reply-body"><div class="reply-progress">'
               f'<progress value="0" max="{max(1, n)}" aria-label="已看過題數"></progress></div>'
               f'<p class="reply-changes">* ＝跟推薦不同（0 題）；? ＝還沒看過（{n} 題，會記成代定）</p>'
               '<textarea class="reply-output" readonly aria-label="我的回覆">' + esc(initial) + '</textarea>'
               '<div class="reply-actions"><button class="reply-copy" type="button">複製</button>'
               '<button class="reply-reset" type="button">全部重設為推薦</button></div>'
               '<p class="reply-status" role="status" aria-live="polite"></p></div></aside>')
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out.append('<script type="application/json" id="decide-data">' + blob + '</script><script>' + js + '</script></body></html>')
    return ''.join(out)
