"use strict";
(() => {
  const form = document.getElementById("issue-form");
  const results = document.getElementById("results");
  const errBox = form.querySelector(".form-error");
  const routeBtn = document.getElementById("route-btn");
  let lastForm = null;
  let lastRoute = null;

  const EXAMPLES = {
    heat: { zip: "06511", category: "housing", description: "My landlord has not fixed the heat in my apartment after repeated requests. I texted him three times over the past two weeks and the apartment is about 55 degrees at night.", outcome: "An inspection of my apartment and the heat repaired as soon as possible." },
    ssa: { zip: "06511", category: "benefits", description: "I applied for Social Security retirement benefits four months ago and have not received a decision. Calls to the national number end with long holds and no update.", outcome: "Help getting a status update and a decision on my application." },
    pothole: { zip: "06511", category: "transportation", description: "There is a large pothole on my residential street in New Haven that has been growing for a month. Cars swerve around it and a cyclist nearly fell yesterday.", outcome: "The pothole repaired." },
    school: { zip: "06519", category: "education", description: "My child has an IEP at a New Haven public school, but the speech therapy sessions listed in the plan have not happened since September.", outcome: "The missed services provided and a meeting with the special education team." },
  };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
  const fmtUsd = (x) => "$" + x.toFixed(x < 0.01 ? 5 : 4);

  // character counter
  form.querySelectorAll(".counter").forEach((c) => {
    const ta = form.elements[c.dataset.for];
    const upd = () => (c.textContent = `${ta.value.length} / ${ta.maxLength}`);
    ta.addEventListener("input", upd);
    upd();
  });

  document.addEventListener("click", (e) => {
    const ex = e.target.closest("[data-example]");
    if (!ex) return;
    const d = EXAMPLES[ex.dataset.example];
    for (const [k, v] of Object.entries(d)) form.elements[k].value = v;
    form.elements.description.dispatchEvent(new Event("input"));
    form.elements.name.focus();
  });

  function formData() {
    const o = {};
    for (const k of ["name", "zip", "category", "description", "outcome", "street", "extra"]) o[k] = form.elements[k].value.trim();
    return o;
  }

  function clientValidate(d) {
    if (!/^\d{5}$/.test(d.zip)) return "Please enter a valid 5-digit ZIP code.";
    if (!d.category) return "Please choose an issue category.";
    if (d.description.length < 20) return "Please describe the situation in at least a sentence.";
    if (d.outcome.length < 5) return "Please say what outcome you want.";
    return null;
  }

  async function post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({ error: "Unexpected server response." }));
    if (!r.ok) throw Object.assign(new Error(j.error || "Request failed"), { setup: j.setup });
    return j;
  }

  function loading(text) {
    const node = document.getElementById("tpl-loading").content.cloneNode(true);
    node.querySelector(".loading-text").textContent = text;
    return node;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.textContent = "";
    const d = formData();
    const msg = clientValidate(d);
    if (msg) { errBox.textContent = msg; return; }
    lastForm = d;
    routeBtn.disabled = true;
    results.setAttribute("aria-busy", "true");
    results.replaceChildren(loading("Checking your districts and asking the Routing Agent which office is responsible…"));
    try {
      lastRoute = await post("/api/route", d);
      renderRoute(lastRoute);
    } catch (err) {
      results.innerHTML = `<div class="alert ${err.setup ? "alert-setup" : "alert-danger"}" role="alert"><strong>${err.setup ? "Setup needed" : "We couldn't complete that"}:</strong> ${esc(err.message)}</div>`;
    } finally {
      routeBtn.disabled = false;
      results.setAttribute("aria-busy", "false");
    }
  });

  function contactRows(r) {
    const rows = [];
    if (r.role && r.kind === "official") rows.push(["Role", esc(r.role)]);
    if (r.phone) rows.push(["Phone", `<a href="tel:${esc(r.phone.replace(/[^\d+]/g, ""))}">${esc(r.phone)}</a>`]);
    if (r.email) rows.push(["Email", `<a href="mailto:${esc(r.email)}">${esc(r.email)}</a>`]);
    const cu = safeUrl(r.contact_url);
    if (cu) rows.push(["Contact", `<a href="${esc(cu)}" target="_blank" rel="noopener">Official contact page ↗</a>`]);
    if (r.address) rows.push(["Address", esc(r.address)]);
    if (r.complaint_process) rows.push(["How to file", esc(r.complaint_process)]);
    return rows.length ? `<dl class="contact-grid">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : "";
  }

  function provenance(r) {
    const src = safeUrl(r.source_url);
    const via = r.verified_via || (r.kind === "official" ? "Official dataset" : "Live official page");
    const snap = safeUrl(r.snapshot_url) ? ` · <a href="${esc(r.snapshot_url)}" target="_blank" rel="noopener">archived copy</a>` : "";
    const datasetName = { "congress-legislators": "unitedstates/congress-legislators", "cga-legislator-db": "CT General Assembly legislator database" }[r.source_id] || "";
    return `<div class="provenance"><span class="verified">✓ Verified record</span> · ${esc(via)}${datasetName ? " (" + esc(datasetName) + ")" : ""} ·
      ${src ? `<a href="${esc(src)}" target="_blank" rel="noopener">source</a>` : ""} · checked ${esc(r.date_checked || "")}${snap}</div>`;
  }

  function officeCard(r, tag, extraClass = "") {
    const limited = r.kind === "directory" ? `<p class="alert alert-warn" style="margin:8px 0">Limited coverage: Civic Compass does not have verified ${esc(r.level)} offices for your location yet, so this links to an official directory.</p>` : "";
    return `<article class="office ${extraClass}">
      <div class="office-top"><div><div class="tag">${esc(tag)}</div><h3>${esc(r.name)}</h3></div>
      <span class="badge lvl-${esc(r.level)}">${esc(r.level)}</span></div>
      ${r.handles ? `<p class="handles">${esc(r.handles)}</p>` : ""}${limited}
      ${contactRows(r)}${provenance(r)}</article>`;
  }

  function usageLine(usages) {
    const t = usages.reduce((a, u) => ({ calls: a.calls + 1, input: a.input + u.input_tokens, cached: a.cached + u.cached_tokens, output: a.output + u.output_tokens, cost: a.cost + u.cost_usd, lat: a.lat + u.latency_s }), { calls: 0, input: 0, cached: 0, output: 0, cost: 0, lat: 0 });
    return `${t.calls} gpt-6-luna call${t.calls > 1 ? "s" : ""} · ${t.input.toLocaleString()} input (${t.cached.toLocaleString()} cached) · ${t.output.toLocaleString()} output tokens · ${t.lat.toFixed(1)} s · est. ${fmtUsd(t.cost)}`;
  }

  function renderRoute(d) {
    const R = d.routing;
    const parts = [];
    if (R.emergency) parts.push(`<div class="alert alert-danger" role="alert"><strong>This may be urgent.</strong> If anyone is in immediate danger (gas smell, fire, carbon monoxide, no heat with a vulnerable person in freezing weather), call 911 or the relevant emergency line now. A letter is not the fastest route.</div>`);
    if (d.safety.injection_flags.length || R.injection_suspected) parts.push(`<div class="alert alert-info"><strong>Safety note:</strong> part of your text looked like instructions to the AI (${esc(d.safety.injection_flags.join("; ") || "flagged by the routing agent")}). We treated it only as a description; recommendations come from the verified directory.</div>`);
    if (R.needs_clarification && R.clarifying_question) parts.push(`<div class="alert alert-warn"><strong>One question to improve this result:</strong> ${esc(R.clarifying_question)}<br><span class="muted">Add your answer under “Add more detail” and run again.</span></div>`);
    for (const n of d.location.notes) parts.push(`<div class="alert alert-warn">${esc(n)}</div>`);

    const loc = d.location;
    const where = [loc.town, loc.states.join("/"), loc.method === "address" ? "matched by street address" : `ZIP ${loc.zip}`].filter(Boolean).join(" · ");
    parts.push(`<section class="card"><div class="route-head"><h2 style="margin:0">2 · Where this goes</h2><span class="level-pill">${esc(R.level)} government</span></div>
      <p class="summary"><strong>Your issue:</strong> ${esc(R.issue_summary)}</p><p class="muted" style="margin:4px 0 0">${esc(where)}</p>
      ${officeCard(d.primary, "Recommended office", "primary")}
      <div class="why"><strong>Why this office?</strong> ${esc(R.rationale)}</div>
      <ul class="checks">${d.safety.checks.map((c) => `<li class="ok">${esc(c)}</li>`).join("")}<li class="ok">Contact details come from the verified directory, not from the AI</li></ul>
    </section>`);

    const others = d.secondary.map((r) => officeCard(r, "Also relevant"));
    if (d.elected) others.push(officeCard(d.elected, "Your elected official (for escalation)"));
    if (others.length) parts.push(`<section class="card"><h2>Other offices that can help</h2><div class="sub-grid">${others.join("")}</div></section>`);

    // elected officials + ambiguity
    const off = d.officials.map((o) => `<li><strong>${esc(o.name)}</strong> — ${esc(o.role)}${o.party ? ` (${esc(o.party)})` : ""}</li>`).join("");
    const poss = Object.entries(d.possible_officials).map(([k, list]) => `<li><strong>${esc(k)}:</strong> one of ${list.map((o) => esc(o.name)).join(", ") || "—"}</li>`).join("");
    if (off || poss) parts.push(`<section class="card"><h2>Your elected officials</h2>
      ${off ? `<ul class="officials-list">${off}</ul>` : ""}
      ${d.coverage_gaps.length ? `<div class="alert alert-warn" style="margin-top:12px"><strong>We won't guess.</strong> ${esc(d.coverage_gaps.join(" "))} Add your street address under “Add more detail” to identify your exact representatives.<ul class="officials-list">${poss}</ul></div>` : ""}
    </section>`);

    // letter step
    const recips = [d.primary, ...d.secondary, ...(d.elected ? [d.elected] : [])];
    parts.push(`<section class="card" id="letter-card"><h2>3 · Draft a letter</h2>
      <p class="muted">Choose who the letter is addressed to. The Letter-Writing Agent uses only the facts you entered.</p>
      <div class="recipient-choice" role="radiogroup" aria-label="Letter recipient">
        ${recips.map((r, i) => `<label><input type="radio" name="recipient" value="${esc(r.id)}" ${i === 0 ? "checked" : ""}> <span><strong>${esc(r.name)}</strong> <span class="muted">· ${esc(r.level)}</span></span></label>`).join("")}
      </div>
      <button class="btn navy" type="button" id="letter-btn">Draft my letter</button>
      <div id="letter-out"></div>
      <p class="usage">Routing: ${usageLine(d.usage)} · directory lookup ${d.timing.lookup_s}s · ${d.candidate_count} verified candidates considered</p>
    </section>`);
    results.innerHTML = parts.join("");
    document.getElementById("letter-btn").addEventListener("click", draftLetter);
    results.querySelector(".card").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function draftLetter() {
    const btn = document.getElementById("letter-btn");
    const out = document.getElementById("letter-out");
    const recipient_id = results.querySelector("input[name=recipient]:checked")?.value;
    btn.disabled = true;
    out.replaceChildren(loading("The Letter-Writing Agent is drafting, then the safety checker reviews it…"));
    try {
      const L = await post("/api/letter", { ...lastForm, run_id: lastRoute.run_id, recipient_id });
      renderLetter(L);
    } catch (err) {
      out.innerHTML = `<div class="alert alert-danger" role="alert">${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  }

  function renderLetter(L) {
    const out = document.getElementById("letter-out");
    const s = L.safety;
    const checks = [];
    if (s.removed_instruction_sentences) checks.push(`<li class="warn">${s.removed_instruction_sentences} sentence(s) that read like instructions to the AI were left out of the letter</li>`);
    if (!s.initial_issues.length) checks.push(`<li class="ok">No invented contact details, legal citations or “must respond” claims found</li>`);
    else {
      checks.push(`<li class="warn">The first draft had ${s.initial_issues.length} issue(s): ${esc(s.initial_issues.map((i) => i.detail).join("; "))}</li>`);
      if (s.repaired) checks.push(`<li class="${s.remaining_issues.length ? "warn" : "ok"}">Automatically revised once${s.remaining_issues.length ? "" : " — all issues resolved"}</li>`);
    }
    for (const i of s.remaining_issues) checks.push(`<li class="warn">Please check: ${esc(i.detail)}${i.type === "unverified_contact" ? " (removed)" : ""}</li>`);
    const ph = (L.letter.match(/\[[^\]]{2,60}\]/g) || []);
    if (ph.length) checks.push(`<li class="warn">Fill in ${ph.length} bracketed placeholder(s), e.g. ${esc([...new Set(ph)].slice(0, 3).join(", "))}</li>`);
    const cu = safeUrl(L.recipient.contact_url);
    out.innerHTML = `
      <label for="letter-text" style="margin-top:16px">Your letter (edit freely)</label>
      <textarea id="letter-text" spellcheck="true">${esc(L.letter)}</textarea>
      <ul class="checks" aria-label="Automatic checks">${checks.join("")}</ul>
      <label class="review-row"><input type="checkbox" id="reviewed"> I have read this letter, corrected anything inaccurate, and filled in the placeholders. I understand Civic Compass does not send it.</label>
      <div class="actions">
        <button class="btn navy" type="button" id="copy-btn" disabled>Copy letter</button>
        <button class="btn" type="button" id="dl-btn" disabled>Download .txt</button>
        ${cu ? `<a class="btn" href="${esc(cu)}" target="_blank" rel="noopener">Open ${esc(L.recipient.name)} contact page ↗</a>` : ""}
      </div>
      <p class="usage">Letter: ${usageLine(L.usage)}</p>`;
    const reviewed = document.getElementById("reviewed");
    const copyBtn = document.getElementById("copy-btn");
    const dlBtn = document.getElementById("dl-btn");
    reviewed.addEventListener("change", () => { copyBtn.disabled = dlBtn.disabled = !reviewed.checked; });
    copyBtn.addEventListener("click", async () => {
      const text = document.getElementById("letter-text").value;
      try { await navigator.clipboard.writeText(text); toast("Letter copied to clipboard"); }
      catch { document.getElementById("letter-text").select(); document.execCommand("copy"); toast("Letter copied"); }
    });
    dlBtn.addEventListener("click", () => {
      const blob = new Blob([document.getElementById("letter-text").value], { type: "text/plain" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "civic-compass-letter.txt" });
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
  }

  function toast(msg) {
    const t = Object.assign(document.createElement("div"), { className: "toast", role: "status", textContent: msg });
    document.body.append(t);
    setTimeout(() => t.remove(), 2200);
  }
})();
