// This script renders decision questions while retaining drafts and focused controls across polls.
"use strict";
window.AOSAsks = ({el, heading, details, chip, link, poll}) => {
  const panel = el("section", "panel asks-panel"), drafts = new Map();
  const offline = location.protocol === "file:";
  let signature = null;
  const stamp = value => {
    const date = new Date(value);
    return value && !Number.isNaN(+date) ? date.toLocaleString("zh-TW", {hour12: false}) : "—";
  };
  function base(ask) {
    const card = el("article", "ask-card");
    card.append(el("h3", "", ask.line_title || ask.line), el("p", "meta", stamp(ask.ts)), el("p", "ask-question", ask.text));
    if ((ask.links || []).length) {
      const links = el("div", "event-links");
      ask.links.forEach(path => links.append(link(path)));
      card.append(links);
    }
    return card;
  }
  function openCard(ask) {
    const card = base(ask), form = el("form", "ask-form");
    const draft = drafts.get(ask.id) || {choice: "", comment: ""}; drafts.set(ask.id, draft);
    const options = el("fieldset", "ask-options"); options.append(el("legend", "", "請選一項"));
    (ask.options || []).forEach(option => {
      const row = el("label", "ask-option"), radio = el("input");
      radio.type = "radio"; radio.name = "choice"; radio.value = option.key; radio.checked = draft.choice === option.key;
      radio.disabled = offline;
      radio.addEventListener("change", () => { draft.choice = radio.value; });
      row.append(radio, el("span", "", option.text));
      if (ask.recommend === option.key) row.append(chip("推薦", "amber"));
      options.append(row);
    });
    const label = el("label", "ask-comment", "意見（可空）"), comment = el("textarea");
    comment.rows = 3; comment.value = draft.comment; comment.disabled = offline;
    comment.addEventListener("input", () => { draft.comment = comment.value; }); label.append(comment);
    const submit = el("button", "button ask-submit", "送出"), status = el("p", "ask-status");
    submit.type = "submit"; submit.disabled = offline; status.setAttribute("role", "status");
    form.append(options, label, submit, status); card.append(form);
    form.addEventListener("submit", async event => {
      event.preventDefault(); if (offline || submit.disabled) return;
      if (!draft.choice && !draft.comment.trim()) { status.textContent = "請選一項或填寫意見。"; return; }
      submit.disabled = true; status.className = "ask-status"; status.textContent = "送出中…";
      try {
        const response = await fetch("api/answer", {method: "POST", headers: {"Content-Type": "application/json", "X-AOS-Board": "1"}, body: JSON.stringify({id: ask.id, choice: draft.choice || null, comment: draft.comment})});
        if (!response.ok) {
          let message = `送出失敗（${response.status}）`;
          try { const error = await response.json(); message += `：${error.error || error.message || "請稍後再試"}`; } catch (_) { /* Keep the HTTP status when no JSON error is available. */ }
          throw new Error(message);
        }
        status.textContent = "已送出"; status.className = "ask-status green";
        form.querySelectorAll("input, textarea").forEach(control => { control.disabled = true; });
        drafts.delete(ask.id); await poll();
      } catch (error) {
        status.className = "ask-status error"; status.textContent = error.message || "送出失敗，請稍後再試。"; submit.disabled = false;
      }
    });
    return card;
  }
  function answeredCard(ask) {
    const card = base(ask), answer = ask.answer;
    const chosen = (ask.options || []).find(option => option.key === answer.choice);
    card.append(el("p", "ask-question", `已選：${chosen ? chosen.text : (answer.choice || "無")}`));
    if (answer.comment) card.append(el("p", "ask-question", `意見：${answer.comment}`));
    card.append(el("p", "meta", `作答時間 ${stamp(answer.ts)}`)); return card;
  }
  return {
    panel,
    update(data) {
      const asks = data.asks || [], next = JSON.stringify(asks);
      if (next === signature) return;
      signature = next; panel.replaceChildren(); heading(panel, "待你裁", "ask");
      const open = asks.filter(ask => !ask.answer), answered = asks.filter(ask => ask.answer);
      panel.append(el("p", "ask-lead", open.length ? `${open.length} 題等你裁（各線已先照推薦往下走，答了再修正）` : "目前沒有要你裁的事"));
      if (offline) panel.append(el("p", "banner", "快照模式不能作答；開伺服器後到 http://127.0.0.1:8765/ 作答"));
      open.forEach(ask => panel.append(openCard(ask)));
      if (answered.length) { const history = details(panel, `已答 ${answered.length} 題`); answered.forEach(ask => history.append(answeredCard(ask))); }
      const ids = new Set(open.map(ask => ask.id));
      for (const id of drafts.keys()) if (!ids.has(id)) drafts.delete(id);
    }
  };
};
