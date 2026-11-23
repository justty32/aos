# web.py - 使用者專區的網頁（aos-user serve）：只綁 127.0.0.1，看信、裁題（每題可留言）、回信、看門上公告、發／收公告；邏輯全部呼叫 zone.py，不寫第二份。
# 安全：Host 只收 127.0.0.1／localhost＋本埠；POST 要帶 web/token（GET 時放進 cookie 與表單，兩者都要對）；有 Origin 就要是本機。
# 同一個 Linux 帳號的 agent 一樣連得到本機網頁，所以「網頁回的」不比指令列回的更可信（規劃 02 第 5 節）。
import html
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import zone as Z

KIND_ZH = {"decide": "要你裁", "verify": "要你驗", "trial": "請你試", "chore": "要你做", "fyi": "告知"}
KIND_COLOR = {"decide": "--c-decide", "verify": "--c-verify", "trial": "--c-trial", "chore": "--c-chore", "fyi": "--c-fyi"}

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e2e0d8;--accent:#2f5d8a;--rec:#b8860b;
--c-decide:#2f5d8a;--c-verify:#2e7d4f;--c-trial:#8a4f9e;--c-chore:#b5651d;--c-fyi:#8a8a84;--warn:#b3261e}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17181a;--card:#222326;--ink:#ecebe6;--mute:#a09f99;
--line:#35363a;--accent:#7fb0e0;--rec:#e0b84a;--c-decide:#7fb0e0;--c-verify:#6cc08f;--c-trial:#c79ad6;--c-chore:#e0a060;--c-fyi:#a5a5a0;--warn:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,"Noto Sans TC",sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}a{color:var(--accent)}
nav{display:flex;gap:16px;align-items:baseline;margin-bottom:12px;flex-wrap:wrap}nav b{font-size:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.badge{display:inline-block;font-size:13px;padding:1px 8px;border-radius:999px;color:#fff;margin-right:6px}
.mute{color:var(--mute);font-size:14px}.urgent{color:var(--warn);font-weight:600}
.opt{display:block;border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:6px 0;cursor:pointer}
.opt:has(input:checked){border-color:var(--accent);outline:2px solid var(--accent)}
.rec{color:var(--rec);font-weight:600}textarea,input[type=text]{width:100%;min-height:70px;font:inherit;padding:8px;border-radius:8px;
border:1px solid var(--line);background:var(--bg);color:var(--ink)}input[type=text],textarea.one{min-height:0}
button{font:inherit;padding:8px 16px;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:var(--bg);cursor:pointer}
button.ghost{background:transparent;color:var(--accent)}details{margin-top:6px}summary{cursor:pointer;color:var(--mute)}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:8px;border-radius:8px;font-size:13px}
.line{font-family:ui-monospace,monospace;font-size:14px;background:var(--bg);padding:6px 8px;border-radius:6px}
.msg{border-left:4px solid var(--accent);padding:8px 12px;background:var(--card)}
svg text{fill:var(--ink);font-size:12px}
"""


def esc(s):
    return html.escape("" if s is None else str(s))


def page(title, body):
    return ("<!doctype html><html lang=zh-Hant><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><title>%s</title><style>%s</style></head>"
            "<body><main><nav><b>你的專區</b><a href='/'>待辦</a><a href='/done'>已回</a><a href='/door'>門上公告</a></nav>%s"
            "</main></body></html>" % (esc(title), CSS, body))


def badge(kind):
    return "<span class=badge style='background:var(%s)'>%s</span>" % (KIND_COLOR.get(kind, "--c-fyi"), esc(KIND_ZH.get(kind, kind)))


def summary_svg(rows):
    """待辦一張圖：五種各幾封（橫條），急件另標。"""
    counts = {k: 0 for k in Z.KINDS}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    urgent = sum(1 for r in rows if r["urgent"])
    mx = max(counts.values()) or 1
    h, bar = 22, 360
    parts = []
    for i, k in enumerate(Z.KINDS):
        y = i * h + 4
        w = int(bar * counts[k] / mx) if counts[k] else 0
        parts.append("<text x=0 y=%d>%s</text>" % (y + 14, esc(KIND_ZH[k])))
        parts.append("<rect x=64 y=%d width=%d height=14 rx=3 style='fill:var(%s)'></rect>" % (y + 3, max(w, 2), KIND_COLOR[k]))
        parts.append("<text x=%d y=%d>%d</text>" % (70 + max(w, 2), y + 14, counts[k]))
    svg = "<svg viewBox='0 0 460 %d' width=100%% role=img aria-label='待辦統計'>%s</svg>" % (len(Z.KINDS) * h + 8, "".join(parts))
    head = "共 <b>%d</b> 件在等你%s" % (len(rows), ("，其中 <span class=urgent>%d 件急</span>" % urgent) if urgent else "")
    return "<div class=card>%s<p>%s</p></div>" % (svg, head)


def list_page(zone, msg=""):
    ws = Z.waiting(zone)
    rows = [m.row(i, s) for i, (m, s) in enumerate(ws, 1)]
    out = [("<p class=msg>%s</p>" % esc(msg)) if msg else ""]
    try:
        ann = Z.announce_get(zone)
    except Z.Fail:
        ann = None
    if ann:
        out.append("<p class=msg>你的公告掛著%s：%s　<a href='/door'>改或收掉</a></p>" % (
            ("（到 %s）" % esc(ann["until"])) if ann["until"] else "（沒有結束時間）", esc(ann["text"])))
    lost = Z.lost_letters(zone)
    if lost:
        out.append("<p class='msg urgent'>有 %d 封看過的信不見了（可能被 aos-mailbox read 刪了）：%s</p>" % (len(lost), esc(", ".join(lost))))
    out.append(summary_svg(rows))
    if not rows:
        out.append("<p>現在沒有事在等你。</p>")
    for r in rows:
        extra = []
        if r["questions"]:
            extra.append("%d 題" % r["questions"])
        if r["deadline"]:
            extra.append("期限 " + esc(r["deadline"]))
        if r["format"] == "old":
            extra.append("舊格式")
        if r["same"]:
            extra.append("%d 封同題" % (len(r["same"]) + 1))
        if r["where"] == "new":
            extra.append("沒看過")
        out.append("<div class=card>%s%s<a href='/l/%s'><b>%s</b></a><div class=mute>%s 寄 · %s</div></div>" % (
            badge(r["kind"]), "<span class=urgent>急 </span>" if r["urgent"] else "",
            urllib.parse.quote(r["letter"]), esc(r["title"] or r["letter"]), esc(r["from"] or "?"), " · ".join(extra)))
    return page("你的專區", "".join(out))


def letter_page(zone, name, token):
    main, same = Z.pick(zone, name)
    x = Z.take(zone, main)
    for s in same:
        Z.take(zone, s)
    b = x.body
    draft = Z.load_draft(zone, x.name) or {}
    dans = {a["id"]: a["answer"] for a in draft.get("answers", []) if isinstance(a, dict)}
    dcom = {a["id"]: a.get("comment", "") for a in draft.get("answers", []) if isinstance(a, dict)}
    out = ["<div class=card>%s%s<h2 style='margin:4px 0'>%s</h2><div class=mute>%s 寄%s%s</div>" % (
        badge(x.kind), "<span class=urgent>急 </span>" if x.urgent else "", esc(b.get("title") or x.name),
        esc(b.get("from") or "?"), (" · 期限 " + esc(b["deadline"])) if b.get("deadline") else "",
        (" · 另有 %d 封同一題，回一次全部收到" % len(same)) if same else "")]
    if b.get("what"):
        out.append("<p>%s</p>" % esc(b["what"]))
    if b.get("done_when"):
        out.append("<p><b>做完怎樣算好：</b>%s</p>" % esc(b["done_when"]))
    if b.get("default_if_silent"):
        out.append("<p class=mute>沒回的話：%s</p>" % esc(b["default_if_silent"]))
    if b.get("risk") == "irreversible":
        out.append("<p class=urgent>不可逆的事（push、刪檔、對外）：請逐題自己點，不能一鍵照推薦。</p>")
    raw = json.dumps(x.letter, ensure_ascii=False, indent=1)
    out.append("<details><summary>原信全文</summary><pre>%s</pre></details></div>" % esc(raw))
    out.append("<form method=post action='/answer'><input type=hidden name=token value='%s'>"
               "<input type=hidden name=letter value='%s'>" % (esc(token), esc(x.name)))
    qs = x.questions()
    for q in qs:
        out.append("<div class=card><b>%s</b><p class=mute>%s</p>" % (esc(q.get("question")), esc(q.get("eli5"))))
        for o in q["options"] + [{"key": "other", "label": "都不要，我自己寫（寫在這題的留言格）"}]:
            rec = o["key"] == q.get("recommend")
            chk = " checked" if dans.get(q["id"]) == o["key"] else ""
            out.append("<label class=opt><input type=radio name='q_%s' value='%s' data-rec='%s'%s> <b>%s</b> %s%s%s</label>" % (
                esc(q["id"]), esc(o["key"]), "1" if rec else "", chk, esc(o["key"]), esc(o.get("label")),
                (" <span class=mute>→ %s</span>" % esc(o["consequence"])) if o.get("consequence") else "",
                " <span class=rec>★推薦</span>" if rec else ""))
        out.append("<textarea class=one name='c_%s' placeholder='這題的留言（可空；只寫留言沒選＝都不要，我自己寫）'>%s</textarea>" % (
            esc(q["id"]), esc(dcom.get(q["id"], ""))))
        det = []
        for k, zh in (("why", "推薦理由"), ("details", "細節"), ("source_path", "出處")):
            if q.get(k):
                det.append("<p><b>%s：</b>%s</p>" % (zh, esc(q[k])))
        if det:
            out.append("<details><summary>理由與細節</summary>%s</details>" % "".join(det))
        out.append("</div>")
    out.append("<div class=card>")
    if qs:
        out.append("<p><b>整封的意見（可空）</b></p><textarea name=note>%s</textarea>" % esc(draft.get("note", "")))
        out.append("<p class=mute>會送出這一行：<span class=line id=preview>（還沒選）</span></p>")
        out.append("<button name=action value=answer>送出</button> <button class=ghost name=action value=draft>存草稿</button>")
        if b.get("risk") != "irreversible":
            out.append(" <button class=ghost type=button onclick='allRec()'>全部照推薦</button>")
    else:
        if x.kind == "fyi" and x.fmt == "zone":
            out.append("<button name=action value=ok>知道了</button>")
            if x.reply_box():
                out.append("<details><summary>想回一句話</summary><textarea name=text></textarea>"
                           "<button name=action value=reply>寄回去</button></details>")
        else:
            out.append("<p><b>回一段話</b></p><textarea name=text>%s</textarea>" % esc(draft.get("text", "")))
            out.append("<button name=action value=reply>寄回去</button> <button class=ghost name=action value=draft>存草稿</button>")
            if x.fmt == "old":
                out.append(" <button class=ghost name=action value=ok>不回，收起來</button>")
    out.append("</div></form>")
    out.append("""<script>
const recs=%s;
function line(){const f=document.forms[0];const ps=[];for(const [id,rec] of recs){const c=f.querySelector('input[name="q_'+id+'"]:checked');
const t=f.querySelector('textarea[name="c_'+id+'"]');const m=(t&&t.value.trim())||'';const v=c?c.value:(m?'other':'');
if(v)ps.push(id+':'+v+(v!==rec?'*':'')+(m?'「'+m+'」':''));}let s=ps.join('、');const n=(f.note&&f.note.value.trim())||'';
if(n)s+='（備註：'+n.replace(/\\n/g,' / ')+'）';const p=document.getElementById('preview');if(p)p.textContent=s||'（還沒選）';}
function allRec(){if(!confirm('沒選的題都照推薦？'))return;const f=document.forms[0];for(const [id,rec] of recs){
if(!f.querySelector('input[name="q_'+id+'"]:checked')){const r=f.querySelector('input[name="q_'+id+'"][value="'+rec+'"]');if(r)r.checked=true;}}line();}
document.addEventListener('input',line);line();
</script>""" % json.dumps([[q["id"], q.get("recommend")] for q in qs]))
    return page(b.get("title") or x.name, "".join(out))


def done_page(zone):
    out = ["<p class=mute>最近回過的（最新在上）</p>"]
    for r in Z.done_list(zone):
        rp = r["reply"] or {}
        out.append("<div class=card>%s<b>%s</b><div class=mute>%s 寄 · %s</div><p class=line>%s</p></div>" % (
            badge(r["kind"]) if r["kind"] in Z.KINDS else "", esc(r["title"] or r["letter"]), esc(r["from"]),
            esc(rp.get("answered_at") or r["month"]), esc(rp.get("answer_line") or rp.get("text") or "知道了（沒回信）")))
    return page("已回", "".join(out))


def announce_card(zone, token):
    a = Z.announce_get(zone)
    now = ("<p>現在掛著：<b>%s</b></p><p class=mute>%s 貼的 · %s</p>" % (
        esc(a["text"]), esc(a["at"]), ("到 %s 為止" % esc(a["until"])) if a["until"] else "沒有結束時間，收掉才消失")
           if a else "<p class=mute>現在沒有公告。</p>")
    clear = ("<form method=post action='/announce'><input type=hidden name=token value='%s'>"
             "<button class=ghost name=action value=clear>收掉公告</button></form>" % esc(token)) if a else ""
    return ("<div class=card><b>你的公告</b>（給各 agent 看的一句話，例如去睡午覺、幾點回來；一次一則，新的蓋掉舊的；過了時間就不算）%s"
            "<form method=post action='/announce'><input type=hidden name=token value='%s'>"
            "<input type=text name=text placeholder='我去睡午覺，一小時後回來'>"
            "<p class=mute>多久（可空，例 90m、2h、1d）<input type=text name=for placeholder='90m'>"
            "或到什麼時候（可空，例 2026-11-23T15:00）<input type=text name=until placeholder='2026-11-23T15:00'></p>"
            "<button name=action value=set>貼上</button></form>%s</div>" % (now, esc(token), clear))


def door_page(zone, token, msg=""):
    d = Z.door_view(zone)
    mode = d.get("mode")
    rules = "".join("<li>%s</li>" % esc(r) for r in d.get("rules", []))
    body = ("<div class=card><p>門上公告是貼給寄信的 agent 看的：收哪幾種信、題目要帶選項與推薦。</p>"
            "<p>現在：<b>%s</b></p><form method=post action='/door'><input type=hidden name=token value='%s'>"
            "<button name=mode value='%s'>切成%s</button></form></div>"
            "<div class=card><b>收的信</b>：%s<details><summary>規則全文</summary><ul>%s</ul><pre>%s</pre></details></div>"
            % ("在家（normal）" if mode != "away" else "出門（away）", esc(token), "away" if mode != "away" else "normal",
               "出門" if mode != "away" else "在家", esc("、".join(KIND_ZH.get(k, k) for k in d.get("accept", []))),
               rules, esc(json.dumps(d, ensure_ascii=False, indent=1))))
    return page("門上公告", (("<p class=msg>%s</p>" % esc(msg)) if msg else "") + announce_card(zone, token) + body)


def make_handler(zone, port):
    tok_path = os.path.join(zone, "web", "token")
    hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}
    origins = {"http://" + h for h in hosts}

    def token():
        with open(tok_path) as f:
            return f.read().strip()

    class H(BaseHTTPRequestHandler):
        server_version = "aos-user"

        def log_message(self, fmt, *a):
            pass

        def send(self, code, text, ctype="text/html; charset=utf-8", extra=None):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def host_ok(self):
            if self.headers.get("Host", "") not in hosts:
                self.send(403, "bad host\n", "text/plain")
                return False
            return True

        def cookie_token(self):
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "zt":
                    return v
            return None

        def do_GET(self):
            if not self.host_ok():
                return
            t = token()
            ck = {"Set-Cookie": "zt=%s; HttpOnly; SameSite=Strict; Path=/" % t}
            path = urllib.parse.urlparse(self.path).path
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                if path == "/":
                    self.send(200, list_page(zone, (q.get("msg") or [""])[0]), extra=ck)
                elif path.startswith("/l/"):
                    self.send(200, letter_page(zone, urllib.parse.unquote(path[3:]), t), extra=ck)
                elif path == "/done":
                    self.send(200, done_page(zone), extra=ck)
                elif path == "/door":
                    self.send(200, door_page(zone, t, (q.get("msg") or [""])[0]), extra=ck)
                elif path == "/api/ls":
                    ws = Z.waiting(zone)
                    self.send(200, json.dumps([m.row(i, s) for i, (m, s) in enumerate(ws, 1)], ensure_ascii=False),
                              "application/json")
                else:
                    self.send(404, page("找不到", "<p>沒有這一頁。</p>"))
            except Z.Fail as e:
                self.send(404 if e.code == "LetterMissing" else 500,
                          page("出錯", "<p class=msg>%s</p><p>這封可能已經回過了。<a href='/'>回待辦</a></p>" % esc("%s %s" % (e.code, e))))

        def do_POST(self):
            if not self.host_ok():
                return
            org = self.headers.get("Origin")
            if org and org not in origins:
                self.send(403, "bad origin\n", "text/plain")
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n > 200000:
                self.send(413, "too big\n", "text/plain")
                return
            form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True)
            f = {k: v[0] for k, v in form.items()}
            t = token()
            if f.get("token") != t or self.cookie_token() != t:
                self.send(403, "bad token\n", "text/plain")
                return
            path = urllib.parse.urlparse(self.path).path
            try:
                if path == "/door":
                    Z.door_mode(zone, f.get("mode", ""))
                    return self.redirect("/door")
                if path == "/announce":
                    if f.get("action") == "clear":
                        Z.announce_clear(zone)
                        return self.redirect("/door?msg=" + urllib.parse.quote("公告收掉了"))
                    Z.announce_set(zone, f.get("text", ""), until=f.get("until", "").strip() or None,
                                   for_=f.get("for", "").strip() or None)
                    return self.redirect("/door?msg=" + urllib.parse.quote("公告貼上了"))
                if path != "/answer":
                    return self.send(404, "no\n", "text/plain")
                name, act = f.get("letter", ""), f.get("action", "")
                note, text = f.get("note", "").strip(), f.get("text", "").strip()
                picked = {}                   # qid → [代號, 留言]；只寫留言沒選＝other（代號明寫，不靠猜）
                for k, v in f.items():
                    if k[:2] in ("q_", "c_") and v.strip():
                        picked.setdefault(k[2:], ["", ""])[0 if k[0] == "q" else 1] = v.strip()
                picked = {qid: [key or "other", com] for qid, (key, com) in picked.items()}
                answers = ["%s:%s%s" % (qid, key, ":" + com if com else "") for qid, (key, com) in picked.items()]
                if act == "draft":
                    m, _ = Z.pick(zone, name)
                    Z.save_draft(zone, m, {"answers": [dict({"id": qid, "answer": key}, **({"comment": com} if com else {}))
                                                       for qid, (key, com) in picked.items()],
                                           "note": note, "text": text})
                    return self.redirect("/l/" + urllib.parse.quote(name))
                if act == "answer":
                    out, _ = Z.respond(zone, name, answers=answers, note=note, via="web")
                elif act == "reply":
                    out, _ = Z.respond(zone, name, text=text, via="web")
                elif act == "ok":
                    out, _ = Z.respond(zone, name, ok_only=True, via="web")
                else:
                    return self.send(400, "bad action\n", "text/plain")
                msg = "已送出：%s" % ", ".join("%s → %s" % (r["letter"], r.get("to") or "收起來") for r in out)
                return self.redirect("/?msg=" + urllib.parse.quote(msg))
            except Z.Fail as e:
                if e.code == "LetterMissing":
                    return self.send(409, page("已回過", "<p class=msg>這封已經回過或不在了。</p><a href='/'>回待辦</a>"))
                back = "/door" if path == "/announce" else "/l/" + urllib.parse.quote(f.get("letter", ""))
                self.send(400, page("沒送出", "<p class=msg>%s</p><p><a href='%s'>回去改</a></p>" % (
                    esc("%s %s" % (e.code, e)), esc(back))))

        def redirect(self, to):
            self.send_response(303)
            self.send_header("Location", to)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return H


def serve(zone, port):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(zone, port))
    print("aos-user: serving %s on http://127.0.0.1:%d/ (pid %d)" % (zone, port, os.getpid()), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
