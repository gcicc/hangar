/* HANGAR page script.
 *
 * Reads the inlined payload and renders. The page makes no data requests of its
 * own - the only network traffic is map tiles, loaded lazily when the map
 * scrolls into view, and web fonts. That is what lets a refresh job and the
 * page be completely decoupled.
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
    if (L.webcast_live) st.appendChild(el("span", "tag go", "live"));
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
      if (r.times_seen > 1) what.appendChild(el("span", "badge", "repeated ×" + r.times_seen));
      a.appendChild(what);
      a.appendChild(el("div", "who", r.source || ""));
      crack.appendChild(a);
    });
    c.appendChild(crack);
    host.appendChild(c);
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
    var p = el("div", "col");
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
                (building ? "transparent" : (f.co === "SpaceX" ? "#8bd3ff" : "#ff8f6b")) +
                ";border:2px solid " + (f.co === "SpaceX" ? "#8bd3ff" : "#ff8f6b") +
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
      '<span><i style="background:#8bd3ff"></i>SpaceX facility</span>' +
      '<span><i style="background:#ff8f6b"></i>Tesla facility</span>' +
      '<span><i style="background:transparent;border:1px dashed var(--ink-2)"></i>under construction</span>' +
      '<span><i style="background:#35b8a8;border-radius:50%"></i>Superchargers (clustered)</span>' +
      '<span>Circle area &#8733; count</span>' +
      (sc.note ? '<span style="flex-basis:100%;opacity:.75">' + sc.note + '</span>' : "");
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
  initTheme();
})();
