/* AI Pulse assistant chat: renders a transcript of user/assistant bubbles and streams SSE answers. */
(function () {
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    if (m) return m[1];
    var e = document.querySelector('[name=csrfmiddlewaretoken]');
    return e ? e.value : '';
  }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.textContent = html;
    return e;
  }
  function mdBold(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
  }
  function richText(tag, cls, text) {
    var node = el(tag, cls); node.innerHTML = mdBold(text); return node;
  }
  function thread(container) {
    var t = container.querySelector('.chat-thread');
    if (!t) { t = el('div', 'chat-thread'); container.appendChild(t); }
    return t;
  }
  function scroll(container) {
    var s = container.closest('[data-chat-scroll]') || container;
    s.scrollTop = s.scrollHeight;
  }
  function renderTable(box, t) {
    var wrap = el('div', 'card card-pad'); wrap.style.marginTop = '8px'; wrap.style.overflowX = 'auto';
    var tbl = el('table', 'tbl');
    var tr = el('tr'); t.columns.forEach(function (c) { tr.appendChild(el('th', null, c)); });
    var thead = el('thead'); thead.appendChild(tr); tbl.appendChild(thead);
    var tb = el('tbody');
    t.rows.forEach(function (row) {
      var r = el('tr'); row.forEach(function (c) { r.appendChild(el('td', null, c == null ? '' : String(c))); });
      tb.appendChild(r);
    });
    tbl.appendChild(tb); wrap.appendChild(tbl); box.appendChild(wrap);
  }
  function renderChart(box, opt) {
    if (!window.echarts) return;
    var d = el('div'); d.style.cssText = 'width:100%;height:220px;margin-top:8px;';
    d.dataset.chart = 'true';
    box.appendChild(d);
    var c = echarts.init(d);
    if (opt.tooltip) opt.tooltip.valueFormatter = function (v) { return v; };
    c.setOption(opt);
    var observer = new ResizeObserver(function () { if (!c.isDisposed()) c.resize(); else observer.disconnect(); });
    observer.observe(d);
  }

  window.kpAsk = function (question, container) {
    question = (question || '').trim();
    if (!question || !container || container.dataset.busy) return;
    container.dataset.busy = 'true';
    container.setAttribute('aria-busy', 'true');
    var scope = container.closest('.assistant-dialog, .assistant-canvas');
    var controls = scope ? Array.from(scope.querySelectorAll('.chat-composer button, .chip, .prompt-card')) : [];
    controls.forEach(function (button) { button.disabled = true; });
    var t = thread(container);

    // user bubble
    var um = el('div', 'chat-msg user'); um.appendChild(richText('div', 'chat-bubble', question));
    t.appendChild(um);

    // assistant bubble with typing indicator
    var am = el('div', 'chat-msg ai');
    var bubble = el('div', 'chat-bubble');
    var steps = el('div', 'chat-steps');
    var typing = el('div', 'typing'); typing.innerHTML = '<span></span><span></span><span></span>';
    typing.setAttribute('aria-label', 'Analyzing your order book');
    var body = el('div');
    bubble.appendChild(steps); bubble.appendChild(typing); bubble.appendChild(body);
    am.appendChild(bubble); t.appendChild(am);
    scroll(container);

    var gotText = false;
    var gotError = false;
    function failed(message) {
      if (gotError) return;
      gotError = true; typing.remove();
      body.appendChild(el('p', null, message));
      var retry = el('button', 'btn', 'Try again');
      retry.onclick = function () { if (!container.dataset.busy) { retry.disabled = true; window.kpAsk(question, container); } };
      body.appendChild(retry);
    }
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 90000);
    fetch('/assistant/stream/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf() },
      body: 'message=' + encodeURIComponent(question),
      signal: controller.signal,
    }).then(function (resp) {
      if (!resp.ok || !resp.body || !(resp.headers.get('content-type') || '').includes('text/event-stream')) { failed('We could not load an answer. Please check your connection or sign in again.'); return; }
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf = '';
      function pump() {
        return reader.read().then(function (res) {
          if (res.done) { typing.remove(); if (!gotText && !gotError) failed('The answer was interrupted. Please try again.'); return; }
          buf += dec.decode(res.value, { stream: true });
          var parts = buf.split('\n\n'); buf = parts.pop();
          parts.forEach(function (chunk) {
            var ev = (chunk.match(/^event: (.*)$/m) || [])[1];
            var dm = chunk.match(/^data: (.*)$/m);
            if (!ev || !dm) return;
            var data = JSON.parse(dm[1]);
            if (ev === 'step') {
              steps.appendChild(el('div', 'done', data.label));
            } else if (ev === 'delta') {
              if (!gotText) { typing.remove(); gotText = true; }
              body.appendChild(richText('p', null, data.text));
            } else if (ev === 'table') {
              renderTable(body, data);
            } else if (ev === 'chart') {
              renderChart(body, data);
            } else if (ev === 'sources') {
              var s = data.map(function (x) {
                var date = new Date(x.as_of);
                var stamp = !isNaN(date) ? new Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Dhaka',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(date) + ' Dhaka' : 'unknown time';
                return x.name + ' (as of ' + stamp + ')';
              }).join(' · ');
              body.appendChild(el('div', 'chat-sources', 'Sources: ' + s));
            } else if (ev === 'followups') {
              var fu = el('div'); fu.style.cssText = 'margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;';
              data.forEach(function (f) {
                var b = el('button', 'chip', f);
                b.onclick = function () { window.kpAsk(f, container); };
                fu.appendChild(b);
              });
              body.appendChild(fu);
            } else if (ev === 'error') {
              failed(data.message || 'We could not complete this answer.');
            }
            scroll(container);
          });
          return pump();
        });
      }
      return pump();
    }).catch(function () { failed('The assistant could not be reached. Please try again.'); })
      .finally(function () {
        clearTimeout(timeout); delete container.dataset.busy; container.setAttribute('aria-busy', 'false');
        controls.forEach(function (button) { button.disabled = false; }); scroll(container);
      });
  };
})();
