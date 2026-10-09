/* Karbar Pulse assistant chat: renders a transcript of user/assistant bubbles and streams SSE answers. */
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
    if (html != null) e.innerHTML = html;
    return e;
  }
  function mdBold(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
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
    box.appendChild(d);
    var c = echarts.init(d);
    if (opt.tooltip) opt.tooltip.valueFormatter = function (v) { return v; };
    c.setOption(opt);
  }

  window.kpAsk = function (question, container) {
    question = (question || '').trim();
    if (!question) return;
    var t = thread(container);

    // user bubble
    var um = el('div', 'chat-msg user'); um.appendChild(el('div', 'chat-bubble', mdBold(question)));
    t.appendChild(um);

    // assistant bubble with typing indicator
    var am = el('div', 'chat-msg ai');
    var bubble = el('div', 'chat-bubble');
    var steps = el('div', 'chat-steps');
    var typing = el('div', 'typing'); typing.innerHTML = '<span></span><span></span><span></span>';
    var body = el('div');
    bubble.appendChild(steps); bubble.appendChild(typing); bubble.appendChild(body);
    am.appendChild(bubble); t.appendChild(am);
    scroll(container);

    var gotText = false;
    fetch('/assistant/stream/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf() },
      body: 'message=' + encodeURIComponent(question),
    }).then(function (resp) {
      if (!resp.ok || !resp.body) { typing.remove(); body.appendChild(el('p', null, 'Sorry — something went wrong.')); return; }
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf = '';
      function pump() {
        return reader.read().then(function (res) {
          if (res.done) { typing.remove(); return; }
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
              body.appendChild(el('p', null, mdBold(data.text)));
            } else if (ev === 'table') {
              renderTable(body, data);
            } else if (ev === 'chart') {
              renderChart(body, data);
            } else if (ev === 'sources') {
              var s = data.map(function (x) { return x.name + ' (as of ' + (x.as_of || '').slice(0, 16).replace('T', ' ') + ')'; }).join(' · ');
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
              typing.remove(); body.appendChild(el('p', null, data.message || 'Error.'));
            }
            scroll(container);
          });
          return pump();
        });
      }
      return pump();
    }).catch(function () { typing.remove(); body.appendChild(el('p', null, 'Sorry — the assistant is unavailable.')); });
  };
})();
