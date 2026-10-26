/* HANGAR page script.
 *
 * Reads the inlined payload and renders. The page makes no data requests of its
 * own - network traffic is libraries and geography only: map tiles, the globe's
 * coastline file, CDN scripts and web fonts. That is what lets a refresh job
 * and the page be completely decoupled.
 */
(function () {
  "use strict";

  var D = JSON.parse(document.getElementById("payload").textContent);
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function fmt(n) {
    if (n == null) return "—";
    return Number(n).toLocaleString("en-US");
  }

  function timeAgo(iso) {
    if (!iso) return "";
    var mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    if (mins < 1440) return Math.floor(mins / 60) + "h ago";
    return Math.floor(mins / 1440) + "d ago";
  }

  function shortDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d)) return String(iso).slice(0, 10);
    return d.toISOString().slice(0, 16).replace("T", " ") + "Z";
  }

  /* ---------- the precision clock -------------------------------------
   * The signature of this page. Launch Library reports how precisely a NET
   * date is actually known, and the clock never displays finer resolution
   * than the data supports: a month-precision NET does not get a seconds
   * readout it cannot justify. Derated units are shown but visibly dimmed,
   * so the reader sees the uncertainty rather than a false countdown.
   */
  var PRECISION_FLOOR = {
    second: 0, minute: 1, hour: 2, day: 3, month: 3, quarter: 3, year: 3
  };

  function precisionRank(abbrev) {
    var a = String(abbrev || "").toLowerCase();
    if (a.indexOf("sec") === 0) return PRECISION_FLOOR.second;
    if (a.indexOf("min") === 0) return PRECISION_FLOOR.minute;
    if (a.indexOf("hour") === 0 || a === "hr") return PRECISION_FLOOR.hour;
    if (a.indexOf("day") === 0) return PRECISION_FLOOR.day;
    if (a.indexOf("month") === 0 || a.indexOf("mo") === 0) return PRECISION_FLOOR.month;
    if (a.indexOf("q") === 0) return PRECISION_FLOOR.quarter;
    if (a.indexOf("year") === 0 || a.indexOf("yr") === 0) return PRECISION_FLOOR.year;
    return 1;
  }

  var PRECISION_TEXT = {
    0: "Every digit is live — this launch time is known to the second.",
    1: "Seconds are dimmed — this launch time is only known to the minute.",
    2: "Minutes and seconds are dimmed — this time is only known to the hour.",
    3: "Only the day is meaningful — the date itself is provisional. Read this as a horizon, not a countdown."
  };

  function renderClock() {
    var lp = D.launches, host = $("clock"), pre = $("precision"), mission = $("mission");
    if (!lp || !lp.next) {
      $("clock-label").textContent = "No launch data";
      host.appendChild(el("div", "", "—"));
      pre.textContent = "Launch Library did not return a next launch. The panel is showing cached or empty data; see source status in the footer.";
      return;
    }
    var L = lp.next;
    var rank = precisionRank(L.net_precision);
    var units = [
      { u: "days", k: 86400000 },
      { u: "hrs", k: 3600000 },
      { u: "min", k: 60000 },
      { u: "sec", k: 1000 }
    ];

    var nodes = units.map(function (spec, i) {
      var wrap = el("div", "unit" + (i > (3 - rank) + 0 && rank > 0 && i >= 4 - rank ? "" : ""));
      wrap.className = "unit" + (i >= 4 - rank ? " derated" : "");
      var n = el("div", "n", "--");
      var u = el("div", "u", spec.u);
      wrap.appendChild(n); wrap.appendChild(u);
      return { wrap: wrap, n: n, k: spec.k };
    });

    nodes.forEach(function (nd, i) {
      host.appendChild(nd.wrap);
      if (i < nodes.length - 1) host.appendChild(el("div", "sep", ":"));
    });

    function tick() {
      var target = new Date(L.net).getTime();
      var diff = target - Date.now();
      var past = diff < 0;
      diff = Math.abs(diff);
      $("clock-label").textContent = past ? "Launched / in progress — T plus" : "Next launch — T minus";
      var rem = diff;
      nodes.forEach(function (nd) {
        var v = Math.floor(rem / nd.k);
        rem -= v * nd.k;
        nd.n.textContent = String(v).padStart(2, "0");
      });

      // The final-24-hours bar drains toward T-0. Shown only when the NET is
      // known to the minute or better - draining a bar toward a date that is
      // only good to the day would be exactly the false precision the clock
      // refuses elsewhere.
      var win = $("window");
      if (!past && diff < 86400000 && rank <= 1) {
        win.hidden = false;
        $("window-fill").style.width = (diff / 86400000 * 100).toFixed(2) + "%";
        $("window-label").textContent = "final 24 h · " + Math.round(diff / 864000) + "% remaining";
      } else {
        win.hidden = true;
      }
    }
    tick();
    // Ticking every second is honest only when the data resolves to seconds.
    setInterval(tick, rank === 0 || rank === 1 ? 1000 : 30000);

    pre.innerHTML = "";
    pre.appendChild(el("span", "", PRECISION_TEXT[rank] || PRECISION_TEXT[1]));
    pre.appendChild(document.createElement("br"));
    var b = el("b", "", "NET " + shortDate(L.net) + " · precision: " + (L.net_precision || "unknown"));
    pre.appendChild(b);

    var h2 = el("h2", "", L.name || "—");
    mission.appendChild(h2);
    var meta = el("div", "meta");
    function row(k, v) {
      if (!v) return;
      var d = el("div");
      d.appendChild(el("span", "", k + "  "));
      d.appendChild(document.createTextNode(v));
      meta.appendChild(d);
    }
    var st = el("div");
    var tag = el("span", "tag " + (String(L.status || "").toLowerCase().indexOf("go") >= 0 ? "go" : ""), L.status_name || L.status || "status unknown");
    st.appendChild(tag);
    if (L.webcast_live) {
      var live = el("a", "tag go pulse", "webcast live");
      if (L.url) { live.href = L.url; live.target = "_blank"; live.rel = "noopener"; }
      st.appendChild(live);
    }
    meta.appendChild(st);
    row("VEHICLE", L.rocket);
    row("PAD", L.pad);
    row("SITE", L.pad_location);
    row("ORBIT", L.orbit);
    row("PROVIDER", L.provider);
    mission.appendChild(meta);
  }

  /* ---------- stat rail ------------------------------------------------ */

  /* A point-in-time number is close to meaningless on this page: "11,086
   * satellites" says nothing without whether that is up 200 this year or up
   * 3,000. Every tile therefore carries its own history - a sparkline and the
   * change over the series - or states plainly that it has none yet.
   */
  // Minimum relative range a sparkline will zoom to. Pure min-max scaling turns
  // a 0.04% wobble into a full-height climb: 11,086 -> 11,090 satellites would
  // render as dramatic growth. Below this threshold the line is drawn against a
  // padded band instead, so a flat metric looks flat.
  var SPARK_MIN_RANGE = 0.02;

  function sparkline(values, w, h) {
    w = w || 108; h = h || 26;
    if (!values || values.length < 2) return null;
    var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    var mid = (hi + lo) / 2 || 1;
    var floorSpan = Math.abs(mid) * SPARK_MIN_RANGE;
    if (hi - lo < floorSpan) {
      lo = mid - floorSpan / 2;
      hi = mid + floorSpan / 2;
    }
    var span = (hi - lo) || 1;
    var pts = values.map(function (v, i) {
      return (i / (values.length - 1) * (w - 2) + 1).toFixed(1) + "," +
        (h - 1 - ((v - lo) / span) * (h - 2)).toFixed(1);
    }).join(" ");
    var svg = svgEl("svg", {
      viewBox: "0 0 " + w + " " + h, width: w, height: h,
      preserveAspectRatio: "xMidYMid meet", class: "spark", "aria-hidden": "true"
    });
    svg.appendChild(svgEl("polyline", {
      points: pts, fill: "none", stroke: "currentColor", "stroke-width": "1.5",
      "stroke-linejoin": "round", "stroke-linecap": "round"
    }));
    var last = values[values.length - 1];
    svg.appendChild(svgEl("circle", {
      cx: (w - 1).toFixed(1),
      cy: (h - 1 - ((last - lo) / span) * (h - 2)).toFixed(1),
      r: 2, fill: "currentColor"
    }));
    return svg;
  }

  function stat(value, key, note, trend) {
    var s = el("div", "stat");
    s.appendChild(el("div", "v", value));
    s.appendChild(el("div", "k", key));

    if (trend && trend.values && trend.values.length > 1) {
      var spark = sparkline(trend.values);
      var row = el("div", "trend");
      if (spark) row.appendChild(spark);
      var v = trend.values;
      var d;

      // A first-to-last delta means "growth" only on a series that accumulates.
      // On a fluctuating rate it compares two arbitrary months and invents a
      // trend: SpaceX's monthly launch share reads 63, 50, 36, 52, 48, 48, 54,
      // which is noise around ~50 - but first-to-last renders it as "-9, -16%".
      // Fluctuating series therefore show their range and a median, with no
      // direction implied and no up/down colour.
      if (trend.kind === "fluctuating") {
        var sorted = v.slice().sort(function (a, b) { return a - b; });
        var med = sorted.length % 2
          ? sorted[(sorted.length - 1) / 2]
          : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
        d = el("span", "delta flat");
        d.textContent = fmt(Math.round(sorted[0])) + "–" + fmt(Math.round(sorted[sorted.length - 1])) +
          (trend.unit || "") + ", med " + fmt(Math.round(med)) + (trend.unit || "");
      } else {
        var delta = v[v.length - 1] - v[0];
        var pct = v[0] ? (delta / Math.abs(v[0])) * 100 : null;
        d = el("span", "delta " + (delta >= 0 ? "up" : "down"));
        d.textContent = (delta >= 0 ? "+" : "−") + fmt(Math.abs(Math.round(delta))) +
          (pct !== null && Math.abs(pct) < 10000 ? " (" + (delta >= 0 ? "+" : "−") +
            Math.abs(pct).toFixed(0) + "%)" : "");
      }
      row.appendChild(d);
      s.appendChild(row);
      if (trend.span) {
        var sp = el("div", "note", trend.span);
        s.appendChild(sp);
      }
    } else if (trend && trend.none) {
      s.appendChild(el("div", "note nohist", trend.none));
    }

    if (note) s.appendChild(el("div", "note", note));
    return s;
  }

  // A metric the ledger has only just started measuring gets an honest note
  // rather than a flat line implying nothing has changed.
  function measured(key) {
    var s = D.history && D.history.series && D.history.series[key];
    if (!s || s.n < 2) {
      return { none: "measuring from " + ((s && s.first) || "today") };
    }
    return {
      values: s.points.map(function (p) { return p.v; }),
      span: "since " + s.first
    };
  }

  function renderRail() {
    var rail = $("rail"), lp = D.launches, c = D.constellation, f = D.financials;

    if (c) {
      var by = c.by_launch_year;
      rail.appendChild(stat(fmt(c.in_orbit), "Starlink in orbit",
        "median " + (c.altitude_median_km || "—") + " km",
        by && by.cumulative.length > 1
          ? { values: by.cumulative, span: by.years[0] + "–" + by.years[by.years.length - 1] }
          : measured("starlink_in_orbit")));
    }

    if (lp) {
      rail.appendChild(stat(fmt(lp.astronauts_count), "People in space",
        (lp.passengers && lp.passengers.length) ? "+ Starman, not a person" : null,
        measured("people_in_space")));

      var cad = lp.cadence;
      var m = (D.board && D.board.metrics) || {};
      if (m.spacex_launches_per_month && cad && cad.spacex.length > 1) {
        // Drop the incomplete current month so the last point is not a dip.
        var sx = [], oth = [], lab = [];
        cad.spacex.forEach(function (v, i) {
          if (cad.partial && cad.partial[i]) return;
          sx.push(v); oth.push(cad.other[i]); lab.push(cad.labels[i]);
        });
        rail.appendChild(stat(m.spacex_launches_per_month, "SpaceX launches / month",
          "trailing average, complete months",
          sx.length > 1 ? { values: sx, kind: "fluctuating",
            span: lab[0] + "–" + lab[lab.length - 1] } : null));

        if (lp.totals && lp.totals.spacex_share != null) {
          var share = sx.map(function (v, i) {
            var tot = v + oth[i];
            return tot ? Math.round((v / tot) * 100) : 0;
          });
          var win = lp.totals.window;
          rail.appendChild(stat(Math.round(lp.totals.spacex_share * 100) + "%",
            "share of recent launches",
            fmt(lp.totals.previous_sampled) + " launches" +
              (win ? ", " + win.from + " to " + win.to : "") + " — rolling window",
            share.length > 1 ? { values: share, kind: "fluctuating", unit: "%",
              span: "monthly share, " + lab.length + " complete months" } : null));
        }
      }
    }

    var sc = (D.sites || {}).superchargers;
    if (sc && sc.open_sites) {
      var g = sc.growth;
      rail.appendChild(stat(fmt(sc.open_sites), "Supercharger sites",
        fmt(sc.total_stalls) + " stalls open",
        g && g.cumulative.length > 1
          ? { values: g.cumulative, span: g.years[0] + "–" + g.years[g.years.length - 1] }
          : measured("supercharger_sites")));
    }

    if (f && f.quotes) {
      Object.keys(f.quotes).forEach(function (sym) {
        var q = f.quotes[sym];
        rail.appendChild(stat(q.price, sym,
          (q.change_pct >= 0 ? "+" : "") + q.change_pct + "% today",
          q.series && q.series.length > 1
            ? { values: q.series, span: "1-year change" } : null));
      });
    }
  }

  /* ---------- the commitments board ------------------------------------ */

  // "4810d left" is a number nobody converts in their head. Long horizons read
  // in years, near ones in days, because that is how each is actually thought about.
  function humanDays(d) {
    if (d == null) return "";
    var late = d < 0, n = Math.abs(d);
    var txt = n < 60 ? n + "d"
      : n < 730 ? Math.round(n / 30.44) + " mo"
        : (n / 365.25).toFixed(1) + " yr";
    return txt + (late ? " late" : " left");
  }

  var STATE_LABEL = {
    missed: "MISSED", "due-soon": "DUE SOON", open: "OPEN", met: "MET", unmeasured: "UNMEASURED"
  };

  function renderBoard() {
    var host = $("board-body"), B = D.board;
    if (!B) return;

    $("board-n").textContent =
      B.tracked.length + " tracked · " + B.claims_total + " claimed";

    var intro = el("p", "");
    intro.style.cssText = "max-width:70ch;color:var(--ink-2);margin:0 0 1.2rem;font-size:0.88rem";
    intro.textContent = "Stated ambition against measured reality. TRACKED rows are curated and carry a source plus a live metric, so status is computed. CLAIMED rows are detected automatically from headlines — they are what somebody said, cited and linked, not verified facts.";
    host.appendChild(intro);
    var hz = horizonChart(B);
    if (hz) host.appendChild(hz);

    if (B.tracked.length) {
      var t = el("div", "col");
      t.appendChild(el("h3", "", "Tracked"));
      var rack = el("div", "rack");
      B.tracked.forEach(function (r, i) {
        var a = el("a", "strip");
        a.style.setProperty("--i", i);
        if (r.source_url) a.href = r.source_url;
        a.appendChild(el("div", "when", r.target_date || "no date"));
        var what = el("div", "what");
        what.textContent = r.statement;
        var badge = el("span", "badge", STATE_LABEL[r.state] || r.state);
        what.appendChild(badge);
        a.appendChild(what);
        a.appendChild(el("div", "who",
          (r.progress != null ? Math.round(r.progress * 100) + "% · " : "") +
          humanDays(r.days_left)));
        rack.appendChild(a);
      });
      t.appendChild(rack);
      host.appendChild(t);
    } else {
      var empty = el("div", "");
      empty.style.cssText = "border-left:3px solid var(--sodium);background:var(--strip);padding:0.9rem 1rem;margin-bottom:1.4rem;font-size:0.88rem;color:var(--ink-2)";
      empty.innerHTML = "<b style='color:var(--ink)'>No tracked targets yet.</b><br>" +
        "<code style='font-family:var(--mono);font-size:0.8rem'>data/targets.json</code> is an empty register. " +
        "It is deliberately not seeded from recollection — every row needs a real source URL and the date the statement was made. " +
        "The CLAIMED lane below fills itself and needs no maintenance.";
      host.appendChild(empty);
    }

    // Claims, newest first.
    var c = el("div", "col");
    var head = el("h3", "", "Claimed — auto-detected from headlines");
    c.appendChild(head);

    var rate = el("div", "");
    rate.style.cssText = "font-family:var(--mono);font-size:0.68rem;color:var(--ink-muted);margin:-0.2rem 0 0.35rem";
    rate.textContent = B.claims_total + " kept" +
      (B.corpus_size ? " · " + (100 * B.claims_total / B.corpus_size).toFixed(1) +
        "% of " + fmt(B.corpus_size) + " headlines matched" : "") +
      " · regex detection, precision and recall unmeasured — treat as leads, not facts";
    c.appendChild(rate);

    var x = B.x || {};
    var xnote = el("div", "");
    xnote.style.cssText = "font-family:var(--mono);font-size:0.68rem;color:var(--ink-muted);margin:-0.2rem 0 0.7rem";
    if (x.available) {
      xnote.textContent = "@" + (x.handle || "elonmusk") + " collected " + (x.age || "—") +
        (x.stale ? " — STALE, showing reported claims only" : " — primary-source posts included");
      if (x.stale) xnote.style.color = "var(--hold)";
    } else {
      xnote.textContent = "X not collected (" + (x.reason || "unavailable") + ") — every claim below is second-hand from news coverage.";
    }
    c.appendChild(xnote);

    var crack = el("div", "rack");
    (B.claims || []).forEach(function (r, i) {
      var a = el("a", "strip" + (r.topics && r.topics.length ? " t-" + r.topics[0] : ""));
      a.style.setProperty("--i", i);
      if (r.link) { a.href = r.link; a.target = "_blank"; a.rel = "noopener"; }
      a.appendChild(el("div", "when", r.horizon || r.horizon_phrase));
      var what = el("div", "what");
      what.textContent = r.statement;
      if (r.primary) what.appendChild(el("span", "badge", "primary"));
      if (r.quantity) what.appendChild(el("span", "badge", r.quantity));
      // times_seen counts refresh runs that still found the headline in a feed,
      // not separate reports, so the badge shows distinct outlets instead.
      if (r.outlets && r.outlets.length > 1) what.appendChild(el("span", "badge", r.outlets.length + " outlets"));
      a.appendChild(what);
      a.appendChild(el("div", "who", r.source || ""));
      crack.appendChild(a);
    });
    c.appendChild(crack);
    host.appendChild(c);
  }

  /* ---------- the promise horizon --------------------------------------
   * Every dated promise on one time axis, one lane per topic, with a NOW line.
   * Deadlines crowd into the next few months while a handful sit years out,
   * so the axis is square-root time: near-term stays legible and the far
   * points still fit. Tick labels carry the real dates.
   *
   * A deadline behind NOW is ringed red and says "deadline passed - outcome
   * unverified". It is never labelled missed: the page has no evidence either
   * way, and a promise can be kept without a headline saying so.
   */

  var TOPIC_LABEL = {
    starship: "Starship", starlink: "Starlink", launch: "Launch", optimus: "Optimus",
    autonomy: "Autonomy", production: "Production", energy: "Energy",
    ai: "AI", neurotech: "Neurotech", tunnels: "Tunnels", regulatory: "Regulatory", money: "Money", other: "Other"
  };

  function horizonChart(B) {
    var today = new Date(D.meta.generated.slice(0, 10) + "T00:00:00Z");
    var pts = [];
    (B.tracked || []).forEach(function (r) {
      if (r.target_date) pts.push({ d: r.target_date, lane: "tracked", text: r.statement, link: r.source_url, tracked: true });
    });
    (B.claims || []).forEach(function (r) {
      if (!r.horizon) return;
      var t = (r.topics && r.topics[0]) || "other";
      pts.push({ d: r.horizon, lane: t, text: r.statement, link: r.link });
    });
    if (pts.length < 2) return null;

    var DAY = 86400000;
    var start = new Date(today.getTime() - 45 * DAY);
    var last = pts.reduce(function (m, p) { return p.d > m ? p.d : m; }, "");
    var endY = Math.min(2032, Math.max(today.getUTCFullYear() + 2, Number(last.slice(0, 4)) + 1));
    var end = new Date(Date.UTC(endY, 0, 1));
    var span = end - start;

    var lanes = [];
    if (pts.some(function (p) { return p.tracked; })) lanes.push("tracked");
    pts.forEach(function (p) { if (lanes.indexOf(p.lane) < 0) lanes.push(p.lane); });

    var W = 1200, LX = 110, RX = 16, LH = 30, TOP = 26;
    var H = TOP + lanes.length * LH + 30;
    function x(dt) {
      var f = Math.max(0, Math.min(1, (dt - start) / span));
      return LX + Math.sqrt(f) * (W - LX - RX);
    }

    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Promised deadlines on a time axis, one lane per topic" });

    // Year ticks, plus month ticks inside the first year where the axis is widest.
    var ticks = [];
    for (var m = 1; m <= 12; m += 1) {
      var md = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + m, 1));
      if (md.getUTCMonth() === 0) continue;
      if (m <= 6 && m % 2 === 1) ticks.push({ d: md, label: md.toISOString().slice(0, 7) });
    }
    for (var y = today.getUTCFullYear() + 1; y <= endY; y++) {
      ticks.push({ d: new Date(Date.UTC(y, 0, 1)), label: String(y) });
    }
    // Year ticks take priority; a month tick too close to any kept tick is
    // dropped rather than drawn over it.
    ticks.sort(function (a, b) { return (b.label.length === 4) - (a.label.length === 4); });
    var kept = [];
    ticks.forEach(function (t) {
      var tx = x(t.d);
      if (kept.some(function (k) { return Math.abs(k - tx) < 72; })) return;
      kept.push(tx);
      svg.appendChild(svgEl("line", { class: "tick", x1: tx, y1: TOP - 6, x2: tx, y2: H - 22 }));
      var lab = svgEl("text", { x: tx, y: H - 6, "text-anchor": "middle" });
      lab.textContent = t.label;
      svg.appendChild(lab);
    });

    lanes.forEach(function (ln, i) {
      var ly = TOP + i * LH + LH / 2;
      svg.appendChild(svgEl("line", { class: "lane", x1: LX, y1: ly, x2: W - RX, y2: ly }));
      var t = svgEl("text", { x: LX - 12, y: ly + 4, "text-anchor": "end" });
      t.textContent = ln === "tracked" ? "TRACKED" : (TOPIC_LABEL[ln] || ln).toUpperCase();
      if (ln === "tracked") t.setAttribute("fill", "var(--sodium)");
      svg.appendChild(t);
    });

    var nx = x(today);
    svg.appendChild(svgEl("line", { class: "now", x1: nx, y1: TOP - 10, x2: nx, y2: H - 22 }));
    var nl = svgEl("text", { class: "now-l", x: nx + 5, y: TOP - 12 });
    nl.textContent = "NOW";
    svg.appendChild(nl);

    // Several promises can share a lane and a deadline ("by end of 2027");
    // they fan out vertically rather than stacking invisibly on one point.
    var seen = {};
    var passed = 0;
    pts.forEach(function (p) {
      var dt = new Date(p.d + "T00:00:00Z");
      var li = lanes.indexOf(p.lane);
      var key = li + "|" + p.d;
      var k = seen[key] = (seen[key] || 0) + 1;
      var off = k === 1 ? 0 : (k % 2 ? 1 : -1) * Math.ceil((k - 1) / 2) * 6;
      var cx = x(dt), cy = TOP + li * LH + LH / 2 + off;
      var isPast = dt < today;
      if (isPast) passed++;
      var a = svgEl("a", p.link ? { href: p.link, target: "_blank", rel: "noopener" } : {});
      var colour = p.tracked ? "var(--sodium)" : "var(--t-" + p.lane + ", var(--ink-muted))";
      var mark = p.tracked
        ? svgEl("rect", { class: "pt", x: cx - 5, y: cy - 5, width: 10, height: 10,
            transform: "rotate(45 " + cx + " " + cy + ")", fill: colour })
        : svgEl("circle", { class: "pt" + (isPast ? " passed" : ""), cx: cx, cy: cy, r: 5.5, fill: colour });
      var title = svgEl("title", {});
      title.textContent = p.d + " — " + p.text + (isPast ? " (deadline passed — outcome unverified)" : "");
      mark.appendChild(title);
      a.appendChild(mark);
      svg.appendChild(a);
    });

    var wrap = el("div", "horizon hud");
    wrap.appendChild(el("h3", "", "Promise horizon"));
    wrap.firstChild.style.cssText = "font-family:var(--mono);font-size:0.66rem;letter-spacing:0.2em;text-transform:uppercase;color:var(--sodium);margin:0 0 0.6rem";
    wrap.appendChild(svg);
    wrap.appendChild(el("div", "cap",
      pts.length + " dated promises · square-root time axis · hover for the headline, click for the source" +
      (passed ? " · " + passed + " red-ringed: deadline passed, outcome unverified" : "")));
    return wrap;
  }

  /* ---------- charts ---------------------------------------------------
   * Hand-rolled SVG. No chart library: the payload is small, the shapes are
   * simple, and it keeps the page to one file with no CDN dependency beyond
   * map tiles.
   */

  function svgEl(tag, attrs) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  /* Charts use a real pixel-scale viewBox and uniform scaling.
   *
   * An earlier version used a 100-unit viewBox with preserveAspectRatio="none",
   * which stretched the SVG non-uniformly to fit its container - and stretched
   * the axis text with it, 14x horizontally, into an unreadable smear. Text in
   * an SVG must never be non-uniformly scaled.
   */
  var CW = 720, CH = 200, PAD_L = 34, PAD_R = 8, PAD_T = 10, PAD_B = 26;

  function axisFrame(labelText) {
    var svg = svgEl("svg", {
      class: "cadence", viewBox: "0 0 " + CW + " " + CH,
      preserveAspectRatio: "xMidYMid meet", role: "img"
    });
    svg.setAttribute("aria-label", labelText);
    return svg;
  }

  function niceMax(v) {
    if (v <= 0) return 1;
    var mag = Math.pow(10, Math.floor(Math.log10(v)));
    return Math.ceil(v / mag) * mag;
  }

  function barChart(labels, seriesA, seriesB, partial, nameA, nameB) {
    var n = labels.length || 1;
    var raw = 1;
    for (var i = 0; i < n; i++) raw = Math.max(raw, (seriesA[i] || 0) + (seriesB[i] || 0));
    var max = niceMax(raw);
    var plotW = CW - PAD_L - PAD_R, plotH = CH - PAD_T - PAD_B;
    var bw = plotW / n;

    var svg = axisFrame(nameA + " versus " + nameB + " by month");

    // Gridlines with values, so bar heights can be read rather than guessed.
    [0, 0.5, 1].forEach(function (f) {
      var y = PAD_T + plotH - f * plotH;
      svg.appendChild(svgEl("line", {
        class: "axis", x1: PAD_L, y1: y, x2: CW - PAD_R, y2: y,
        opacity: f === 0 ? 1 : 0.35
      }));
      var t = svgEl("text", { x: PAD_L - 6, y: y + 3, "text-anchor": "end" });
      t.textContent = Math.round(max * f);
      svg.appendChild(t);
    });

    for (var j = 0; j < n; j++) {
      var a = seriesA[j] || 0, b = seriesB[j] || 0;
      var ha = (a / max) * plotH, hb = (b / max) * plotH;
      var x = PAD_L + j * bw;
      var g = svgEl("g", (partial && partial[j]) ? { class: "partial" } : {});
      g.appendChild(svgEl("rect", {
        class: "bar-ot", x: x + bw * 0.15, y: PAD_T + plotH - hb, width: bw * 0.7, height: hb
      }));
      g.appendChild(svgEl("rect", {
        class: "bar-sx", x: x + bw * 0.15, y: PAD_T + plotH - hb - ha, width: bw * 0.7, height: ha
      }));
      var title = svgEl("title", {});
      title.textContent = labels[j] + " — " + nameA + " " + a + (nameB ? ", " + nameB + " " + b : "");
      g.appendChild(title);
      svg.appendChild(g);

      // Thin out labels so they never collide, whatever the series length.
      var every = Math.ceil(n / 12);
      if (j % every === 0) {
        var lab = svgEl("text", {
          x: x + bw / 2, y: CH - PAD_B + 14, "text-anchor": "middle"
        });
        lab.textContent = labels[j].length > 4 ? labels[j].slice(2) : labels[j];
        svg.appendChild(lab);
      }
    }
    return svg;
  }

  function lineChart(values, labelText, xLabels, zeroBase) {
    if (!values.length) return el("div", "", "no data");
    var plotW = CW - PAD_L - PAD_R, plotH = CH - PAD_T - PAD_B;
    var lo = zeroBase ? 0 : Math.min.apply(null, values);
    var hi = Math.max.apply(null, values);

    // Same guard as the sparklines: without a floor on the range, min-max
    // scaling renders a fraction of a percent of movement as a full-height
    // climb. Axis labels alone do not stop a reader trusting the shape.
    if (!zeroBase) {
      var mid = (hi + lo) / 2 || 1;
      var floorSpan = Math.abs(mid) * SPARK_MIN_RANGE;
      if (hi - lo < floorSpan) {
        lo = mid - floorSpan / 2;
        hi = mid + floorSpan / 2;
      }
    }
    var span = (hi - lo) || 1;

    var svg = axisFrame(labelText);

    [0, 0.5, 1].forEach(function (f) {
      var y = PAD_T + plotH - f * plotH;
      svg.appendChild(svgEl("line", {
        class: "axis", x1: PAD_L, y1: y, x2: CW - PAD_R, y2: y, opacity: f === 0 ? 1 : 0.35
      }));
      var t = svgEl("text", { x: PAD_L - 6, y: y + 3, "text-anchor": "end" });
      var v = lo + span * f;
      t.textContent = Math.abs(v) >= 1e9 ? (v / 1e9).toFixed(0) + "B"
        : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(0) + "M"
          : Math.abs(v) >= 1000 ? (v / 1000).toFixed(1) + "k" : Math.round(v);
      svg.appendChild(t);
    });

    var pts = values.map(function (v, i) {
      var x = PAD_L + (i / (values.length - 1 || 1)) * plotW;
      var y = PAD_T + plotH - ((v - lo) / span) * plotH;
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");

    svg.appendChild(svgEl("polyline", {
      points: pts, fill: "none", stroke: "var(--series-3)", "stroke-width": "2",
      "stroke-linejoin": "round"
    }));

    if (xLabels && xLabels.length === values.length) {
      var every = Math.ceil(values.length / 8);
      xLabels.forEach(function (lx, i) {
        if (i % every && i !== values.length - 1) return;
        var t = svgEl("text", {
          x: PAD_L + (i / (values.length - 1 || 1)) * plotW,
          y: CH - PAD_B + 14, "text-anchor": "middle"
        });
        t.textContent = lx;
        svg.appendChild(t);
      });
    }
    return svg;
  }

  function panel(title, node, note) {
    var p = el("div", "col hud");
    p.appendChild(el("h3", "", title));
    p.appendChild(node);
    if (note) {
      var d = el("div", "");
      d.style.cssText = "font-size:0.72rem;color:var(--ink-muted);margin-top:0.5rem;max-width:60ch";
      d.textContent = note;
      p.appendChild(d);
    }
    return p;
  }

  function renderGrowth() {
    var host = $("growth-body");
    var grid = el("div", "cols");
    var count = 0;

    var lp = D.launches;
    if (lp && lp.cadence && lp.cadence.labels.length) {
      var c = lp.cadence;
      var chart = barChart(c.labels, c.spacex, c.other, c.partial, "SpaceX", "All other providers");
      var wrap = el("div");
      wrap.appendChild(chart);
      var lg = el("div", "legend");
      lg.innerHTML = '<span><i style="background:var(--series-1)"></i>SpaceX</span>' +
        '<span><i style="background:var(--rule-bright)"></i>All others</span>' +
        '<span style="opacity:.5"><i style="background:var(--rule-bright)"></i>faded = incomplete month</span>';
      wrap.appendChild(lg);
      grid.appendChild(panel("Launch cadence, by month", wrap, c.note));
      count++;
    }

    var con = D.constellation;
    if (con && con.by_launch_year && con.by_launch_year.years.length) {
      var by = con.by_launch_year;
      var chart2 = barChart(by.years.map(String), by.cumulative, by.years.map(function () { return 0; }), null, "Cumulative", "");
      grid.appendChild(panel("Starlink fleet by launch year (cumulative)", chart2, by.caveat));
      count++;
    }

    var fin = D.financials;
    if (fin && fin.series && fin.series.revenue && fin.series.revenue.points.length) {
      var pts = fin.series.revenue.points;
      var vals = pts.map(function (p) { return p.value; });
      var node = el("div");
      node.appendChild(lineChart(vals, "Tesla quarterly revenue",
          pts.map(function (p) { return p.period.replace('-Q', 'Q'); }), true));
      var last = pts[pts.length - 1];
      var cap = el("div", "");
      cap.style.cssText = "font-family:var(--mono);font-size:0.72rem;color:var(--ink-2);margin-top:0.4rem";
      cap.textContent = pts[0].period + " → " + last.period + " · latest $" +
        (last.value / 1e9).toFixed(2) + "B";
      node.appendChild(cap);
      grid.appendChild(panel("Tesla quarterly revenue (SEC filed)", node,
        fin.series.revenue.derived_note));
      count++;
    }

    var hist = D.history && D.history.series;
    if (hist) {
      Object.keys(hist).forEach(function (k) {
        var s = hist[k];
        if (s.n < 2) return;
        var node = el("div");
        node.appendChild(lineChart(s.points.map(function (p) { return p.v; }), s.label,
          s.points.map(function (p) { return p.d.slice(5); }), false));
        grid.appendChild(panel(s.label + " (measured)", node,
          s.n + " observations since " + s.first));
        count++;
      });
      if (count && D.history.note) {
        var n = el("div", "");
        n.style.cssText = "font-size:0.72rem;color:var(--ink-muted);margin-top:1rem";
        n.textContent = D.history.note;
        host.appendChild(n);
      }
    }

    $("growth-n").textContent = count + " series";
    host.insertBefore(grid, host.firstChild);
  }

  /* ---------- manifest -------------------------------------------------- */

  function renderManifest() {
    var host = $("manifest-body"), lp = D.launches;
    if (!lp || !lp.upcoming) return;
    $("manifest-n").textContent = lp.upcoming.length + " scheduled";
    lp.upcoming.forEach(function (L, i) {
      var a = el("a", "strip" + (i === 0 ? " next" : ""));
      a.style.setProperty("--i", i);
      if (L.url) { a.href = L.url; a.target = "_blank"; a.rel = "noopener"; }
      a.appendChild(el("div", "when", shortDate(L.net)));
      var what = el("div", "what");
      what.textContent = L.name || "—";
      if (L.orbit) what.appendChild(el("span", "badge", L.orbit));
      if (L.net_precision && String(L.net_precision).toLowerCase().indexOf("min") !== 0) {
        what.appendChild(el("span", "badge", "±" + L.net_precision));
      }
      a.appendChild(what);
      a.appendChild(el("div", "who", L.provider || ""));
      host.appendChild(a);
    });
  }

  /* ---------- dispatch -------------------------------------------------- */

  function renderDispatch() {
    var host = $("dispatch-body"), news = D.news;
    if (!news || !news.sections) return;
    var total = 0;
    news.order.forEach(function (key) {
      var items = news.sections[key] || [];
      total += items.length;
      var col = el("div", "col");
      col.appendChild(el("h3", "", news.labels[key]));
      var rack = el("div", "rack");
      items.forEach(function (e, i) {
        var a = el("a", "strip" + (e.topics && e.topics.length ? " t-" + e.topics[0] : ""));
        a.style.setProperty("--i", i);
        a.href = e.link; a.target = "_blank"; a.rel = "noopener";
        a.style.gridTemplateColumns = "1fr";
        var what = el("div", "what");
        what.textContent = e.title;
        a.appendChild(what);
        var who = el("div", "who");
        who.style.textAlign = "left";
        who.textContent = (e.source || "") + " · " + timeAgo(e.published);
        a.appendChild(who);
        rack.appendChild(a);
      });
      col.appendChild(rack);
      host.appendChild(col);
    });
    $("dispatch-n").textContent = total + " stories";
  }

  /* ---------- map ------------------------------------------------------
   * Leaflet is loaded lazily, and only when the map scrolls into view, so a
   * reader who never reaches it makes no external request at all. Data is
   * embedded rather than fetched - the lifemap.html pattern from dads80th -
   * which is what makes this work from file:// as well as from Pages.
   */

  // Identity colours per company, shared by the range map and the globe. Shape
  // carries the kind of site (square facility, round pad); colour carries who
  // owns it. Identity only - never used to encode a value.
  var CO_COLOR = {
    "SpaceX": "#8bd3ff", "Tesla": "#ff8f6b", "xAI": "#d36be0", "X": "#f2d45c",
    "Neuralink": "#5fe0a0", "Boring Company": "#c0a878"
  };
  function coColor(co) { return CO_COLOR[co] || "#a3b0c0"; }

  function coLegend(facilities) {
    var seen = [];
    facilities.forEach(function (f) { if (seen.indexOf(f.co) < 0) seen.push(f.co); });
    return seen.map(function (co) {
      return '<span><i style="background:' + coColor(co) + '"></i>' + co + " facility</span>";
    }).join("");
  }

  function loadLeaflet(cb) {
    // Leaflet is a static tag in <head>; see the comment there for why. If it
    // failed to load - offline, or the CDN blocked - say so in the panel rather
    // than leaving a grey rectangle that looks like a broken map.
    if (window.L) return cb();
    $("map").innerHTML =
      '<div style="padding:1.5rem;font-family:var(--mono);font-size:0.8rem;color:var(--ink-muted)">' +
      "Map library did not load, so the map cannot draw. Pad, facility and " +
      "Supercharger data is present in this page and is listed above; only the " +
      "basemap needs a network connection.</div>";
  }

  function renderMap() {
    var lp = D.launches;
    var pads = (lp && lp.pads) || [];
    var st = D.sites || {};
    var facilities = st.facilities || [];
    var sc = st.superchargers || {};
    var clusters = sc.clusters || [];

    var counts = [];
    if (pads.length) counts.push(pads.length + " pads");
    if (facilities.length) counts.push(facilities.length + " facilities");
    if (sc.open_sites) counts.push(fmt(sc.open_sites) + " Supercharger sites");
    $("range-n").textContent = counts.join(" · ");
    if (!pads.length && !facilities.length && !clusters.length) return;

    var host = $("map");
    var built = false;

    function build() {
      if (built) return;
      built = true;
      loadLeaflet(function () {
        var map = L.map("map", { scrollWheelZoom: false }).setView([20, -40], 2);

        // Esri's grey canvas basemaps: keyless, and they come in a matched
        // light/dark pair so the map follows the page theme instead of sitting
        // in it like a hole. CARTO's dark_all now watermarks every tile with
        // "API KEY REQUIRED".
        //
        // Note the tile path is {z}/{y}/{x} on ArcGIS, not Leaflet's usual
        // {z}/{x}/{y} - swapping them silently returns the wrong part of the
        // world rather than an error.
        var ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/";
        var base = null;
        function paintBase() {
          var dark = document.documentElement.getAttribute("data-theme") !== "light";
          if (base) map.removeLayer(base);
          base = L.tileLayer(
            ESRI + "World_" + (dark ? "Dark" : "Light") + "_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            { maxZoom: 12, attribution: "&copy; Esri" }
          ).addTo(map);
          base.bringToBack();
        }
        paintBase();
        document.addEventListener("hangar:theme", paintBase);

        var sx = L.layerGroup().addTo(map);
        var other = L.layerGroup().addTo(map);
        var plants = L.layerGroup().addTo(map);
        var charging = L.layerGroup();

        pads.forEach(function (p) {
          var r = Math.max(4, Math.min(20, Math.sqrt(p.count) * 2.2));
          L.circleMarker([p.lat, p.lon], {
            radius: r,
            color: p.spacex ? "#ffa14a" : "#7d8894",
            weight: p.spacex ? 2 : 1,
            fillColor: p.spacex ? "#ffa14a" : "#4a5563",
            fillOpacity: p.spacex ? 0.45 : 0.3
          }).bindPopup(
            "<b>" + p.name + "</b><br>" + (p.location || "") +
            "<br>" + p.count + " launches sampled<br>" + (p.top_provider || "")
          ).addTo(p.spacex ? sx : other);
        });

        // Facilities are squares, pads are circles: shape carries the kind of
        // site, so colour is free to carry the company.
        facilities.forEach(function (f) {
          var building = f.status !== "operating";
          L.marker([f.lat, f.lon], {
            icon: L.divIcon({
              className: "",
              iconSize: [11, 11],
              html: '<div style="width:11px;height:11px;background:' +
                (building ? "transparent" : coColor(f.co)) +
                ";border:2px solid " + coColor(f.co) +
                (building ? ";border-style:dashed" : "") + '"></div>'
            })
          }).bindPopup(
            "<b>" + f.name + "</b><br>" + f.co + " — " + f.kind +
            "<br><i>" + f.status + "</i>"
          ).addTo(plants);
        });

        clusters.forEach(function (c) {
          L.circleMarker([c.lat, c.lon], {
            radius: Math.max(3, Math.min(22, Math.sqrt(c.sites) * 1.6)),
            color: "#35b8a8", weight: 1, fillColor: "#35b8a8", fillOpacity: 0.22
          }).bindPopup(
            "<b>" + fmt(c.sites) + " Supercharger sites</b><br>" +
            fmt(c.stalls) + " stalls<br>" + (c.regions || []).join(", ")
          ).addTo(charging);
        });

        L.control.layers(null, {
          "SpaceX pads": sx,
          "Other providers": other,
          "Factories &amp; plants": plants,
          "Superchargers": charging
        }, { collapsed: false }).addTo(map);

        var pts = pads.map(function (p) { return [p.lat, p.lon]; })
          .concat(facilities.map(function (f) { return [f.lat, f.lon]; }));
        if (pts.length) map.fitBounds(pts, { padding: [30, 30] });
      });
    }

    // Build when the map comes within a screen of the viewport. This started as
    // an IntersectionObserver, which proved unreliable here - it silently never
    // fired on a reload that restored scroll position, leaving an empty grey
    // box and no error. An explicit distance check is duller and it always runs.
    function maybeBuild() {
      if (built) return;
      var r = host.getBoundingClientRect();
      if (r.top < window.innerHeight * 2 && r.bottom > -window.innerHeight) {
        build();
        window.removeEventListener("scroll", maybeBuild);
        window.removeEventListener("resize", maybeBuild);
      }
    }
    window.addEventListener("scroll", maybeBuild, { passive: true });
    window.addEventListener("resize", maybeBuild);
    maybeBuild();

    $("map-legend").innerHTML =
      '<span><i style="background:#ffa14a;border-radius:50%"></i>SpaceX pad</span>' +
      '<span><i style="background:#4a5563;border-radius:50%"></i>Other provider</span>' +
      coLegend(facilities) +
      '<span><i style="background:transparent;border:1px dashed var(--ink-2)"></i>under construction</span>' +
      '<span><i style="background:#35b8a8;border-radius:50%"></i>Superchargers (clustered)</span>' +
      '<span>Circle area &#8733; count</span>' +
      (sc.note ? '<span style="flex-basis:100%;opacity:.75">' + sc.note + '</span>' : "");
  }

  /* ---------- the globe ------------------------------------------------
   * Orthographic Earth with launch pads and factories on the surface, the next
   * launch pad ringed, and every payload in Earth orbit flying over it.
   *
   * It opens as a time-lapse, Sputnik 1 to today: each launch rises from its
   * site, its satellites join the sky, and decayed ones drop out on their decay
   * date. At the present it hands over to the live globe.
   *
   * Data is fetched from the page's own origin, not inlined (decisions/0001):
   * orbits.json is every Earth-orbit payload (SATCAT + GCAT) and fleet.json the
   * element sets of operating satellites. The page then tries CelesTrak live for
   * fresher elements and keeps the committed copy if that fails.
   *
   * Positions are two-body motion plus the J2 drift of node and perigee - not
   * SGP4; drag and higher harmonics are ignored. Satellites without element sets
   * (decayed or defunct) fly their real inclination, apogee and perigee with a
   * synthetic node and phase, so historical positions are illustrative. The
   * caption says both.
   */

  var LAND_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json";
  var LIVE_GP = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json";
  var MU = 398600.4418, RE = 6378.137, R_MEAN = 6371, J2 = 1.08263e-3;
  var RAD = Math.PI / 180, TWO_PI = 2 * Math.PI, DAY = 86400000;

  var TL_START = Date.UTC(1957, 9, 4);  // Sputnik 1
  var TL_SECONDS = 105;                 // 1957 to today at x1, about 1.5 s a year
  var STREAK_MS = 600;                  // a launch streak lasts this long on screen

  // Owner group -> colour token. Only three hues stay distinguishable when every
  // colour can sit beside every other (the dataviz validator, both themes), so
  // three groups get a hue and the rest are neutral; the tooltip names them.
  // SpaceX keeps the series-1 it has in the cadence chart.
  var GROUP_TOKEN = { "SpaceX": "series-1", "US": "series-2", "USSR / Russia": "series-3" };
  var GROUP_KEYS = ["SpaceX", "US", "USSR / Russia", "Everyone else"];

  // Glyph per purpose, in the order of orbits.json "purposes".
  var GLYPHS = ["circle", "diamond", "square", "triangle", "cross", "dot"];

  function elementsModel(mm, e, incDeg, raanDeg, argpDeg, maDeg, t0) {
    var n = mm * TWO_PI / 86400;
    var a = Math.cbrt(MU / (n * n));
    var inc = incDeg * RAD;
    var p = a * (1 - e * e);
    var k = 1.5 * n * J2 * (RE / p) * (RE / p);
    return {
      t0: t0, n: n, a: a, inc: inc, e: e,
      raan: raanDeg * RAD, argp: argpDeg * RAD, ma: maDeg * RAD,
      dRaan: -k * Math.cos(inc),
      dArgp: 0.5 * k * (5 * Math.cos(inc) * Math.cos(inc) - 1)
    };
  }

  // Deterministic pseudo-random in [0, 1) from a catalogue number, so a
  // synthetic orbit is the same on every load.
  function hash01(id, salt) {
    var x = Math.sin(id * 12.9898 + salt * 78.233) * 43758.5453;
    return x - Math.floor(x);
  }

  // Orbit from the catalogue's apogee, perigee and inclination alone: real
  // shape and tilt, synthetic node, perigee and phase.
  function synthModel(id, apo, per, incDeg, t0) {
    var a = RE + (apo + per) / 2;
    var e = Math.max(0, Math.min(0.99, (apo - per) / (2 * a)));
    var n = Math.sqrt(MU / (a * a * a)) * 86400 / TWO_PI;
    return elementsModel(n, e, incDeg, hash01(id, 1) * 360, hash01(id, 2) * 360,
      hash01(id, 3) * 360, t0);
  }

  function gmst(ms) {
    var d = ms / 86400000 + 2440587.5 - 2451545.0;
    return ((280.46061837 + 360.98564736629 * d) % 360) * RAD;
  }

  // Sub-satellite point [lon, lat] in degrees, plus orbital radius in Earth radii.
  function subpoint(o, ms, theta) {
    var dt = (ms - o.t0) / 1000, e = o.e;
    var M = (o.ma + o.n * dt) % TWO_PI, nu, r;
    if (e < 0.02) {
      nu = M + 2 * e * Math.sin(M);
      r = o.a * (1 - e * Math.cos(M));
    } else {
      // Kepler's equation by Newton's method, for Molniya, GTO and the like.
      var E = e > 0.8 ? Math.PI : M;
      for (var k = 0; k < 8; k++) E -= (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
      nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2));
      r = o.a * (1 - e * Math.cos(E));
    }
    var u = o.argp + o.dArgp * dt + nu;
    var W = o.raan + o.dRaan * dt;
    var cu = Math.cos(u), su = Math.sin(u), cW = Math.cos(W), sW = Math.sin(W);
    var ci = Math.cos(o.inc), si = Math.sin(o.inc);
    var x = cW * cu - sW * su * ci, y = sW * cu + cW * su * ci, z = su * si;
    var lon = Math.atan2(y, x) - theta;
    return [((lon / RAD) % 360 + 540) % 360 - 180, Math.asin(z) / RAD, r / R_MEAN];
  }

  // Display radius in Earth radii: true scale to 1,000 km, logarithmic beyond,
  // so GPS (~20,200 km) and the geostationary ring (~35,786 km) stay on screen.
  // The caption says altitude is compressed.
  function dispR(r) {
    var h = (r - 1) * R_MEAN;
    if (h <= 1000) return r;
    return Math.min(1.7, 1 + 1000 / R_MEAN + 0.16 * Math.log(1 + (h - 1000) / 3000));
  }

  function orbitClass(apo, per) {
    if (apo < 2000) return "LEO";
    if (per > 34000 && apo < 37000) return "GEO";
    if (apo < 34000 && per >= 2000) return "MEO";
    if (apo >= 34000) return "HEO";
    return "elliptical";  // low perigee, apogee short of GEO: Vanguard, early Explorers
  }

  // Glyph at scale k (1 = a ~500 px globe). Below ~4 px circles, squares and
  // triangles all render as the same blob, so the base sizes stay above that.
  function glyphPath(ctx, kind, x, y, k) {
    var c = 2.2 * k, h = 2.1 * k, d = 3.2 * k, t = 2.8 * k, a = 3 * k, w = 0.9 * k;
    switch (kind) {
      case "circle": ctx.moveTo(x + c, y); ctx.arc(x, y, c, 0, TWO_PI); break;
      case "diamond": ctx.moveTo(x, y - d); ctx.lineTo(x + d, y); ctx.lineTo(x, y + d); ctx.lineTo(x - d, y); ctx.closePath(); break;
      case "square": ctx.rect(x - h, y - h, 2 * h, 2 * h); break;
      case "triangle": ctx.moveTo(x, y - t); ctx.lineTo(x + t, y + 0.75 * t); ctx.lineTo(x - t, y + 0.75 * t); ctx.closePath(); break;
      case "cross": ctx.rect(x - a, y - w, 2 * a, 2 * w); ctx.rect(x - w, y - a, 2 * w, 2 * a); break;
      default: ctx.rect(x - 1.1 * k, y - 1.1 * k, 2.2 * k, 2.2 * k);
    }
  }

  // Small inline SVG of a glyph for the legend.
  function glyphSvg(kind, colour) {
    var s = { circle: '<circle cx="5" cy="5" r="3"/>',
      diamond: '<path d="M5 1L9 5L5 9L1 5Z"/>',
      square: '<rect x="2" y="2" width="6" height="6"/>',
      triangle: '<path d="M5 1.5L8.8 8.2H1.2Z"/>',
      cross: '<path d="M1 4h8v2H1zM4 1h2v8H4z"/>',
      dot: '<rect x="3.5" y="3.5" width="3" height="3"/>' }[kind];
    return '<svg width="10" height="10" viewBox="0 0 10 10" style="vertical-align:-1px;fill:' +
      colour + '">' + s + "</svg>";
  }

  function getJSON(url, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    if (ctl && ms) setTimeout(function () { ctl.abort(); }, ms);
    return fetch(url, ctl ? { signal: ctl.signal } : {})
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
  }

  // CelesTrak GP JSON -> the columnar shape of fleet.json.
  function fleetFromGp(rows) {
    var ep0 = Date.UTC(1957, 0, 1);
    var f = { id: [], ep: [], mm: [], e: [], i: [], ra: [], ap: [], ma: [] };
    rows.forEach(function (o) {
      var t = Date.parse(String(o.EPOCH).slice(0, 23) + "Z");
      if (!isFinite(t) || !o.MEAN_MOTION) return;
      f.id.push(o.NORAD_CAT_ID); f.ep.push((t - ep0) / DAY); f.mm.push(o.MEAN_MOTION);
      f.e.push(o.ECCENTRICITY); f.i.push(o.INCLINATION); f.ra.push(o.RA_OF_ASC_NODE);
      f.ap.push(o.ARG_OF_PERICENTER); f.ma.push(o.MEAN_ANOMALY);
    });
    return f;
  }

  // Set by renderGlobe when the globe draws; the command bar uses it.
  var globeFly = null;

  function renderGlobe() {
    var host = $("globe"), cap = $("globe-cap");
    if (!window.d3 || !d3.geoOrthographic || !d3.geoRotation) {
      host.classList.add("off");
      host.innerHTML = '<div style="padding:1.5rem;font-family:var(--mono);font-size:0.75rem;color:var(--ink-muted)">' +
        "Globe library did not load, so the globe cannot draw. Pads, facilities and the " +
        "Starlink fleet are all still in the Range map and Growth panels below.</div>";
      return;
    }

    var lp = D.launches || {}, pads = lp.pads || [];
    var facilities = (D.sites || {}).facilities || [];
    var next = lp.next;
    var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Live clock, used once the time-lapse reaches the present.
    var speed = reduced ? 1 : 60;
    var simBase = Date.now(), realBase = simBase;
    function simNow() { return simBase + (Date.now() - realBase) * speed; }

    // Time-lapse clock. Reduced motion opens on the present instead of playing.
    var tl = { on: !reduced, playing: !reduced, t: reduced ? Date.now() : TL_START, mult: 1 };
    function tlRate() { return (Date.now() - TL_START) / (TL_SECONDS * 1000) * tl.mult; }
    function simT() { return tl.on ? tl.t : simNow(); }
    // Sim time a launch streak takes, so it lasts STREAK_MS on screen at any speed.
    function streakSpan() { return STREAK_MS * (tl.on ? tlRate() : speed); }

    // Catalogue, filled when orbits.json arrives. Per satellite: model, launch
    // and decay time (ms), colour group, glyph, and whether it has real elements.
    var cat = null, catAsOf = "", fleetNote = "", loadNote = "loading orbit data…";
    var N = 0, mdl = [], sLaunch = [], sDecay = [], sGroup = [], sReal = [];
    var launchOrder = [], launchMs = [], spxPrefix = [], firstSat = {};
    var hitX = null, hitY = null, hitI = null, hitN = 0;
    var tipSat = -1, pinned = false;

    var canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "Globe time-lapse of every satellite launched to Earth " +
      "orbit since 1957, with launch pads and company facilities");
    host.appendChild(canvas);
    var ctx = canvas.getContext("2d");
    var proj = d3.geoOrthographic().clipAngle(90).precision(0.6);
    var path = d3.geoPath(proj, ctx);
    var grat = d3.geoGraticule10();
    var sphere = { type: "Sphere" };
    var land = null, landFailed = !window.topojson;
    var size = 0, R = 0, cx = 0, cy = 0, rotator = null, zoom = 1;
    var hover = null, focus = null, flying = false;
    var rot = [tl.on ? 80 : -(next && next.lon != null ? next.lon : -80), -22, 0];

    var C = {};
    function readColours() {
      var cs = getComputedStyle(document.documentElement);
      ["globe-ocean", "globe-land", "globe-coast", "globe-grat", "globe-limb", "sat", "sodium", "ink-muted",
        "series-1", "series-2", "series-3", "ink", "globe-neutral"]
        .forEach(function (k) { C[k] = cs.getPropertyValue("--" + k).trim(); });
    }
    readColours();

    function resize() {
      var w = host.clientWidth;
      if (!w) return;
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      size = w;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(w * dpr);
      canvas.style.width = canvas.style.height = w + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // 0.56 leaves room for the outermost orbits: dispR() tops out at 1.7.
      R = w / 2 * 0.56 * zoom;
      cx = cy = w / 2;
      proj.scale(R).translate([cx, cy]);
    }

    // Screen position of a point at `ratio` Earth radii. z > 0 is the near
    // hemisphere; a far-side point is still visible if it clears the disk.
    function place(lon, lat, ratio) {
      var q = rotator([lon, lat]), l = q[0] * RAD, f = q[1] * RAD;
      var x = Math.cos(f) * Math.sin(l), y = Math.sin(f), z = Math.cos(f) * Math.cos(l);
      return { x: cx + R * ratio * x, y: cy - R * ratio * y, z: z,
        rr: Math.sqrt(x * x + y * y) * ratio };
    }

    function draw() {
      if (!size) return;
      proj.rotate(rot);
      rotator = d3.geoRotation(rot);
      ctx.clearRect(0, 0, size, size);

      var g = ctx.createRadialGradient(cx, cy, R * 0.97, cx, cy, R * 1.16);
      g.addColorStop(0, C["globe-limb"]);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, R * 1.16, 0, 2 * Math.PI); ctx.fill();

      ctx.beginPath(); path(sphere); ctx.fillStyle = C["globe-ocean"]; ctx.fill();
      ctx.beginPath(); path(grat); ctx.strokeStyle = C["globe-grat"]; ctx.lineWidth = 1; ctx.stroke();
      if (land) {
        ctx.beginPath(); path(land);
        ctx.fillStyle = C["globe-land"]; ctx.fill();
        ctx.strokeStyle = C["globe-coast"]; ctx.lineWidth = 0.6; ctx.stroke();
      }

      var t = simT(), th = gmst(t), span = streakSpan();
      var sats = placeSats(t, th, span);

      // Far side: satellites behind the Earth but clear of its disk, faint.
      ctx.globalAlpha = 0.28;
      for (var gk = 0; gk < 4; gk++) {
        var fb = sats.far[gk];
        if (!fb.length) continue;
        ctx.fillStyle = groupColour(gk);
        for (var fi = 0; fi < fb.length; fi += 2) ctx.fillRect(fb[fi] - 0.7, fb[fi + 1] - 0.7, 1.4, 1.4);
      }

      ctx.globalAlpha = 1;
      // Today's pads, factories and next launch only make sense on today's globe.
      if (!tl.on) drawSites();

      // Near side: one path per bucket. Defunct (live globe only) first, then
      // groups in reverse so SpaceX paints last and on top; others sit back.
      var k = glyphScale();
      [24, 0].forEach(function (base) {
        for (var g = 3; g >= 0; g--) {
          for (var pu = 0; pu < 6; pu++) {
            var nb = sats.near[base + g * 6 + pu];
            if (!nb.length) continue;
            ctx.globalAlpha = base ? 0.35 : (g === 0 ? 1 : 0.7);
            ctx.fillStyle = groupColour(g);
            ctx.beginPath();
            for (var ni = 0; ni < nb.length; ni += 2) glyphPath(ctx, GLYPHS[pu], nb[ni], nb[ni + 1], k);
            ctx.fill();
          }
        }
      });
      ctx.globalAlpha = 1;

      drawStreaks(t, th, span);
      if (tl.on) drawClock(t, sats.spx);

      // Hovered or pinned satellite: ring it and keep the tooltip on it.
      if (tipSat >= 0) {
        var hp2 = satScreen(tipSat, t, th);
        if (hp2 && satVisible(tipSat, t, span)) {
          ctx.strokeStyle = C.ink;
          ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(hp2.x, hp2.y, 6 + 2 * k, 0, TWO_PI); ctx.stroke();
          // Flip left near the right edge; keep the card inside the globe box.
          tip.classList.toggle("left", hp2.x > size * 0.55);
          tip.style.left = hp2.x + "px";
          var half = tip.offsetHeight / 2;
          tip.style.top = Math.max(half, Math.min(size - half, hp2.y)) + "px";
          tip.hidden = false;
        } else {
          tip.hidden = true;
        }
      }
    }

    // Glyph scale: grows with the globe on screen, and a little with zoom.
    function glyphScale() {
      return Math.max(1, Math.min(2.2, size / 500)) * Math.pow(zoom, 0.25);
    }

    // The year, large and faint on the canvas, with SpaceX's count beneath:
    // a time-lapse is read by its clock, and the eye stays on the globe.
    function drawClock(t, spx) {
      var fs = Math.round(size * 0.09);
      ctx.textAlign = "right";
      ctx.globalAlpha = 0.4;
      ctx.fillStyle = C.ink;
      ctx.font = "800 " + fs + "px Archivo, 'Helvetica Neue', Arial, sans-serif";
      ctx.fillText(String(new Date(t).getUTCFullYear()), size - 10, fs + 4);
      ctx.globalAlpha = 0.85;
      ctx.fillStyle = C["series-1"];
      ctx.font = "500 " + Math.round(fs * 0.3) + "px 'IBM Plex Mono', monospace";
      ctx.fillText("SpaceX " + fmt(spx) + " up", size - 12, fs + 8 + Math.round(fs * 0.34));
      ctx.textAlign = "start";
      ctx.globalAlpha = 1;
    }

    function drawSites() {
      pads.forEach(function (pd) {
        var p = place(pd.lon, pd.lat, 1);
        if (p.z <= 0) return;
        ctx.beginPath();
        ctx.arc(p.x, p.y, pd.spacex ? 3 : 2, 0, 2 * Math.PI);
        ctx.fillStyle = pd.spacex ? "#ffa14a" : C["ink-muted"];
        ctx.fill();
      });
      facilities.forEach(function (fc) {
        var p = place(fc.lon, fc.lat, 1);
        if (p.z <= 0) return;
        ctx.fillStyle = coColor(fc.co);
        ctx.fillRect(p.x - 2.5, p.y - 2.5, 5, 5);
      });

      // Hover label for the site under the pointer.
      if (hover && !focus) {
        var hp = place(hover.lon, hover.lat, 1);
        if (hp.z > 0) {
          ctx.strokeStyle = C.sodium;
          ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(hp.x, hp.y, 7, 0, 2 * Math.PI); ctx.stroke();
          ctx.font = "11px 'IBM Plex Mono', monospace";
          ctx.fillStyle = C.sodium;
          ctx.fillText(hover.name + " · click to zoom", hp.x + 11, hp.y + 4);
        }
      }

      if (next && next.lat != null) {
        var np = place(next.lon, next.lat, 1);
        if (np.z > 0) {
          var ph = (Date.now() % 2000) / 2000;
          ctx.strokeStyle = C.sodium;
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = reduced ? 1 : 1 - ph;
          ctx.beginPath(); ctx.arc(np.x, np.y, reduced ? 9 : 5 + ph * 14, 0, 2 * Math.PI); ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.font = "10px 'IBM Plex Mono', monospace";
          ctx.fillStyle = C.sodium;
          ctx.fillText("NEXT · " + (next.pad_location || next.pad || "").split(",")[0], np.x + 12, np.y - 8);
        }
      }
    }


    function groupColour(gk) {
      return gk < 3 ? C["series-" + (gk + 1)] : C["globe-neutral"];
    }

    // Colour group (0-3) for a catalogue group index.
    var groupKey = [];

    function satVisible(i, t, span) {
      // Counted from launch day; the streak is drawn on top, so it never delays the count.
      return t >= sLaunch[i] && t < sDecay[i];
    }

    function satScreen(i, t, th) {
      var s = subpoint(mdl[i], t, th);
      var p = place(s[0], s[1], dispR(s[2]));
      return p.z > 0 ? p : null;
    }

    // Project every satellite in orbit at time t into per-colour, per-glyph
    // buckets, and record near-side points for hover hit-testing.
    function placeSats(t, th, span) {
      var near = [], far = [[], [], [], []], k, spx = 0;
      for (k = 0; k < 48; k++) near.push([]);
      hitN = 0;
      var live = !tl.on;
      for (var i = 0; i < N; i++) {
        if (!satVisible(i, t, span)) continue;
        var s = subpoint(mdl[i], t, th);
        var p = place(s[0], s[1], dispR(s[2]));
        var g = sGroup[i];
        if (g === 0) spx++;
        if (p.z > 0) {
          var b = (live && !sReal[i] ? 24 : 0) + g * 6 + cat.sat.p[i];
          near[b].push(p.x, p.y);
          hitX[hitN] = p.x; hitY[hitN] = p.y; hitI[hitN] = i; hitN++;
        } else if (p.rr > 1) {
          far[g].push(p.x, p.y);
        }
      }
      return { near: near, far: far, spx: spx };
    }

    // Launch streaks: from the site, rising along a great circle to where the
    // launch's first payload is when the streak ends.
    function drawStreaks(t, th, span) {
      if (!cat || !launchMs.length) return;
      var lo = lowerBound(launchMs, t - span);
      for (var q = lo; q < launchMs.length && launchMs[q] <= t; q++) {
        var li = launchOrder[q], fs = firstSat[li];
        var site = cat.sites[cat.launch.site[li]];
        if (fs == null || !site || site[2] == null) continue;
        var prog = (t - launchMs[q]) / span;
        var end = subpoint(mdl[fs], launchMs[q] + span, gmst(launchMs[q] + span));
        var path2 = d3.geoInterpolate([site[3], site[2]], [end[0], end[1]]);
        var top = dispR(end[2]);
        ctx.strokeStyle = cat.launch.spx[li] ? C["series-1"] : groupColour(sGroup[fs]);
        ctx.lineWidth = 1.6;
        ctx.globalAlpha = prog > 0.8 ? (1 - prog) * 5 : 1;
        ctx.beginPath();
        var started = false, head = null;
        for (var j = 0; j <= 12; j++) {
          var f = prog * j / 12;
          var ll = path2(f * 0.35);  // a launch covers a fraction of the arc to orbit
          var pt = place(ll[0], ll[1], 1 + (top - 1) * Math.sin(f * Math.PI / 2));
          if (pt.z <= 0 && pt.rr < 1) { started = false; continue; }
          if (!started) { ctx.moveTo(pt.x, pt.y); started = true; } else ctx.lineTo(pt.x, pt.y);
          head = pt;
        }
        ctx.stroke();
        if (head) {
          ctx.fillStyle = ctx.strokeStyle;  // head in the streak's own colour
          ctx.beginPath(); ctx.arc(head.x, head.y, 1.8, 0, TWO_PI); ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }

    function lowerBound(arr, v) {
      var a = 0, b = arr.length;
      while (a < b) { var m = (a + b) >> 1; if (arr[m] < v) a = m + 1; else b = m; }
      return a;
    }

    /* ---- catalogue ---------------------------------------------------- */

    function buildCatalogue(c) {
      var ep0 = Date.UTC(1957, 0, 1);
      cat = c;
      var S = c.sat, L = c.launch;
      N = S.id.length;
      groupKey = c.groups.map(function (g) {
        var k = GROUP_KEYS.indexOf(g);
        return k >= 0 && k < 3 ? k : 3;
      });
      // Launch time of day is not in the catalogue; noon UTC stands in.
      sLaunch = new Array(N); sDecay = new Array(N); sGroup = new Array(N);
      for (var i = 0; i < N; i++) {
        var li = S.l[i];
        sLaunch[i] = ep0 + L.day[li] * DAY + DAY / 2;
        // Infinity, not -1, for "still up": every date before 1970 is a negative timestamp.
        sDecay[i] = S.dec[i] < 0 ? Infinity : ep0 + S.dec[i] * DAY;
        sGroup[i] = groupKey[S.g[i]];
        if (firstSat[li] == null) firstSat[li] = i;
      }
      launchOrder = L.day.map(function (_, k) { return k; })
        .sort(function (a, b) { return L.day[a] - L.day[b]; });
      launchMs = launchOrder.map(function (k) { return ep0 + L.day[k] * DAY + DAY / 2; });
      spxPrefix = [0];
      launchOrder.forEach(function (k, q) { spxPrefix.push(spxPrefix[q] + L.spx[k]); });
      hitX = new Float32Array(N); hitY = new Float32Array(N); hitI = new Int32Array(N);
    }

    // (Re)build every satellite's orbit model: real elements where the fleet
    // has them, synthetic from the catalogue otherwise.
    function applyFleet(F) {
      var ep0 = Date.UTC(1957, 0, 1), idx = {};
      for (var j = 0; j < F.id.length; j++) idx[F.id[j]] = j;
      var S = cat.sat;
      mdl = new Array(N); sReal = new Array(N);
      for (var i = 0; i < N; i++) {
        var fj = idx[S.id[i]];
        if (fj != null && S.dec[i] < 0) {
          mdl[i] = elementsModel(F.mm[fj], F.e[fj], F.i[fj], F.ra[fj], F.ap[fj], F.ma[fj],
            ep0 + F.ep[fj] * DAY);
          sReal[i] = true;
        } else {
          mdl[i] = synthModel(S.id[i], S.apo[i], S.per[i], S.inc[i], sLaunch[i]);
          sReal[i] = false;
        }
      }
    }

    function satName(i) {
      var n = cat.sat.name[i];
      return n.charAt(0) === "*" ? "STARLINK-" + n.slice(1) : n;
    }

    function day(ms) { return new Date(ms).toISOString().slice(0, 10); }

    function satHtml(i) {
      var S = cat.sat, L = cat.launch, li = S.l[i];
      var site = cat.sites[L.site[li]] || [];
      var lv = cat.lvs[L.lv[li]] || "vehicle unknown";
      var catg = cat.cats[S.c[i]];
      var gk = sGroup[i];
      var status = S.dec[i] >= 0 ? "decayed " + day(sDecay[i]) :
        (sReal[i] ? "in orbit · operating" : "in orbit · not operating");
      // Real elements are only a real position near the present.
      var nearNow = Math.abs(simT() - Date.now()) < 3 * DAY;
      var where = sReal[i] && nearNow ? "position from " + fleetNote : "position illustrative";
      var group = cat.groups[S.g[i]], owner = cat.owners[S.o[i]];
      return "<b>" + esc(satName(i)) + "</b> <span class=\"fine\">#" + S.id[i] + "</span>" +
        '<div><span style="color:' + groupColour(gk) + '">●</span> ' + esc(group === "Other" ? "other country" : group) +
        (owner && owner !== group ? " · owner code " + esc(owner) : "") + "</div>" +
        "<div>" + esc(cat.purposes[S.p[i]]) +
        (catg === "-" ? " (no GCAT category)" : " · GCAT " + esc(catg)) + "</div>" +
        "<div>launched " + day(sLaunch[i]) + " · " + esc(lv) +
        (L.spx[li] ? " (SpaceX)" : "") + "</div>" +
        "<div>from " + esc(site[1] || "site unknown") + "</div>" +
        "<div>" + orbitClass(S.apo[i], S.per[i]) + " · " + fmt(S.per[i]) + "×" + fmt(S.apo[i]) +
        " km · " + S.inc[i] + "°</div>" +
        "<div>" + status + "</div>" +
        '<div class="fine">' + where + "</div>";
    }

    // Satellite nearest the pointer within 6 px, among near-side points drawn last frame.
    function satAt(e) {
      if (!cat || (tl.on && tl.playing)) return -1;
      var b = canvas.getBoundingClientRect(), mx = e.clientX - b.left, my = e.clientY - b.top;
      var best = -1, bestD = 36;
      for (var h = 0; h < hitN; h++) {
        var dx = hitX[h] - mx, dy = hitY[h] - my, d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = hitI[h]; }
      }
      return best;
    }

    function showTip(i) {
      tipSat = i;
      if (i < 0) { tip.hidden = true; return; }
      tip.innerHTML = satHtml(i);
    }

    // Tooltip for a hovered or pinned satellite; positioned in draw().
    var tip = el("div", "sat-tip");
    tip.hidden = true;
    tip.setAttribute("role", "status");
    host.appendChild(tip);

    // Time-lapse controls: play/pause, scrub, speed, and a readout of the year.
    var bar = el("div", "tl-bar");
    var playBtn = el("button", "", "");
    playBtn.type = "button";
    var scrub = el("input");
    scrub.type = "range"; scrub.min = 0; scrub.max = 1000; scrub.step = 1;
    scrub.setAttribute("aria-label", "Time-lapse date");
    var speedBtn = el("button", "", "×1");
    speedBtn.type = "button";
    speedBtn.title = "Time-lapse speed";
    var readout = el("div", "tl-read");
    // Zoom and full-window view. The wheel zooms only when expanded, so the
    // hero does not swallow page scrolling; the buttons work everywhere.
    var zoomOut = el("button", "", "−"), zoomIn = el("button", "", "+");
    var bigBtn = el("button", "", "⤢ expand");
    zoomOut.type = zoomIn.type = bigBtn.type = "button";
    zoomOut.setAttribute("aria-label", "Zoom out");
    zoomIn.setAttribute("aria-label", "Zoom in");
    [playBtn, scrub, speedBtn, zoomOut, zoomIn, bigBtn].forEach(function (b) { bar.appendChild(b); });
    cap.appendChild(bar);
    cap.appendChild(readout);

    function setZoom(z) {
      if (focus || flying) return;
      zoom = Math.max(0.7, Math.min(10, z));
      resize();
      draw();
    }
    zoomIn.addEventListener("click", function () { setZoom(zoom * 1.5); });
    zoomOut.addEventListener("click", function () { setZoom(zoom / 1.5); });

    var wrapEl = host.parentNode;
    function setBig(on) {
      wrapEl.classList.toggle("big", on);
      document.body.style.overflow = on ? "hidden" : "";
      bigBtn.textContent = on ? "✕ close" : "⤢ expand";
      resize();
      draw();
    }
    bigBtn.addEventListener("click", function () { setBig(!wrapEl.classList.contains("big")); });
    host.addEventListener("wheel", function (e) {
      if (!wrapEl.classList.contains("big")) return;
      e.preventDefault();
      setZoom(zoom * Math.exp(-e.deltaY * 0.0015));
    }, { passive: false });

    function setPlaying(p) {
      if (p && !tl.on) { tl.on = true; tl.t = TL_START; }  // replay from Sputnik
      tl.playing = p;
      if (p && !pinned) showTip(-1);
      updateBar();
    }
    function goLive() {
      tl.on = false; tl.playing = false;
      simBase = realBase = Date.now();
      updateBar();
    }
    playBtn.addEventListener("click", function () { setPlaying(!(tl.on && tl.playing)); });
    speedBtn.addEventListener("click", function () {
      tl.mult = tl.mult >= 4 ? 0.5 : tl.mult * 2;
      speedBtn.textContent = "×" + (tl.mult === 0.5 ? "½" : tl.mult);
    });
    scrub.addEventListener("input", function () {
      tl.on = true; tl.playing = false;
      tl.t = TL_START + (Date.now() - TL_START) * scrub.value / 1000;
      updateBar();
      draw();
    });

    function updateBar() {
      playBtn.textContent = tl.on && tl.playing ? "❚❚ pause" : (tl.on ? "▶ play" : "▶ replay 1957→");
      playBtn.setAttribute("aria-label", tl.on && tl.playing ? "Pause time-lapse" : "Play time-lapse");
    }

    // Year, satellites up, and this year's launches with SpaceX's share.
    function tickReadout() {
      var t = simT();
      var y = new Date(t).getUTCFullYear();
      if (!cat) { readout.textContent = loadNote; return; }
      var span = streakSpan(), up = 0, byGroup = [0, 0, 0, 0];
      for (var i = 0; i < N; i++) {
        if (satVisible(i, t, span)) { up++; byGroup[sGroup[i]]++; }
      }
      for (var g = 0; g < 4; g++) keyCounts[g].textContent = fmt(byGroup[g]);
      var a = lowerBound(launchMs, Date.UTC(y, 0, 1)), b = lowerBound(launchMs, t + 1);
      var n = b - a, sx = spxPrefix[b] - spxPrefix[a];
      readout.innerHTML = "<b>" + (tl.on ? new Date(t).toISOString().slice(0, 7) : "NOW · live") +
        "</b> · SpaceX " + fmt(byGroup[0]) + " of " + fmt(up) + " satellites up" +
        (up ? " (" + Math.round(100 * byGroup[0] / up) + "%)" : "") + " · " + fmt(n) +
        (n === 1 ? " launch in " : " launches in ") + y + ", " + fmt(sx) + " by SpaceX";
      if (document.activeElement !== scrub) {
        scrub.value = Math.round(1000 * Math.min(1, (t - TL_START) / (Date.now() - TL_START)));
      }
    }
    setInterval(tickReadout, 250);

    // Key: colour is owner (with a live count, so the SpaceX ramp reads as a
    // number as well as a colour), shape is purpose. Inline it sits under the
    // globe so it hides nothing; expanded it floats in the margin beside it.
    // Collapsible, so it can get out of the way on a small screen.
    var key = el("div", "globe-key");
    var keyBtn = el("button", "globe-key-btn", "key ▾");
    keyBtn.type = "button";
    keyBtn.setAttribute("aria-expanded", "true");
    var keyBody = el("div", "globe-key-body");
    var keyCounts = [];
    var ownerHtml = '<div class="gk-h">Owner <span>satellites up</span></div>';
    GROUP_KEYS.forEach(function (g, gk) {
      ownerHtml += '<div class="gk-row"><i style="background:var(--' +
        (gk < 3 ? "series-" + (gk + 1) : "globe-neutral") + ')"></i>' + esc(g) +
        '<b data-g="' + gk + '">–</b></div>';
    });
    keyBody.innerHTML = '<div class="gk-col">' + ownerHtml + "</div>" +
      '<div class="gk-col"><div class="gk-h">Purpose</div><div class="gk-purpose"></div></div>';
    keyCounts = [0, 1, 2, 3].map(function (gk) { return keyBody.querySelector('b[data-g="' + gk + '"]'); });
    key.appendChild(keyBtn);
    key.appendChild(keyBody);
    host.parentNode.insertBefore(key, cap);
    keyBtn.addEventListener("click", function () {
      var open = keyBody.hidden;
      keyBody.hidden = !open;
      keyBtn.textContent = open ? "key ▾" : "key ▸";
      keyBtn.setAttribute("aria-expanded", String(open));
    });
    // The key is an overlay; keep pointer events on it from dragging the globe.
    key.addEventListener("pointerdown", function (e) { e.stopPropagation(); });

    var note = el("div");
    var lg = el("div");
    cap.appendChild(note);
    cap.appendChild(lg);
    function writeCaption() {
      if (cat) {
        keyBody.querySelector(".gk-purpose").innerHTML = cat.purposes.map(function (p, k) {
          return '<div class="gk-row">' + glyphSvg(GLYPHS[k], "var(--ink)") + " " + esc(p) + "</div>";
        }).join("");
      }
      var c = cat ? cat.counts : null;
      note.textContent = c ?
        fmt(c.payloads) + " payloads ever sent to Earth orbit, debris excluded (SATCAT + GCAT, " +
        catAsOf + "). Before today, positions are illustrative: real inclination and altitude, " +
        "synthetic phase. Today: " + fleetNote + ". Two-body + J2, not SGP4. " +
        "Altitude compressed above 1,000 km. Pause, then hover a satellite." :
        loadNote;
      lg.innerHTML = '<span style="color:#ffa14a">●</span> SpaceX pad &nbsp;<span>●</span> other pad &nbsp;' +
        Object.keys(CO_COLOR).filter(function (co) {
          return facilities.some(function (f) { return f.co === co; });
        }).map(function (co) {
          return '<span style="color:' + coColor(co) + '">■</span> ' + co + " &nbsp;";
        }).join("") +
        '<span style="color:var(--sodium)">◯</span> next launch · drag to turn · click a site to zoom in';
    }
    updateBar();
    writeCaption();

    // Committed files first; then try CelesTrak live for fresher elements.
    Promise.all([getJSON("orbits.json", 30000), getJSON("fleet.json", 30000)])
      .then(function (res) {
        catAsOf = String(res[0].fetched_at || "").slice(0, 10);
        buildCatalogue(res[0].data);
        applyFleet(res[1].data);
        fleetNote = "elements as of " + String(res[1].fetched_at || "").slice(0, 10);
        writeCaption();
        draw();
        return getJSON(LIVE_GP, 20000).then(function (rows) {
          var f = fleetFromGp(rows);
          if (!f.id.length) return;
          applyFleet(f);
          fleetNote = "live CelesTrak elements";
          writeCaption();
        }, function () { /* 403 within CelesTrak's update cycle, or offline: keep the committed copy */ });
      })
      .catch(function () {
        loadNote = location.protocol === "file:" ?
          "Orbit data cannot load from a file:// page; serve docs/ over http (python -m http.server -d docs)." :
          "Orbit data did not load, so the time-lapse cannot run.";
        tl.on = false; tl.playing = false;
        updateBar();
        writeCaption();
      });

    if (!landFailed) {
      fetch(LAND_URL).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (topo) { land = topojson.feature(topo, topo.objects.land); draw(); })
        .catch(function () {
          lg.appendChild(document.createTextNode(" · coastlines did not load"));
        });
    }

    var dragging = false, idleUntil = 0, from = null;

    // Every clickable site, pads and facilities alike, in one list.
    var sites = pads.map(function (pd) {
      return { name: pd.name, lat: pd.lat, lon: pd.lon, pad: pd, z: 16 };
    }).concat(facilities.map(function (fc) {
      return { name: fc.name, lat: fc.lat, lon: fc.lon, fac: fc, z: fc.zoom || 15 };
    }));

    function siteAt(e) {
      if (tl.on) return null;
      var b = canvas.getBoundingClientRect(), mx = e.clientX - b.left, my = e.clientY - b.top;
      var best = null, bestD = 12 * 12;
      sites.forEach(function (st) {
        var p = place(st.lon, st.lat, 1);
        if (p.z <= 0) return;
        var d = (p.x - mx) * (p.x - mx) + (p.y - my) * (p.y - my);
        if (d < bestD) { bestD = d; best = st; }
      });
      return best;
    }

    // Two pointers down is a pinch: zoom by the change in their distance.
    var ptrs = {}, pinch = null;
    function ptrDist() {
      var p = Object.keys(ptrs).map(function (k) { return ptrs[k]; });
      return Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
    }

    host.addEventListener("pointerdown", function (e) {
      if (focus || flying) return;
      ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      if (Object.keys(ptrs).length === 2) {
        dragging = false;
        pinch = { d0: ptrDist() || 1, z0: zoom };
        return;
      }
      dragging = true;
      from = { x: e.clientX, y: e.clientY, r: rot.slice() };
      try { host.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    });
    host.addEventListener("pointermove", function (e) {
      if (focus || flying) return;
      if (ptrs[e.pointerId]) ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      if (pinch) {
        if (Object.keys(ptrs).length === 2) setZoom(pinch.z0 * ptrDist() / pinch.d0);
        return;
      }
      if (!dragging) {
        var h = siteAt(e);
        // A site under the pointer wins; otherwise a satellite, when the
        // time-lapse is paused or on the live globe.
        var si = h ? -1 : satAt(e);
        if (!pinned && si !== tipSat) showTip(si);
        if (h !== hover) {
          hover = h;
          if (reduced) draw();
        }
        host.style.cursor = h || si >= 0 ? "pointer" : "";
        return;
      }
      var k = 180 / (Math.PI * R);
      rot[0] = from.r[0] + (e.clientX - from.x) * k;
      rot[1] = Math.max(-80, Math.min(80, from.r[1] - (e.clientY - from.y) * k));
      if (reduced) draw();
    });
    function release(e) {
      delete ptrs[e.pointerId];
      if (pinch) {
        // Lifting a finger ends the pinch; it is never a click.
        if (Object.keys(ptrs).length < 2) { pinch = null; ptrs = {}; idleUntil = Date.now() + 5000; }
        return;
      }
      if (!dragging) return;
      dragging = false;
      idleUntil = Date.now() + 5000;
      // A press that barely moved is a click, not a drag.
      if (e.type === "pointerup" &&
          Math.abs(e.clientX - from.x) + Math.abs(e.clientY - from.y) < 6) {
        var st = siteAt(e);
        if (st) { pinned = false; showTip(-1); flyTo(st); return; }
        // Click a satellite to pin its card; click anywhere else to let go.
        var sc = satAt(e);
        pinned = sc >= 0;
        showTip(sc);
        if (reduced) draw();
      }
    }
    host.addEventListener("pointerup", release);
    host.addEventListener("pointercancel", release);
    host.addEventListener("pointerleave", function () {
      if (!dragging && hover) { hover = null; host.style.cursor = ""; }
      if (!dragging && !pinned) showTip(-1);
    });

    /* ---- close-up ------------------------------------------------------
     * Click a site: the globe turns and dives toward it, then hands over to
     * satellite imagery, which continues the dive down to the site. The globe
     * itself cannot do the last part - its coastline file is 110 m scale, so
     * past continent level it is a grey polygon - so the close-up is Esri World
     * Imagery in a Leaflet map laid over the globe. Imagery capture dates vary
     * by place and can predate construction; the card says so.
     */
    var wrap = host.parentNode;
    var closeEl = el("div", "closeup");
    closeEl.hidden = true;
    var closeMap = el("div", "closeup-map");
    var card = el("div", "closeup-card");
    var back = el("button", "closeup-back", "← globe");
    back.type = "button";
    closeEl.appendChild(closeMap);
    closeEl.appendChild(card);
    closeEl.appendChild(back);
    wrap.appendChild(closeEl);
    var lmap = null, lmarker = null;

    function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

    function animate(toRot, toZoom, ms, done) {
      var r0 = rot.slice(), z0 = zoom, t0 = performance.now();
      // Turn the short way round.
      var dl = ((toRot[0] - r0[0]) % 360 + 540) % 360 - 180;
      flying = true;
      function step(now) {
        var t = reduced ? 1 : Math.min(1, (now - t0) / ms), k = ease(t);
        rot[0] = r0[0] + dl * k;
        rot[1] = r0[1] + (toRot[1] - r0[1]) * k;
        zoom = z0 * Math.pow(toZoom / z0, k);
        resize();
        draw();
        if (t < 1) requestAnimationFrame(step);
        else { flying = false; if (done) done(); }
      }
      requestAnimationFrame(step);
    }

    function esc(x) {
      var d = el("div");
      d.textContent = x == null ? "" : String(x);
      return d.innerHTML.replace(/"/g, "&quot;");
    }

    function cardHtml(st) {
      var h = "<b>" + esc(st.name) + "</b>";
      if (st.fac) {
        var f = st.fac;
        h += '<div><span style="color:' + coColor(f.co) + '">' + esc(f.co) + "</span> · " + esc(f.kind) + "</div>" +
          '<div class="st st-' + esc(f.status) + '">' + esc(f.status) + "</div>" +
          (f.note ? '<div class="nt">' + esc(f.note) + "</div>" : "") +
          (f.source ? '<div><a href="' + esc(f.source) + '" target="_blank" rel="noopener">source</a></div>' : "");
      } else {
        var pd = st.pad;
        h += "<div>" + esc(pd.location || "") + "</div>" +
          "<div>" + esc(pd.count) + " launches sampled · " + esc(pd.top_provider || "") + "</div>";
      }
      var gm = "https://www.google.com/maps/@" + st.lat + "," + st.lon + ",900m/data=!3m1!1e3";
      return h + '<div class="fine">' + st.lat.toFixed(4) + ", " + st.lon.toFixed(4) +
        ' · <a href="' + gm + '" target="_blank" rel="noopener">Google Maps</a>' +
        "<br>Esri World Imagery; capture date varies by site.</div>";
    }

    function openCloseUp(st) {
      card.innerHTML = cardHtml(st);
      closeEl.hidden = false;
      void closeEl.offsetWidth;  // flush styles so the fade-in transition runs
      closeEl.classList.add("on");
      back.focus({ preventScroll: true });
      if (!window.L) {
        closeMap.innerHTML = '<div class="closeup-off">Imagery needs the map library, which did not load.</div>';
        return;
      }
      if (!lmap) {
        lmap = L.map(closeMap, { zoomControl: true, scrollWheelZoom: true });
        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          { maxZoom: 19, maxNativeZoom: 18, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics" }
        ).addTo(lmap);
      }
      lmap.invalidateSize();
      lmap.setView([st.lat, st.lon], 5, { animate: false });
      if (lmarker) lmap.removeLayer(lmarker);
      lmarker = L.circleMarker([st.lat, st.lon], { radius: 10, color: "#ffa14a", weight: 2, fill: false })
        .addTo(lmap);
      if (reduced) lmap.setView([st.lat, st.lon], st.z, { animate: false });
      else lmap.flyTo([st.lat, st.lon], st.z, { duration: 2.4 });
    }

    function flyTo(st) {
      focus = st;
      hover = null;
      host.style.cursor = "";
      animate([-st.lon, -st.lat, 0], 3.2, 1100, function () { openCloseUp(st); });
    }

    function closeUp() {
      if (!focus || flying) return;
      closeEl.classList.remove("on");
      setTimeout(function () { closeEl.hidden = true; }, 300);
      focus = null;
      idleUntil = Date.now() + 4000;
      animate([rot[0], -22, 0], 1, 900);
    }
    back.addEventListener("click", closeUp);
    globeFly = function (name) {
      var st = sites.filter(function (x) { return x.fac && x.fac.name === name; })[0];
      if (!st || flying) return;
      if (focus) {
        // Already in a close-up: move the imagery rather than re-diving.
        focus = st;
        openCloseUp(st);
        return;
      }
      flyTo(st);
    };
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (pinned || tipSat >= 0) { pinned = false; showTip(-1); return; }
      if (!focus && wrapEl.classList.contains("big")) { setBig(false); return; }
      closeUp();
    });

    document.addEventListener("hangar:theme", function () { readColours(); draw(); });
    window.addEventListener("resize", function () { resize(); draw(); });
    resize();
    draw();

    // One loop for both modes. Under reduced motion the globe never turns on its
    // own and redraws once a second, except while the viewer plays the time-lapse.
    var last = performance.now(), lastDraw = 0;
    function frame(now) {
      var dt = Math.min(100, now - last);
      last = now;
      if (!document.hidden) {
        var r = host.getBoundingClientRect();
        if (r.bottom > 0 && r.top < window.innerHeight) {
          // The time-lapse only advances while the globe is on screen.
          if (tl.on && tl.playing && cat) {
            tl.t += dt * tlRate();
            if (tl.t >= Date.now()) goLive();
          }
          var paused = tl.on && !tl.playing;
          if (!reduced && !paused && !dragging && !focus && !flying && Date.now() > idleUntil) {
            rot[0] += dt * (tl.on ? 0.001 : 0.004);
          }
          if (!flying && (!reduced || (tl.on && tl.playing) || now - lastDraw > 1000)) {
            draw();
            lastDraw = now;
          }
        }
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- source bus and ticker ------------------------------------ */

  function renderBus() {
    var host = $("bus"), st = D.status || {};
    Object.keys(st).forEach(function (k) {
      var s = st[k];
      var sp = el("span", s.stale ? "stale" : "");
      sp.appendChild(el("i"));
      sp.appendChild(document.createTextNode(k + " " + s.age));
      sp.title = k + (s.stale ? " — STALE" : " — fresh") + ", last success " + s.age + " ago";
      host.appendChild(sp);
    });
  }

  function renderTicker() {
    var host = $("ticker"), news = D.news;
    var items = [];
    if (news && news.sections) {
      news.order.forEach(function (k) {
        (news.sections[k] || []).forEach(function (e) { items.push(e); });
      });
    }
    if (!items.length) { host.remove(); return; }
    items.sort(function (a, b) { return String(b.published).localeCompare(String(a.published)); });
    items = items.slice(0, 14);
    var track = el("div", "track");
    // Two copies make the crawl seamless: the track slides exactly half its width.
    [0, 1].forEach(function (copy) {
      items.forEach(function (e) {
        var a = el("a", copy ? "dup" : "");
        a.href = e.link; a.target = "_blank"; a.rel = "noopener";
        if (copy) { a.tabIndex = -1; a.setAttribute("aria-hidden", "true"); }
        a.appendChild(el("b", "", timeAgo(e.published).replace(" ago", "")));
        a.appendChild(document.createTextNode(e.title));
        track.appendChild(a);
      });
    });
    track.style.setProperty("--dur", Math.max(60, items.length * 7) + "s");
    host.appendChild(track);
  }

  /* ---------- boot sequence ---------------------------------------------
   * Once per browser session, the board "comes online": each source reports
   * in with its real age and state from the payload. Theatre, but every line
   * is true. Skipped under reduced motion; any click or key dismisses it.
   */

  function boot() {
    var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var done = false;
    try { done = sessionStorage.getItem("hangar-booted") === "1"; } catch (e) { done = true; }
    if (reduced || done) return;
    try { sessionStorage.setItem("hangar-booted", "1"); } catch (e) { /* ignore */ }

    var ov = el("div", "boot"), pre = el("pre");
    ov.setAttribute("aria-hidden", "true");
    ov.appendChild(pre);
    document.body.appendChild(ov);

    var st = D.status || {}, lines = [["hi", "HANGAR // RANGE BOARD"],
      ["", "build " + D.meta.generated.replace("T", " ").slice(0, 19) + " UTC"]];
    Object.keys(st).forEach(function (k) {
      var s = st[k];
      lines.push([s.stale ? "bad" : "ok",
        "LINK " + (k + " ").padEnd(16, ".") + (s.stale ? " STALE " : " OK    ") + s.age]);
    });
    var c = D.constellation;
    if (c && c.in_orbit) lines.push(["", "TRACK starlink ... " + fmt(c.in_orbit) + " in orbit"]);
    var n = D.launches && D.launches.next;
    if (n) lines.push(["hi", "T-MINUS  " + (n.name || "")]);

    function finish() {
      if (ov.classList.contains("gone")) return;
      ov.classList.add("gone");
      setTimeout(function () { ov.remove(); }, 450);
    }
    ov.addEventListener("click", finish);
    document.addEventListener("keydown", finish, { once: true });
    var i = 0;
    (function step() {
      if (ov.classList.contains("gone")) return;
      if (i < lines.length) {
        pre.appendChild(el("span", lines[i][0], lines[i][1] + "\n"));
        i++;
        setTimeout(step, 110);
      } else {
        setTimeout(finish, 550);
      }
    })();
  }

  /* ---------- command bar ------------------------------------------------ */

  function initCommand() {
    var items = [
      { label: "Next launch", hint: "top", href: "#hero" },
      { label: "Schedule performance", hint: "promise horizon", href: "#board" },
      { label: "Growth", hint: "charts", href: "#growth" },
      { label: "Manifest", hint: "upcoming launches", href: "#manifest" },
      { label: "Range", hint: "map", href: "#range" },
      { label: "Dispatch", hint: "news", href: "#dispatch" },
      { label: "Toggle theme", hint: "light / dark", run: function () { $("theme").click(); } }
    ];
    ((D.launches || {}).upcoming || []).forEach(function (L) {
      if (L.url) items.push({ label: L.name, hint: shortDate(L.net).slice(0, 10), url: L.url });
    });
    // Every globe site, so a site on the far side of the globe is one search away.
    if (globeFly) {
      ((D.sites || {}).facilities || []).forEach(function (f) {
        items.push({ label: "Zoom → " + f.name, hint: f.co, run: function () {
          window.scrollTo({ top: 0, behavior: "smooth" });
          globeFly(f.name);
        } });
      });
    }

    var ov = el("div", "cmd");
    ov.hidden = true;
    var box = el("div", "box");
    var input = el("input");
    input.type = "text";
    input.placeholder = "Jump to a section or search the manifest…";
    input.setAttribute("aria-label", "Command bar");
    var list = el("ul");
    box.appendChild(input);
    box.appendChild(list);
    ov.appendChild(box);
    document.body.appendChild(ov);

    var shown = [], sel = 0;
    function paint() {
      var q = input.value.toLowerCase();
      shown = items.filter(function (it) { return !q || it.label.toLowerCase().indexOf(q) >= 0; }).slice(0, 12);
      sel = Math.min(sel, Math.max(0, shown.length - 1));
      list.innerHTML = "";
      shown.forEach(function (it, i) {
        var li = el("li", i === sel ? "on" : "");
        li.appendChild(el("span", "", it.label));
        li.appendChild(el("small", "", it.hint || ""));
        li.addEventListener("mousedown", function (e) { e.preventDefault(); sel = i; go(); });
        list.appendChild(li);
      });
    }
    function open() { ov.hidden = false; input.value = ""; sel = 0; paint(); input.focus(); }
    function close() { ov.hidden = true; }
    function go() {
      var it = shown[sel];
      close();
      if (!it) return;
      if (it.run) it.run();
      else if (it.url) window.open(it.url, "_blank", "noopener");
      else if (it.href) {
        var t = document.querySelector(it.href);
        if (t) t.scrollIntoView({ behavior: "smooth" });
      }
    }
    input.addEventListener("input", function () { sel = 0; paint(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { sel = Math.min(shown.length - 1, sel + 1); paint(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); paint(); e.preventDefault(); }
      else if (e.key === "Enter") { go(); e.preventDefault(); }
      else if (e.key === "Escape") { close(); }
    });
    ov.addEventListener("mousedown", function (e) { if (e.target === ov) close(); });
    document.addEventListener("keydown", function (e) {
      var tag = (e.target && e.target.tagName) || "";
      var typing = tag === "INPUT" || tag === "TEXTAREA" || (e.target && e.target.isContentEditable);
      if (!typing && (e.key === "/" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k"))) {
        e.preventDefault();
        open();
      }
    });
    $("cmd-open").addEventListener("click", function (e) { e.preventDefault(); open(); });
  }

  /* ---------- source status -------------------------------------------- */

  function renderStatus() {
    var host = $("sources"), st = D.status || {};
    Object.keys(st).forEach(function (k) {
      var s = st[k];
      var d = el("div", s.stale ? "stale" : "");
      d.textContent = k + " — " + (s.stale ? "STALE " : "") + s.age +
        (s.last_error ? " (" + s.last_error.slice(0, 40) + ")" : "");
      host.appendChild(d);
    });
    var stamps = { "board-stamp": "news", "manifest-stamp": "launches", "dispatch-stamp": "news" };
    Object.keys(stamps).forEach(function (id) {
      var s = st[stamps[id]];
      if (!s) return;
      var n = $(id);
      n.textContent = "updated " + s.age + " ago";
      if (s.stale) n.className = "stamp stale";
    });
    $("bar-sub").textContent = "updated " + timeAgo(D.meta.generated);
  }

  /* ---------- theme ----------------------------------------------------- */

  function initTheme() {
    var btn = $("theme");
    function apply(mode) {
      document.documentElement.setAttribute("data-theme", mode);
      btn.textContent = mode === "dark" ? "Light" : "Dark";
      try { localStorage.setItem("hangar-theme", mode); } catch (e) { /* private mode */ }
      // The map basemap is not CSS and cannot follow a token change, so it is
      // told explicitly.
      document.dispatchEvent(new CustomEvent("hangar:theme", { detail: mode }));
    }
    var saved = null;
    try { saved = localStorage.getItem("hangar-theme"); } catch (e) { /* ignore */ }
    apply(saved || "dark");
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      apply(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  }

  renderClock();
  renderRail();
  renderBoard();
  renderGrowth();
  renderManifest();
  renderDispatch();
  renderMap();
  renderStatus();
  renderBus();
  renderTicker();
  renderGlobe();
  initCommand();
  initTheme();
  boot();
})();
