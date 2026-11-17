// This script renders offline forum snapshots and polls live posts while preserving the open discussion and drafts.
"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const live = ["http:", "https:"].includes(location.protocol);
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  const stamp = value => {
    const date = new Date(value);
    return Number.isNaN(+date) ? "—" : date.toLocaleString("zh-TW", {hour12: false});
  };
  const postId = () => new URLSearchParams(location.hash.slice(1)).get("post");
  const postHash = id => `#${new URLSearchParams({post: id})}`;
  let data = window.AOS_FORUM || null, filter = "all", currentId = null;
  let listSignature = "", postSignature = "", listScroll = 0, polling = false;

  function connection(ok = true) {
    byId("connection").textContent = !live ? "離線快照：開啟本機伺服器後即可發文與回覆。"
      : ok ? "即時・每 15 秒更新" : "暫時無法更新，保留最後資料。";
  }
  function badges(post) {
    const row = el("div", "forum-badges");
    if (post.pinned) row.append(el("span", "chip blue", "置頂"));
    if (post.featured) row.append(el("span", "chip amber", "精華"));
    if (post.deleted) row.append(el("span", "chip grey", "已刪除"));
    (post.tags || []).forEach(tag => row.append(el("span", "chip grey", tag)));
    return row;
  }
  function markdown(body) {
    // A "<!-- more -->" line splits the plain-language lead from folded details.
    const [lead, ...rest] = String(body || "").split(/^\s*<!--\s*more\s*-->\s*$/m);
    const node = el("div", "summary-body");
    node.append(window.AosMd.render(lead));
    if (rest.length) {
      const more = document.createElement("details");
      more.append(el("summary", "", "展開細節"), window.AosMd.render(rest.join("\n")));
      node.append(more);
    }
    return node;
  }
  function authors() {
    const select = byId("author-filter"), chosen = select.value;
    const names = [...new Set((data?.posts || []).map(post => post.author))].sort();
    if (JSON.stringify(names) === select.dataset.names) return;
    select.dataset.names = JSON.stringify(names);
    const all = el("option", "", "全部工作線"); all.value = "";
    select.replaceChildren(all);
    names.forEach(name => { const option = el("option", "", name); option.value = name; select.append(option); });
    select.value = names.includes(chosen) ? chosen : "";
  }
  function renderList() {
    const author = byId("author-filter").value, deleted = byId("show-deleted").checked;
    const posts = (data?.posts || []).filter(post => (deleted || !post.deleted)
      && (filter === "all" || post.featured) && (!author || author === post.author));
    const signature = JSON.stringify([data !== null, posts]);
    if (signature === listSignature) return;
    listSignature = signature;
    byId("post-count").textContent = `共 ${posts.length} 篇文章`;
    const host = byId("posts"); host.replaceChildren();
    if (!data) host.append(el("p", "banner", "尚無論壇快照。請先收集看板資料。"));
    else if (!posts.length) host.append(el("p", "banner", "目前沒有符合條件的文章。"));
    posts.forEach(post => {
      const card = el("article", `forum-card${post.deleted ? " forum-deleted" : ""}`);
      const heading = el("h2"), link = el("a", "", post.title); link.href = postHash(post.id); heading.append(link);
      card.append(heading, badges(post), el("p", "meta", `${post.author}｜${stamp(post.ts)}｜最近活動 ${stamp(post.last_ts)}｜${post.replies.length} 則回覆`));
      const excerpt = window.AosMd.render(String(post.body || "").replace(/<!--[\s\S]*?-->/g, "")).textContent;
      const text = excerpt.replace(/\s+/g, " ").trim(), chars = [...text];
      card.append(el("p", "forum-excerpt", chars.slice(0, 150).join("") + (chars.length > 150 ? "…" : "")));
      host.append(card);
    });
  }
  function renderPost(id) {
    const post = (data?.posts || []).find(item => item.id === id);
    const signature = JSON.stringify([id, post]);
    if (signature === postSignature) return;
    postSignature = signature;
    const host = byId("post-content");
    const folds = [...host.querySelectorAll("details")].map(node => node.open);
    host.replaceChildren();
    byId("reply-form").hidden = !live || !post || post.deleted;
    if (!post) { host.append(el("p", "banner", "找不到這篇文章。")); return; }
    const article = el("article", post.deleted ? "forum-deleted" : "");
    article.append(el("h2", "", post.title), badges(post),
      el("p", "meta", `${post.author}｜${stamp(post.ts)}｜最近活動 ${stamp(post.last_ts)}`), markdown(post.body),
      el("p", "meta forum-source", `原始檔案：${post.source_path || "未提供"}`));
    const replies = el("section", "forum-replies");
    replies.append(el("h3", "", `回覆（${post.replies.length}）`));
    if (!post.replies.length) replies.append(el("p", "meta", "還沒有回覆。"));
    post.replies.forEach(reply => {
      const item = el("article", "forum-reply");
      item.append(el("p", "meta", `${reply.author}｜${stamp(reply.ts)}`), markdown(reply.body)); replies.append(item);
    });
    article.append(replies); host.append(article);
    host.querySelectorAll("details").forEach((node, index) => { if (index < folds.length) node.open = folds[index]; });
  }
  function render() {
    const y = window.scrollY;
    authors(); renderList();
    if (currentId) renderPost(currentId);
    window.scrollTo(0, y);
  }
  function navigate() {
    const next = postId(), changed = next !== currentId;
    if (changed && !currentId) listScroll = window.scrollY;
    if (changed) {
      byId("reply-form").reset();
      byId("reply-form").querySelector(".form-status").textContent = "";
      postSignature = "";
    }
    currentId = next;
    byId("forum-list").hidden = Boolean(next);
    byId("post-panel").hidden = !next;
    byId("composer").hidden = !live || Boolean(next);
    render();
    if (changed) window.scrollTo(0, next ? 0 : listScroll);
  }
  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch(`data/forum.json?t=${Date.now()}`, {cache: "no-store"});
      if (!response.ok) throw new Error(`Forum snapshot request failed (${response.status})`);
      data = await response.json(); render(); connection();
    } catch (error) {
      console.error("forum: error: SnapshotReadFailed", error.message); connection(false);
    } finally { polling = false; }
  }
  async function submit(event, kind) {
    event.preventDefault();
    const form = event.currentTarget, status = form.querySelector(".form-status");
    const body = {body: form.elements.body.value};
    if (kind === "reply") body.post = currentId; else body.title = form.elements.title.value;
    status.className = "form-status";
    if (!body.body.trim() || (kind === "post" && !body.title.trim())) {
      status.textContent = kind === "reply" ? "請填寫非空白的回覆。" : "請填寫非空白的標題與內文。"; return;
    }
    [...form.elements].forEach(input => { input.disabled = true; });
    status.textContent = "送出中…";
    try {
      const response = await fetch(`api/forum/${kind}`, {
        method: "POST", headers: {"Content-Type": "application/json", "X-AOS-Board": "1"}, body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || `Forum submission failed (${response.status})`);
      form.reset(); await poll();
      status.textContent = kind === "reply" ? "回覆已送出。" : "文章已發表。";
      if (kind === "post") location.hash = postHash(result.post);
    } catch (error) {
      console.error("forum: error: SubmissionFailed", error.message);
      status.className = "form-status error";
      status.textContent = "送出失敗，請確認連線與內容長度後再試。";
    } finally { [...form.elements].forEach(input => { input.disabled = false; }); }
  }
  document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
    filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
    render();
  }));
  byId("author-filter").addEventListener("change", render);
  byId("show-deleted").addEventListener("change", render);
  if (live) {
    byId("post-form").addEventListener("submit", event => submit(event, "post"));
    byId("reply-form").addEventListener("submit", event => submit(event, "reply"));
  }
  window.addEventListener("hashchange", navigate);
  connection(); navigate();
  if (live) { poll(); setInterval(poll, 15000); }
})();
