/* 秋招岗位追踪 - 前端逻辑 */
(function () {
  "use strict";

  var state = {
    jobs: [],
    meta: null,
    filters: {
      q: "",
      direction: "all", // all | primary | secondary | <direction key>
      region: "all",    // all | primary | secondary | other | unknown
      tag: "all",       // all | <tag> | untagged
      hq: "all",        // all | beijing | other | unknown（公司总部）
      size: "all",      // all | 10000+ | 1000+ | 100+ | unknown（公司规模）
      source: "all",
      newOnly: false,
      starredOnly: false
    },
    starred: loadStarred()
  };

  function loadStarred() {
    try {
      var v = JSON.parse(localStorage.getItem("jobs-starred") || "[]");
      return Array.isArray(v) ? v : [];
    } catch (e) {
      return [];
    }
  }
  function saveStarred() {
    try {
      localStorage.setItem("jobs-starred", JSON.stringify(state.starred));
    } catch (e) { /* 私密浏览等场景忽略 */ }
  }

  function $(id) { return document.getElementById(id); }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* ---------- 主题 ---------- */
  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("jobs-theme"); } catch (e) {}
    if (saved === "dark" || saved === "light") {
      document.documentElement.setAttribute("data-theme", saved);
    }
    $("theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("jobs-theme", next); } catch (e) {}
    });
  }

  /* ---------- 筛选控件 ---------- */
  function fillSelects() {
    var m = state.meta;
    var dirSel = $("filter-direction");
    dirSel.innerHTML = "";
    dirSel.appendChild(opt("all", "全部方向"));
    dirSel.appendChild(opt("primary", "主投（硬件类）"));
    dirSel.appendChild(opt("secondary", "副投（器件/PIE/PE类）"));
    var groups = {};
    m.directions.forEach(function (d) {
      (groups[d.priority] = groups[d.priority] || []).push(d);
    });
    Object.keys(groups).forEach(function (prio) {
      var g = document.createElement("optgroup");
      g.label = prio + " · 具体方向";
      groups[prio].forEach(function (d) {
        var o = document.createElement("option");
        o.value = d.key;
        o.textContent = d.label;
        g.appendChild(o);
      });
      dirSel.appendChild(g);
    });

    var regSel = $("filter-region");
    regSel.innerHTML = "";
    [["all", "全部地区"], ["primary", "北京（主投）"], ["secondary", "上海（副投）"],
     ["other", "其他城市"], ["unknown", "地点未知"]].forEach(function (p) {
      regSel.appendChild(opt(p[0], p[1]));
    });

    var tagSel = $("filter-tag");
    tagSel.innerHTML = "";
    tagSel.appendChild(opt("all", "全部公司类型"));
    m.company_tags.forEach(function (t) { tagSel.appendChild(opt(t, t)); });
    tagSel.appendChild(opt("untagged", "未分类"));

    var hqSel = $("filter-hq");
    hqSel.innerHTML = "";
    [["all", "全部总部"], ["beijing", "总部·北京"], ["other", "总部·京外"],
     ["unknown", "总部未知"]].forEach(function (p) {
      hqSel.appendChild(opt(p[0], p[1]));
    });

    var sizeSel = $("filter-size");
    sizeSel.innerHTML = "";
    sizeSel.appendChild(opt("all", "全部规模"));
    ["10000+", "1000+", "100+"].forEach(function (s) { sizeSel.appendChild(opt(s, s + "人")); });
    sizeSel.appendChild(opt("unknown", "规模未知"));

    var srcSel = $("filter-source");
    srcSel.innerHTML = "";
    srcSel.appendChild(opt("all", "全部来源"));
    var sources = {};
    state.jobs.forEach(function (j) { sources[j.source || "unknown"] = 1; });
    Object.keys(sources).sort().forEach(function (s) {
      srcSel.appendChild(opt(s, s));
    });
  }

  function opt(value, text) {
    var o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    return o;
  }

  /* ---------- 筛选与渲染 ---------- */
  function matches(j) {
    var f = state.filters;
    if (f.newOnly && j.first_seen !== state.meta.updated_date) return false;
    if (f.starredOnly && state.starred.indexOf(j.id) === -1) return false;
    if (f.direction === "primary" && j.priority !== "主投") return false;
    if (f.direction === "secondary" && j.priority !== "副投") return false;
    if (f.direction !== "all" && f.direction !== "primary" && f.direction !== "secondary" &&
        j.direction !== f.direction) return false;
    if (f.region !== "all" && j.region_level !== f.region) return false;
    if (f.tag === "untagged" && j.company_tag) return false;
    if (f.tag !== "all" && f.tag !== "untagged" && j.company_tag !== f.tag) return false;
    var hq = j.hq_city ? (j.hq_city === "北京" ? "beijing" : "other") : "unknown";
    if (f.hq !== "all" && hq !== f.hq) return false;
    var size = j.size_bucket || "unknown";
    if (f.size === "unknown") {
      if (size !== "unknown") return false;
    } else if (f.size !== "all") {
      // 规模筛选按档位包含：选 1000+ 时 10000+ 公司也算
      var order = { "10000+": 3, "1000+": 2, "100+": 1 };
      if (!(order[size] >= order[f.size])) return false;
    }
    if (f.source !== "all" && (j.source || "unknown") !== f.source) return false;
    if (f.q) {
      var hay = ((j.title || "") + " " + (j.company || "") + " " +
                 (j.locations || []).join(" ") + " " + (j.company_tag || "")).toLowerCase();
      if (hay.indexOf(f.q.toLowerCase()) === -1) return false;
    }
    return true;
  }

  function sortByTime(a, b) {
    // 无发布时间但有截止时间的条目按截止时间参与排序
    var ta = a.publish_time || a.deadline || "", tb = b.publish_time || b.deadline || "";
    if (ta === tb) return 0;
    return ta > tb ? -1 : 1; // 最新在前；无时间的排最后
  }

  function fmtTime(t) {
    if (!t) return "—";
    // "2026-08-24 10:30" -> "08-24 10:30"
    return t.length >= 16 ? t.slice(5, 16) : t.slice(0, 10);
  }

  function render() {
    var today = state.meta.updated_date;
    var rows = state.jobs.filter(matches).sort(sortByTime);
    var tbody = $("jobs-tbody");
    tbody.innerHTML = "";

    rows.forEach(function (j) {
      var tr = document.createElement("tr");

      var tdTime = document.createElement("td");
      tdTime.className = "time-cell";
      if (j.publish_time) {
        tdTime.textContent = fmtTime(j.publish_time);
      } else if (j.deadline) {
        var dspan = document.createElement("span");
        dspan.style.color = "var(--good)";
        dspan.style.fontWeight = "600";
        dspan.textContent = "截止 " + j.deadline.slice(5, 10);
        tdTime.appendChild(dspan);
      } else {
        tdTime.textContent = "—";
      }
      if (j.first_seen === today) {
        tdTime.appendChild(badge("新收录", "badge badge-new"));
      } else if (j.last_seen === today) {
        tdTime.appendChild(badge("更新", "badge badge-upd"));
      }
      tr.appendChild(tdTime);

      var tdTitle = document.createElement("td");
      var a = document.createElement("a");
      a.className = "job-title";
      a.href = j.url || "#";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = j.title || "（无标题）";
      tdTitle.appendChild(a);
      tr.appendChild(tdTitle);

      var tdCompany = document.createElement("td");
      tdCompany.className = "company-cell";
      tdCompany.textContent = j.company || "—";
      if (j.hq_city) {
        var chip = document.createElement("span");
        chip.className = "hq-note";
        chip.textContent = "总部" + j.hq_city;
        tdCompany.appendChild(document.createTextNode(" "));
        tdCompany.appendChild(chip);
        tdCompany.title = "总部：" + j.hq_city +
          (j.size_bucket ? " · 规模：" + j.size_bucket + "人" : "") +
          (j.industry ? " · 行业：" + j.industry : "");
      }
      tr.appendChild(tdCompany);

      var tdCity = document.createElement("td");
      var locs = j.locations || [];
      if (j.region_level === "primary" || j.region_level === "secondary") {
        var dot = document.createElement("span");
        dot.className = "city-dot " + (j.region_level === "primary" ? "pri" : "sec");
        tdCity.appendChild(dot);
      }
      tdCity.appendChild(document.createTextNode(locs.length ? locs.join(" · ") : "—"));
      tr.appendChild(tdCity);

      var tdDir = document.createElement("td");
      if (j.priority) {
        tdDir.appendChild(badge(j.priority === "主投" ? "主投" : "副投",
          j.priority === "主投" ? "badge badge-pri" : "badge badge-sec"));
      }
      if (j.direction_label) {
        var span = document.createElement("span");
        span.style.fontSize = "12px";
        span.style.color = "var(--ink-2)";
        span.textContent = " " + j.direction_label;
        tdDir.appendChild(span);
      }
      tr.appendChild(tdDir);

      var tdTag = document.createElement("td");
      if (j.company_tag) {
        tdTag.appendChild(badge(j.company_tag, "badge badge-tag"));
      }
      tr.appendChild(tdTag);

      var tdSrc = document.createElement("td");
      tdSrc.className = "src-cell";
      tdSrc.textContent = j.source || "unknown";
      tr.appendChild(tdSrc);

      var tdStar = document.createElement("td");
      var btn = document.createElement("button");
      var on = state.starred.indexOf(j.id) !== -1;
      btn.className = "star-btn" + (on ? " on" : "");
      btn.textContent = on ? "★" : "☆";
      btn.setAttribute("aria-label", on ? "取消收藏" : "收藏");
      btn.addEventListener("click", function () {
        var idx = state.starred.indexOf(j.id);
        if (idx === -1) state.starred.push(j.id); else state.starred.splice(idx, 1);
        saveStarred();
        render();
      });
      tdStar.appendChild(btn);
      tr.appendChild(tdStar);

      tbody.appendChild(tr);
    });

    $("empty-state").hidden = rows.length > 0;
    $("result-info").textContent = "共 " + state.jobs.length + " 条岗位，当前显示 " +
      rows.length + " 条（按发布时间从新到旧）";
  }

  function badge(text, cls) {
    var b = document.createElement("span");
    b.className = cls;
    b.textContent = text;
    b.style.marginLeft = "6px";
    return b;
  }

  /* ---------- KPI ---------- */
  function renderKpi() {
    var t = state.meta.totals;
    $("kpi-total").textContent = t.total;
    $("kpi-today").textContent = t.added_today;
    $("kpi-primary").textContent = t.primary;
    $("kpi-secondary").textContent = t.secondary;
    $("kpi-beijing").textContent = t.beijing;
    $("kpi-shanghai").textContent = t.shanghai;
    $("updated-at").textContent = "数据更新于 " + state.meta.updated_at;
    $("footer-meta").textContent = "数据更新于 " + state.meta.updated_at +
      " · 累计收录 " + t.total + " 条岗位 · 每日北京时间 8:00 / 20:00 自动抓取";
    renderFreshness();
  }

  function renderFreshness() {
    var el = $("source-freshness");
    var fresh = state.meta.source_freshness;
    if (!fresh) { el.textContent = ""; return; }
    var parts = Object.keys(fresh).map(function (s) {
      var latest = fresh[s].latest || "";
      return s + " " + (latest ? latest.slice(5, 10) : "无时间");
    });
    el.textContent = "各来源最新岗位： " + parts.join(" · ");
  }

  /* ---------- 事件绑定 ---------- */
  function bindEvents() {
    $("search-input").addEventListener("input", function (e) {
      state.filters.q = e.target.value.trim();
      render();
    });
    $("filter-direction").addEventListener("change", function (e) {
      state.filters.direction = e.target.value;
      render();
    });
    $("filter-region").addEventListener("change", function (e) {
      state.filters.region = e.target.value;
      render();
    });
    $("filter-tag").addEventListener("change", function (e) {
      state.filters.tag = e.target.value;
      render();
    });
    $("filter-hq").addEventListener("change", function (e) {
      state.filters.hq = e.target.value;
      render();
    });
    $("filter-size").addEventListener("change", function (e) {
      state.filters.size = e.target.value;
      render();
    });
    $("filter-source").addEventListener("change", function (e) {
      state.filters.source = e.target.value;
      render();
    });
    $("filter-new").addEventListener("change", function (e) {
      state.filters.newOnly = e.target.checked;
      render();
    });
    $("filter-star").addEventListener("change", function (e) {
      state.filters.starredOnly = e.target.checked;
      render();
    });
    $("clear-filters").addEventListener("click", function () {
      state.filters = { q: "", direction: "all", region: "all", tag: "all",
        hq: "all", size: "all", source: "all", newOnly: false, starredOnly: false };
      $("search-input").value = "";
      $("filter-direction").value = "all";
      $("filter-region").value = "all";
      $("filter-tag").value = "all";
      $("filter-hq").value = "all";
      $("filter-size").value = "all";
      $("filter-source").value = "all";
      $("filter-new").checked = false;
      $("filter-star").checked = false;
      render();
    });
  }

  /* ---------- 启动 ---------- */
  function init() {
    initTheme();
    Promise.all([
      fetch("meta.json").then(function (r) { return r.json(); }),
      fetch("jobs.json").then(function (r) { return r.json(); })
    ]).then(function (rs) {
      state.meta = rs[0];
      state.jobs = Array.isArray(rs[1]) ? rs[1] : [];
      fillSelects();
      renderKpi();
      bindEvents();
      render();
    }).catch(function (err) {
      document.body.innerHTML = "<p style='padding:40px;text-align:center;color:#898781'>" +
        "数据加载失败：" + escapeHtml(String(err)) + "<br>请确认通过 HTTP 访问本页（本地预览请运行 python -m http.server）。</p>";
    });
  }

  init();
})();
