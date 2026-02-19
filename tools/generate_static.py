#!/usr/bin/env python3
"""Generate a static HTML site from programs.json for GitHub Pages deployment."""

import json
import os
import re
from datetime import date

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "programs.json")
CSS_FILE = os.path.join(PROJECT_ROOT, "static", "style.css")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")


def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def base_pay(pay_str):
    if not pay_str:
        return "\u2014"
    m = re.match(r'(\$[\d.,]+-?[\d.,]*/hr)', pay_str)
    if m:
        return m.group(1)
    m = re.match(r'(\$[\d.,]+K/yr)', pay_str)
    if m:
        return m.group(1)
    m = re.search(r'(\$[\d.,]+/hr)', pay_str)
    if m:
        return m.group(1)
    return pay_str


def short_city(city_str):
    if not city_str:
        return ""
    if city_str.startswith("Multiple"):
        abbrevs = {
            "Sacramento": "Sac", "Oakland": "Oak", "San Jose": "SJ",
            "Santa Rosa": "S Rosa", "Los Angeles": "LA",
            "Orange County": "OC", "San Diego": "SD",
            "Inland Empire": "IE", "Burbank": "Burbank",
            "Mission Hills": "Mission Hls", "Tarzana": "Tarzana",
            "Santa Monica": "S Monica", "Torrance": "Torrance",
            "Thousand Oaks": "T Oaks", "Bay Area": "Bay Area",
        }
        m = re.search(r'\((.+)\)', city_str)
        if not m:
            return "Multi"
        raw = [c.strip().rstrip('.') for c in m.group(1).split(',') if c.strip() != 'etc']
        short = [abbrevs.get(c, c) for c in raw]
        if len(short) > 2:
            return ', '.join(short[:2]) + ', etc'
        return ', '.join(short)
    city_str = city_str.replace("Los Angeles", "LA")
    city_str = city_str.replace("Boyle Heights", "Boyle Hts")
    city_str = city_str.replace("Walnut Creek", "W Creek")
    city_str = city_str.replace("Newport Beach", "Newport")
    city_str = city_str.replace("Mountain View", "Mtn View")
    if city_str.count("/") >= 2:
        first = city_str.split("/")[0].strip()
        first = first.replace("West ", "W ")
        return first + "+"
    city_str = city_str.replace("San Diego", "SD")
    city_str = city_str.replace("San Jose", "SJ")
    city_str = city_str.replace("Santa Monica", "S Monica")
    city_str = city_str.replace("Sacramento", "Sac")
    city_str = city_str.replace("San Francisco", "SF")
    return city_str


def format_date(date_str):
    """Format 2026-03-10 as Mar 10 for display."""
    d = parse_date(date_str)
    if not d:
        return esc(date_str) if date_str else ""
    return d.strftime("%b %d").replace(" 0", " ")


def esc(text):
    """HTML-escape a string."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def generate():
    with open(DATA_FILE) as f:
        data = json.load(f)

    with open(CSS_FILE) as f:
        css = f.read()

    programs = data["programs"]
    metadata = data["metadata"]
    today = date.today()

    # Compute stats
    total = len(programs)
    open_now = 0
    upcoming = 0
    urgent = 0
    for p in programs:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        if app_close and app_close >= today:
            upcoming += 1
            if (app_close - today).days <= 14:
                urgent += 1
        if app_open and app_open <= today and (not app_close or app_close >= today):
            open_now += 1

    # Count cohort start date ranges
    cohort_jul_sep = 0
    cohort_oct_dec = 0
    for p in programs:
        cs = parse_date(p.get("cohort_start", ""))
        if cs:
            if cs.year == 2026 and 7 <= cs.month <= 9:
                cohort_jul_sep += 1
            elif cs.year == 2026 and 10 <= cs.month <= 12:
                cohort_oct_dec += 1

    nclex_date = metadata.get("nclex_target_date", "")
    nclex_parsed = parse_date(nclex_date)
    if not nclex_parsed and len(nclex_date) == 7:
        nclex_parsed = parse_date(nclex_date + "-01")
    nclex_days = (nclex_parsed - today).days if nclex_parsed else None

    regions = sorted(set(p["region"] for p in programs))
    region_counts = {}
    for p in programs:
        r = p["region"]
        region_counts[r] = region_counts.get(r, 0) + 1
    cities = sorted(set(p["city"] for p in programs))
    bsn_values = sorted(set(p.get("bsn_required", "") for p in programs if p.get("bsn_required")))
    statuses = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]

    # Compute pay range for bars
    pay_values = []
    for p in programs:
        m = re.search(r'(\d[\d.,]+)/hr', p.get("pay_range", ""))
        if m:
            pay_values.append(float(m.group(1).replace(',', '')))
    min_pay = min(pay_values) if pay_values else 0
    max_pay = max(pay_values) if pay_values else 1
    pay_range_span = max_pay - min_pay if max_pay > min_pay else 1

    # Build table rows
    rows_html = []
    for p in programs:
        stars = "\u2605" * p.get("reputation", 0) + "\u2606" * (5 - p.get("reputation", 0))
        specs = ", ".join(p.get("specialty_units", []))
        pay = base_pay(p.get("pay_range", ""))
        city = short_city(p.get("city", ""))
        full_city = esc(p.get("city", ""))
        status = p.get("application_status", "Not Started")

        # Compute data completeness
        comp_fields = [
            bool(p.get('app_open_date')),
            bool(p.get('app_close_date')),
            bool(p.get('cohort_start')),
            bool(p.get('pay_range')),
            bool(p.get('application_url')),
            bool(p.get('bsn_required')),
            bool(p.get('program_length_months')),
            bool(p.get('reputation', 0)),
        ]
        comp_pct = int(sum(comp_fields) / len(comp_fields) * 100)
        comp_color = '#22c55e' if comp_pct >= 80 else '#f59e0b' if comp_pct >= 50 else '#ef4444'
        comp_ring = f'<span class="comp-ring" title="{comp_pct}% data complete" style="--comp-pct:{comp_pct};--comp-color:{comp_color}"><span class="comp-val">{comp_pct}</span></span>' if comp_pct < 100 else ''

        status_options = ""
        for s in statuses:
            sel = " selected" if s == status else ""
            status_options += f'<option value="{esc(s)}"{sel}>{esc(s)}</option>'

        apply_cell = ""
        if p.get("application_url"):
            apply_cell = f'<a href="{esc(p["application_url"])}" target="_blank" class="apply-link">Apply &rarr;</a><button class="mark-applied-btn" data-id="{p["id"]}" data-url="{esc(p["application_url"])}" onclick="markApplied(this)" title="Open link & mark as Submitted">&#10003;</button>'

        notes_raw = p.get('personal_notes', '')
        notes_esc = esc(notes_raw)
        if len(notes_raw) > 120:
            notes_cell = f'<span class="note-trunc" title="{notes_esc}">{esc(notes_raw[:120])}&hellip; <a href="#" class="note-expand">more</a></span><span class="note-full" style="display:none">{notes_esc} <a href="#" class="note-collapse">less</a></span>'
        else:
            notes_cell = notes_esc

        app_open_raw = p.get('app_open_date', '')
        app_close_raw = p.get('app_close_date', '')
        cohort_raw = p.get('cohort_start', '')
        app_open_fmt = format_date(app_open_raw)
        app_close_fmt = format_date(app_close_raw)
        cohort_fmt = format_date(cohort_raw) if parse_date(cohort_raw) else esc(cohort_raw)

        # Compute tooltip for open date
        open_d = parse_date(app_open_raw)
        close_d = parse_date(app_close_raw)
        open_title = app_open_raw
        if open_d and close_d:
            if open_d > today:
                days_until = (open_d - today).days
                open_title = f"Opens in {days_until} days ({app_open_raw})"
            elif close_d >= today:
                open_title = f"Currently open ({app_open_raw})"
            else:
                open_title = f"Closed ({app_open_raw})"

        bsn = p.get("bsn_required", "")
        bsn_cls = "bsn-no" if bsn == "No" else "bsn-pref" if bsn == "Preferred" else "bsn-req" if bsn == "Yes" else ""

        # Compute pay bar
        pay_bar_html = ""
        pay_match = re.search(r'(\d[\d.,]+)/hr', p.get("pay_range", ""))
        if pay_match:
            pay_val = float(pay_match.group(1).replace(',', ''))
            pct = int(((pay_val - min_pay) / pay_range_span) * 100)
            pct = max(5, min(100, pct))  # clamp between 5-100
            tier = "high" if pct >= 70 else "mid" if pct >= 40 else "low"
            pay_bar_html = f'<span class="pay-bar pay-bar-{tier}"><span class="pay-bar-fill" style="width:{pct}%"></span></span>'

        region = p.get("region", "")
        region_cls = ""
        if "Bay" in region: region_cls = "region-bay"
        elif "SoCal" in region or "Los Angeles" in region or "Orange" in region or "San Diego" in region: region_cls = "region-socal"
        elif "Central" in region: region_cls = "region-central"
        elif "Sacr" in region or "NorCal" in region: region_cls = "region-sacr"
        elif "Inland" in region: region_cls = "region-ie"
        elif "Statewide" in region: region_cls = "region-state"
        region_dot = f'<span class="region-badge {region_cls}"></span>' if region_cls else ""

        row = f"""<tr data-id="{p['id']}" data-region="{esc(p.get('region',''))}" data-city="{esc(p.get('city',''))}" data-bsn="{esc(bsn)}" data-status="{esc(status)}">
<td class="col-check"><input type="checkbox" class="compare-check" value="{p['id']}"></td>
<td class="col-fav"><button class="fav-btn" data-id="{p['id']}" onclick="toggleFav({p['id']})" title="Toggle favorite">&#9734;</button></td>
<td class="col-hospital frozen-col">{comp_ring}<a href="#" class="hospital-link" data-id="{p['id']}">{esc(p['hospital'])}</a><button class="qnote-btn" data-id="{p['id']}" onclick="event.stopPropagation(); showQuickNote({p['id']}, this)" title="Quick note">&#9998;</button></td>
<td class="col-program">{esc(p.get('program_name',''))}</td>
<td class="col-region clickable-filter" onclick="filterByRegion('{esc(p.get('region',''))}')">{region_dot}{esc(p.get('region',''))}</td>
<td class="col-city" title="{full_city}">{esc(city)}</td>
<td class="col-bsn {bsn_cls} clickable-filter" onclick="filterByBsn('{esc(bsn)}')">{esc(bsn)}</td>
<td class="col-date" data-raw="{esc(app_open_raw)}" title="{esc(open_title)}">{app_open_fmt}</td>
<td class="col-date" data-raw="{esc(app_close_raw)}">{app_close_fmt}</td>
<td class="col-date" data-raw="{esc(cohort_raw)}">{cohort_fmt}</td>
<td class="col-rep stars">{stars}</td>
<td class="col-pay" title="{esc(p.get('pay_range', ''))}">{esc(pay)}{pay_bar_html}</td>
<td class="col-len">{p.get('program_length_months','')}mo</td>
<td class="col-specialties" title="{esc(specs)}">{esc(specs)}</td>
<td class="col-status"><select class="status-select" data-id="{p['id']}" aria-label="Status for {esc(p.get('hospital', ''))}">{status_options}</select></td>
<td class="col-notes" data-id="{p['id']}" ondblclick="inlineEditNote(this)" title="Double-click to edit">{notes_cell}</td>
<td class="col-apply">{apply_cell}</td>
</tr>"""
        rows_html.append(row)

    region_options = ''.join(f'<option value="{esc(r)}">{esc(r)} ({region_counts[r]})</option>' for r in regions)
    city_options = ''.join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in cities)
    bsn_options = ''.join(f'<option value="{esc(b)}">{esc(b)}</option>' for b in bsn_values)
    status_options_filter = ''.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in statuses)

    # Embed program data as JSON for detail modal
    programs_json = json.dumps([{
        "id": p["id"],
        "hospital": p.get("hospital", ""),
        "program_name": p.get("program_name", ""),
        "region": p.get("region", ""),
        "city": p.get("city", ""),
        "bsn_required": p.get("bsn_required", ""),
        "reputation": p.get("reputation", 0),
        "program_length_months": p.get("program_length_months", ""),
        "pay_range": p.get("pay_range", ""),
        "app_open_date": p.get("app_open_date", ""),
        "app_close_date": p.get("app_close_date", ""),
        "cohort_start": p.get("cohort_start", ""),
        "specialty_units": p.get("specialty_units", []),
        "requirements": p.get("requirements", ""),
        "application_url": p.get("application_url", ""),
        "application_status": p.get("application_status", "Not Started"),
        "personal_notes": p.get("personal_notes", ""),
        "reputation_notes": p.get("reputation_notes", ""),
        "info_session_dates": p.get("info_session_dates", []),
        "last_updated": p.get("last_updated", ""),
    } for p in programs])

    # PWA manifest
    import urllib.parse
    manifest_data = {
        "name": "CA New Grad RN Tracker",
        "short_name": "RN Tracker",
        "start_url": ".",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#1e293b",
        "description": f"Track {total} California new graduate RN residency programs"
    }
    manifest_json = urllib.parse.quote(json.dumps(manifest_data), safe='')

    nclex_stat = f"<strong>{nclex_days}d</strong>" if nclex_days is not None else nclex_date
    urgent_class = ' stat-highlight-red' if urgent > 0 else ''
    urgent_text = f" ({urgent} urgent)" if urgent > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Track {total} California new graduate RN residency programs — application dates, deadlines, pay rates, and requirements.">
    <title>({nclex_days if nclex_days is not None else '?'}d to NCLEX) CA New Grad RN Tracker</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏥</text></svg>">
    <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏥</text></svg>">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="RN Tracker">
    <meta name="theme-color" content="#1e293b">
    <link rel="manifest" href="data:application/json,{manifest_json}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
{css}
    </style>
</head>
<body>
    <div class="reading-progress" id="reading-progress"></div>
    <a href="#main-table" class="skip-link">Skip to programs table</a>
    <div id="live-region" class="live-region" aria-live="polite" aria-atomic="true"></div>
    <nav class="container-fluid" role="navigation" aria-label="Main navigation">
        <ul>
            <li><strong>CA New Grad RN Tracker</strong></li>
        </ul>
        <ul>
            <li><a href="#" class="active" id="nav-table" onclick="showView('table'); return false;">Table</a></li>
            <li><a href="#" id="nav-cards" onclick="showView('cards'); return false;">Cards</a></li>
            <li><a href="#" id="nav-pipeline" onclick="showView('pipeline'); return false;">Pipeline</a></li>
            <li><a href="#" id="nav-calendar" onclick="showView('calendar'); return false;">Calendar</a></li>
            <li><a href="#" id="nav-stats" onclick="showView('stats'); return false;">Stats</a></li>
            <li><a href="#" id="nav-timeline" onclick="showView('timeline'); return false;">Timeline</a></li>
            <li class="nclex-nav" title="Days until NCLEX ({nclex_date})"><span class="nclex-badge">{nclex_days if nclex_days is not None else '?'}d</span> NCLEX</li>
            <li class="nav-progress-wrap" title="Application progress"><span class="nav-progress-bar" id="nav-progress-bar"><span class="nav-progress-fill" id="nav-progress-fill"></span></span><span class="nav-progress-text" id="nav-progress-text">0/{total}</span></li>
            <li class="notif-nav"><a href="#" onclick="toggleNotifications(); return false;" id="notif-toggle" title="Notifications">&#x1F514;<span class="notif-count" id="notif-count" style="display:none">0</span></a>
                <div class="notif-panel" id="notif-panel" style="display:none">
                    <div class="notif-header"><strong>Notifications</strong><button onclick="clearNotifications(); return false;" class="notif-clear">Clear all</button></div>
                    <div class="notif-list" id="notif-list"></div>
                </div>
            </li>
            <li><a href="#" onclick="toggleTheme(); return false;" id="theme-toggle" title="Toggle dark mode">Dark</a></li>
            <li class="accent-picker-wrap"><span class="accent-swatch" id="accent-swatch" onclick="toggleAccentPalette()" title="Accent color"></span>
                <div class="accent-palette" id="accent-palette">
                    <span class="accent-dot" style="background:#2563eb" onclick="setAccent('#2563eb','#3b82f6','#1d4ed8')" title="Blue"></span>
                    <span class="accent-dot" style="background:#7c3aed" onclick="setAccent('#7c3aed','#8b5cf6','#6d28d9')" title="Purple"></span>
                    <span class="accent-dot" style="background:#db2777" onclick="setAccent('#db2777','#ec4899','#be185d')" title="Pink"></span>
                    <span class="accent-dot" style="background:#dc2626" onclick="setAccent('#dc2626','#ef4444','#b91c1c')" title="Red"></span>
                    <span class="accent-dot" style="background:#ea580c" onclick="setAccent('#ea580c','#f97316','#c2410c')" title="Orange"></span>
                    <span class="accent-dot" style="background:#059669" onclick="setAccent('#059669','#10b981','#047857')" title="Green"></span>
                    <span class="accent-dot" style="background:#0891b2" onclick="setAccent('#0891b2','#06b6d4','#0e7490')" title="Teal"></span>
                    <span class="accent-dot" style="background:#4f46e5" onclick="setAccent('#4f46e5','#6366f1','#4338ca')" title="Indigo"></span>
                    <span class="accent-dot" style="background:#475569" onclick="setAccent('#475569','#64748b','#334155')" title="Slate"></span>
                </div>
            </li>
            <li><a href="#" onclick="toggleShortcutHelp(); return false;" title="Keyboard shortcuts (?)" class="nav-help">?</a></li>
        </ul>
    </nav>

    <div class="urgency-banner" id="urgency-banner" style="display:none"></div>

    <main class="container-fluid sheet-page" role="main" id="main-table">
        <div class="sheet-toolbar">
            <div class="sheet-filters">
                <div class="search-wrap"><input type="search" name="q" placeholder="Search... ( / )" value="" id="main-search" autocomplete="off" aria-label="Search programs"><div class="search-suggest" id="search-suggest" role="listbox"></div></div>
                <select data-instant="region" aria-label="Filter by region">
                    <option value="">All Regions</option>
                    {region_options}
                </select>
                <select data-instant="city" aria-label="Filter by city">
                    <option value="">All Cities</option>
                    {city_options}
                </select>
                <select data-instant="bsn" aria-label="Filter by BSN requirement">
                    <option value="">All BSN</option>
                    {bsn_options}
                </select>
                <select data-instant="status" aria-label="Filter by application status">
                    <option value="">All Statuses</option>
                    {status_options_filter}
                </select>
                <select data-instant="cohort-status" aria-label="Filter by cohort status">
                    <option value="">All Cohorts</option>
                    <option value="released">Released</option>
                    <option value="not-released">Not Released</option>
                    <option value="rolling">Rolling</option>
                    <option value="paused">Paused</option>
                </select>
                <span class="sheet-count">{total} rows</span>
                <button type="button" class="clear-filter" id="clear-all-btn" onclick="clearAllFilters()" style="display:none">Clear All</button>
                <button type="button" class="jump-btn" onclick="jumpToOpen()" title="Jump to first open program">&darr; Open</button>
                <span class="filter-spacer"></span>
                <select id="sort-preset" onchange="applySortPreset(this.value)" aria-label="Sort programs" style="height:28px;font-size:0.75rem;padding:4px 8px;margin:0;border:1px solid #d1d5db;border-radius:3px">
                    <option value="">Sort by...</option>
                    <option value="deadline">Nearest Deadline</option>
                    <option value="pay-high">Highest Pay</option>
                    <option value="rep-high">Best Reputation</option>
                    <option value="opening">Opening Soon</option>
                    <option value="cohort">Cohort Start</option>
                    <option value="hospital">Hospital A-Z</option>
                    <option value="smart">Smart Match</option>
                </select>
                <select id="group-by" onchange="applyGrouping()" aria-label="Group programs" style="height:28px;font-size:0.75rem;padding:4px 8px;margin:0;border:1px solid #d1d5db;border-radius:3px">
                    <option value="">Group by...</option>
                    <option value="region">Region</option>
                    <option value="status">Status</option>
                    <option value="bsn">BSN Req</option>
                </select>
                <button type="button" id="compare-btn" disabled onclick="goCompare()">Compare</button>
                <div class="more-actions-wrap">
                    <button type="button" onclick="toggleMoreMenu()" title="More actions" id="more-btn">More &darr;</button>
                    <div id="more-menu" class="more-menu" style="display:none">
                        <button type="button" onclick="toggleColMenu()">Columns</button>
                        <button type="button" onclick="toggleDensity(); toggleMoreMenu();" id="density-btn">Compact</button>
                        <button type="button" onclick="exportCSV(); toggleMoreMenu();">Export CSV</button>
                        <button type="button" onclick="exportICS(); toggleMoreMenu();">Export Calendar</button>
                        <button type="button" onclick="backupData(); toggleMoreMenu();">Backup</button>
                        <button type="button" onclick="document.getElementById('restore-file').click(); toggleMoreMenu();">Restore</button>
                        <button type="button" onclick="shareUrl(); toggleMoreMenu();">Share URL</button>
                        <button type="button" onclick="printView(); toggleMoreMenu();">Print / PDF</button>
                        <button type="button" onclick="exportSummary(); toggleMoreMenu();">Copy Summary</button>
                        <button type="button" onclick="showActivityFeed(); toggleMoreMenu();">Activity Feed</button>
                        <button type="button" onclick="batchApplyOpen(); toggleMoreMenu();">Batch Apply Open</button>
                        <button type="button" onclick="showProgressCard(); toggleMoreMenu();">Progress Card</button>
                        <hr style="margin:4px 0;border-color:#e5e7eb">
                        <button type="button" onclick="saveFilterPreset(); toggleMoreMenu();">Save Current Filter</button>
                        <div id="saved-filters-menu"></div>
                    </div>
                    <div id="col-menu" class="col-menu" style="display:none">
                        <label><input type="checkbox" data-toggle-col="col-program" checked> Program</label>
                        <label><input type="checkbox" data-toggle-col="col-region" checked> Region</label>
                        <label><input type="checkbox" data-toggle-col="col-city" checked> City</label>
                        <label><input type="checkbox" data-toggle-col="col-bsn" checked> BSN</label>
                        <label><input type="checkbox" data-toggle-col="col-date" checked> Dates</label>
                        <label><input type="checkbox" data-toggle-col="col-rep" checked> Rep</label>
                        <label><input type="checkbox" data-toggle-col="col-pay" checked> Pay</label>
                        <label><input type="checkbox" data-toggle-col="col-len" checked> Length</label>
                        <label><input type="checkbox" data-toggle-col="col-specialties" checked> Specialties</label>
                        <label><input type="checkbox" data-toggle-col="col-notes" checked> Notes</label>
                    </div>
                </div>
                <input type="file" id="restore-file" accept=".json" style="display:none" onchange="restoreData(this)">
            </div>
        </div>

        <div class="recent-viewed" id="recent-viewed" style="display:none"></div>
        <div class="status-summary" id="status-summary"></div>

        <div class="quick-chips">
            <button class="chip chip-red" onclick="filterFavorites(this)" id="fav-chip">&#9733; Favorites <span class="chip-count" id="fav-count">0</span></button>
            <span class="chip-sep"></span>
            <button class="chip chip-green" onclick="filterOpen(this)">Open Now <span class="chip-count">{open_now}</span></button>
            <button class="chip chip-green" onclick="filterApplyNow(this)" style="background:#dcfce7;border-color:#22c55e;color:#065f46;font-weight:700">Apply Now!</button>
            <button class="chip chip-amber" onclick="filterUpcoming(this)">Upcoming <span class="chip-count">{upcoming}</span></button>
            <button class="chip" onclick="filterBsn('No', this)">ADN OK</button>
            <button class="chip" onclick="filterBsn('Preferred', this)">BSN Preferred</button>
            <span class="chip-sep"></span>
            <button class="chip chip-purple" onclick="filterCohort('jul-sep', this)">Jul-Sep <span class="chip-count">{cohort_jul_sep}</span></button>
            <button class="chip chip-purple" onclick="filterCohort('oct-dec', this)">Oct-Dec <span class="chip-count">{cohort_oct_dec}</span></button>
            <span class="chip-sep"></span>
            <button class="chip chip-focus" onclick="toggleFocusMode(this)" id="focus-chip">Focus Mode</button>
        </div>

        <div class="sheet-wrapper">
            <table class="sheet">
                <thead>
                    <tr>
                        <th class="col-check"><input type="checkbox" id="select-all"></th>
                        <th class="col-fav" title="Favorites">&#9733;</th>
                        <th class="col-hospital frozen-col sortable" data-col="2" data-sort="text" data-label="Hospital">Hospital <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-program sortable" data-col="3" data-sort="text" data-label="Program">Program <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-region sortable" data-col="4" data-sort="text" data-label="Region">Region <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-city sortable" data-col="5" data-sort="text" data-label="City">City <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-bsn sortable" data-col="6" data-sort="text" data-label="BSN">BSN <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="7" data-sort="date" data-label="App Open">App Open <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="8" data-sort="date" data-label="App Close">App Close <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="9" data-sort="date" data-label="Cohort">Cohort <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-rep sortable" data-col="10" data-sort="stars" data-label="Reputation">Rep <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-pay sortable" data-col="11" data-sort="pay" data-label="Pay">Pay <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-len sortable" data-col="12" data-sort="num" data-label="Length">Len <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-specialties sortable" data-col="13" data-sort="text" data-label="Specialties">Specialties <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-status sortable" data-col="14" data-sort="status" data-label="Status">Status <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-notes sortable" data-col="15" data-sort="text" data-label="Notes">Notes <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-apply">Apply</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
                <tfoot id="table-footer">
                    <tr class="table-summary-row">
                        <td colspan="7" class="summary-label">Summary</td>
                        <td class="summary-cell" id="tfoot-open">-</td>
                        <td class="summary-cell" id="tfoot-close">-</td>
                        <td class="summary-cell" id="tfoot-cohort">-</td>
                        <td class="summary-cell" id="tfoot-rep">-</td>
                        <td class="summary-cell" id="tfoot-pay">-</td>
                        <td class="summary-cell" id="tfoot-len">-</td>
                        <td class="summary-cell" id="tfoot-spec">-</td>
                        <td class="summary-cell" id="tfoot-status">-</td>
                        <td class="summary-cell" id="tfoot-notes">-</td>
                        <td class="summary-cell"></td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div class="no-results" id="no-results">No programs match your filters. <a href="#" onclick="clearAllFilters(); return false;">Clear filters</a></div>

        <div class="bulk-bar" id="bulk-bar" style="display:none">
            <span class="bulk-count">0 selected</span>
            <select id="bulk-status-select" class="bulk-status-select">
                <option value="">Set Status...</option>
                <option value="Not Started">Not Started</option>
                <option value="In Progress">In Progress</option>
                <option value="Submitted">Submitted</option>
                <option value="Interview">Interview</option>
                <option value="Offer">Offer</option>
                <option value="Rejected">Rejected</option>
            </select>
            <button type="button" onclick="bulkSetStatus()">Apply</button>
            <button type="button" onclick="bulkToggleFavorite()">&#9733; Fav</button>
            <button type="button" class="bulk-clear" onclick="clearSelection()">Clear</button>
        </div>
    </main>

    <!-- Cards View -->
    <div id="cards-view" class="container-fluid" style="display:none">
        <div class="cards-toolbar">
            <input type="search" id="cards-search" placeholder="Filter cards..." class="cards-search-input">
            <select id="cards-region-filter" class="cards-filter-select">
                <option value="">All Regions</option>
                {region_options}
            </select>
            <select id="cards-sort" class="cards-filter-select" onchange="renderCards()">
                <option value="deadline">By Deadline</option>
                <option value="reputation">By Reputation</option>
                <option value="pay">By Pay</option>
                <option value="smart">Smart Match</option>
            </select>
        </div>
        <div class="cards-grid" id="cards-grid"></div>
    </div>

    <!-- Pipeline View -->
    <div id="pipeline-view" class="container-fluid" style="display:none">
        <div class="pipeline-toolbar">
            <input type="search" id="pipeline-search" placeholder="Filter programs..." class="pipeline-search-input">
            <select id="pipeline-region-filter" class="pipeline-filter-select">
                <option value="">All Regions</option>
                {region_options}
            </select>
        </div>
        <div class="pipeline-container" id="pipeline-container"></div>
    </div>

    <!-- Stats View -->
    <div id="stats-view" class="container" style="display:none">
        <div class="stats-dashboard" id="stats-dashboard"></div>
    </div>

    <!-- Calendar View -->
    <div id="calendar-view" class="container-fluid" style="display:none">
        <div class="cal-nav">
            <button onclick="calPrev()">&larr;</button>
            <h2 id="cal-month-title"></h2>
            <button onclick="calNext()">&rarr;</button>
            <button onclick="calToday()" class="cal-today-btn">Today</button>
            <select id="cal-region-filter" class="cal-filter-select" onchange="renderCalendar()">
                <option value="">All Regions</option>
                {region_options}
            </select>
        </div>
        <div class="cal-grid" id="cal-grid"></div>
        <div class="cal-legend">
            <span><span class="cal-legend-dot cal-dot-open"></span> App window open</span>
            <span><span class="cal-legend-dot cal-dot-close"></span> App deadline</span>
            <span><span class="cal-legend-dot cal-dot-cohort"></span> Cohort start</span>
        </div>
    </div>

    <!-- Timeline/Gantt View -->
    <div id="timeline-view" class="container-fluid" style="display:none">
        <div class="timeline-toolbar">
            <select id="timeline-region-filter" onchange="renderTimeline()" aria-label="Filter timeline by region">
                <option value="">All Regions</option>
                {region_options}
            </select>
            <select id="timeline-sort" onchange="renderTimeline()" aria-label="Sort timeline">
                <option value="open">By App Open</option>
                <option value="close">By App Close</option>
                <option value="hospital">By Hospital</option>
                <option value="reputation">By Reputation</option>
            </select>
        </div>
        <div class="gantt-container" id="gantt-container"></div>
        <div class="gantt-legend">
            <span class="gantt-legend-item"><span class="gantt-legend-bar" style="background:var(--accent,#3b82f6)"></span> Application Window</span>
            <span class="gantt-legend-item"><span class="gantt-legend-bar" style="background:#22c55e"></span> Cohort Start</span>
            <span class="gantt-legend-item"><span class="gantt-legend-bar" style="background:#ef4444;width:2px;height:16px"></span> Today</span>
        </div>
    </div>

    <!-- Detail Modal -->
    <div id="detail-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Program Details">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>
            <div id="modal-body"></div>
        </div>
    </div>

    <!-- Welcome Modal -->
    <div id="welcome-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Welcome">
        <div class="modal-content modal-welcome">
            <h2>Welcome to CA New Grad RN Tracker</h2>
            <p class="welcome-subtitle">Track {total} nursing residency programs across California</p>

            <div class="welcome-features">
                <div class="welcome-feature">
                    <span class="welcome-icon">&#9733;</span>
                    <div>
                        <strong>Star your favorites</strong>
                        <p>Click the star next to any program to save it for quick access</p>
                    </div>
                </div>
                <div class="welcome-feature">
                    <span class="welcome-icon">&#128203;</span>
                    <div>
                        <strong>Track your progress</strong>
                        <p>Set application status and use the checklist in each program detail</p>
                    </div>
                </div>
                <div class="welcome-feature">
                    <span class="welcome-icon">&#128197;</span>
                    <div>
                        <strong>Multiple views</strong>
                        <p>Switch between Table, Pipeline, Calendar, and Stats views</p>
                    </div>
                </div>
                <div class="welcome-feature">
                    <span class="welcome-icon">&#128268;</span>
                    <div>
                        <strong>Export &amp; backup</strong>
                        <p>Download CSV, calendar (.ics), or backup your data via the More menu</p>
                    </div>
                </div>
            </div>

            <div class="welcome-actions">
                <button onclick="dismissWelcome()" class="welcome-start">Get Started</button>
                <p class="welcome-hint">Press <kbd>?</kbd> anytime for keyboard shortcuts</p>
            </div>
        </div>
    </div>

    <!-- Shortcuts Modal -->
    <div id="shortcuts-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Keyboard Shortcuts">
        <div class="modal-content modal-shortcuts">
            <button class="modal-close" onclick="closeModalEl(document.getElementById('shortcuts-modal'))" aria-label="Close">&times;</button>
            <h2>Keyboard Shortcuts</h2>
            <div class="shortcuts-grid">
                <div class="shortcut-group">
                    <h3>Navigation</h3>
                    <div class="shortcut-row"><kbd>j</kbd> / <kbd>&darr;</kbd> <span>Next row</span></div>
                    <div class="shortcut-row"><kbd>k</kbd> / <kbd>&uarr;</kbd> <span>Previous row</span></div>
                    <div class="shortcut-row"><kbd>Enter</kbd> <span>Open program details</span></div>
                    <div class="shortcut-row"><kbd>&larr;</kbd> <span>Previous program (in modal)</span></div>
                    <div class="shortcut-row"><kbd>&rarr;</kbd> <span>Next program (in modal)</span></div>
                    <div class="shortcut-row"><kbd>Esc</kbd> <span>Close modal / blur input</span></div>
                </div>
                <div class="shortcut-group">
                    <h3>Actions</h3>
                    <div class="shortcut-row"><kbd>/</kbd> <span>Focus search</span></div>
                    <div class="shortcut-row"><kbd>f</kbd> <span>Toggle favorite (selected row)</span></div>
                    <div class="shortcut-row"><kbd>d</kbd> <span>Toggle dark mode</span></div>
                    <div class="shortcut-row"><kbd>n</kbd> <span>Toggle notifications</span></div>
                    <div class="shortcut-row"><kbd>1</kbd>-<kbd>6</kbd> <span>Switch views (Table/Cards/Pipeline/Cal/Stats/Timeline)</span></div>
                    <div class="shortcut-row"><kbd>?</kbd> <span>Show this help</span></div>
                </div>
                <div class="shortcut-group">
                    <h3>Mobile</h3>
                    <div class="shortcut-row">Swipe &larr; <span>Next program (in modal)</span></div>
                    <div class="shortcut-row">Swipe &rarr; <span>Previous program (in modal)</span></div>
                    <div class="shortcut-row">Double-tap <span>Open program details</span></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Compare Modal -->
    <div id="compare-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Compare Programs">
        <div class="modal-content modal-wide">
            <button class="modal-close" onclick="closeCompareModal()" aria-label="Close">&times;</button>
            <div id="compare-body"></div>
        </div>
    </div>

    <div id="activity-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Activity Feed">
        <div class="modal-content modal-wide">
            <button class="modal-close" onclick="closeModal('activity-modal')" aria-label="Close">&times;</button>
            <h2 style="margin-top:0">Activity Feed</h2>
            <div id="activity-feed-body"></div>
        </div>
    </div>

    <div id="progress-card-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Progress Report Card">
        <div class="modal-content modal-wide">
            <button class="modal-close" onclick="closeModal('progress-card-modal')" aria-label="Close">&times;</button>
            <h2 style="margin-top:0">Progress Report Card</h2>
            <div id="progress-card-container" style="text-align:center"></div>
            <div class="progress-card-actions">
                <button onclick="downloadProgressCard()" class="pc-btn pc-btn-primary">&#11015; Download PNG</button>
                <button onclick="copyProgressCard()" class="pc-btn">&#128203; Copy to Clipboard</button>
                <button onclick="exportSummary(); closeModal('progress-card-modal')" class="pc-btn">&#128196; Copy as Text</button>
            </div>
        </div>
    </div>

    <footer class="container">
        <small>{total} programs across {len(regions)} regions &bull; Data updated {metadata.get('last_updated', today.strftime('%Y-%m-%d'))} &bull; Generated {today.strftime("%b %d, %Y")}</small>
        <small class="shortcuts-hint"><kbd>/</kbd> Search &bull; <kbd>j</kbd><kbd>k</kbd> Navigate &bull; <kbd>Enter</kbd> Details &bull; <kbd>f</kbd> Favorite &bull; <kbd>n</kbd> Notify &bull; <kbd>1</kbd>-<kbd>6</kbd> Views &bull; <kbd>d</kbd> Dark &bull; <kbd>?</kbd> Help</small>
    </footer>

    <button class="back-to-top" id="back-to-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="Back to top">
        <svg class="scroll-progress-ring" viewBox="0 0 36 36"><circle class="scroll-ring-bg" cx="18" cy="18" r="15.5"/><circle class="scroll-ring-fill" id="scroll-ring-fill" cx="18" cy="18" r="15.5"/></svg>
        <span class="btt-arrow">&uarr;</span>
    </button>

    <!-- Floating Action Button -->
    <div class="fab-wrap" id="fab-wrap">
        <div class="fab-options" id="fab-options">
            <button class="fab-option" onclick="jumpToOpen(); closeFab();" title="Jump to open"><span class="fab-icon">&darr;</span> Open Apps</button>
            <button class="fab-option" onclick="toggleFocusMode(); closeFab();" title="Focus mode"><span class="fab-icon">&#9673;</span> Focus</button>
            <button class="fab-option" onclick="showActivityFeed(); closeFab();" title="Activity feed"><span class="fab-icon">&#9776;</span> Activity</button>
            <button class="fab-option" onclick="exportSummary(); closeFab();" title="Copy summary"><span class="fab-icon">&#9998;</span> Summary</button>
        </div>
        <button class="fab-btn" id="fab-btn" onclick="toggleFab()" title="Quick actions">+</button>
    </div>

    <!-- Mobile Bottom Nav -->
    <nav class="mobile-bottom-nav" id="mobile-bottom-nav" aria-label="View navigation">
        <button class="mnav-btn mnav-active" data-view="table" onclick="showView('table')"><span class="mnav-icon">&#9783;</span><span class="mnav-label">Table</span></button>
        <button class="mnav-btn" data-view="cards" onclick="showView('cards')"><span class="mnav-icon">&#9642;</span><span class="mnav-label">Cards</span></button>
        <button class="mnav-btn" data-view="pipeline" onclick="showView('pipeline')"><span class="mnav-icon">&#9654;</span><span class="mnav-label">Pipeline</span></button>
        <button class="mnav-btn" data-view="calendar" onclick="showView('calendar')"><span class="mnav-icon">&#128197;</span><span class="mnav-label">Calendar</span></button>
        <button class="mnav-btn" data-view="stats" onclick="showView('stats')"><span class="mnav-icon">&#9733;</span><span class="mnav-label">Stats</span></button>
        <button class="mnav-btn" data-view="timeline" onclick="showView('timeline')"><span class="mnav-icon">&#8594;</span><span class="mnav-label">Timeline</span></button>
    </nav>

    <!-- Command Palette -->
    <div class="cmd-overlay" id="cmd-overlay" style="display:none" onclick="closeCmdPalette()">
        <div class="cmd-palette" onclick="event.stopPropagation()">
            <input type="text" class="cmd-input" id="cmd-input" placeholder="Search programs, actions, views..." autocomplete="off">
            <div class="cmd-results" id="cmd-results"></div>
            <div class="cmd-footer"><kbd>Enter</kbd> Select &bull; <kbd>Esc</kbd> Close &bull; <kbd>&uarr;&darr;</kbd> Navigate</div>
        </div>
    </div>

    <script>
var PROGRAMS = {programs_json};
// ===== Static site JS (no backend) =====

const statusClasses = {{
    'Not Started': '',
    'In Progress': 'row-in-progress',
    'Submitted': 'row-submitted',
    'Interview': 'row-interview',
    'Offer': 'row-offer',
    'Rejected': 'row-rejected'
}};

var selectStatusClasses = {{
    'In Progress': 'sel-in-progress',
    'Submitted': 'sel-submitted',
    'Interview': 'sel-interview',
    'Offer': 'sel-offer',
    'Rejected': 'sel-rejected'
}};

function applyRowStatus(row, status) {{
    Object.values(statusClasses).forEach(function(cls) {{
        if (cls) row.classList.remove(cls);
    }});
    if (statusClasses[status]) row.classList.add(statusClasses[status]);
    // Color the dropdown
    var sel = row.querySelector('.status-select');
    if (sel) {{
        Object.values(selectStatusClasses).forEach(function(c) {{ sel.classList.remove(c); }});
        if (selectStatusClasses[status]) sel.classList.add(selectStatusClasses[status]);
    }}
    // Flash animation
    row.classList.remove('row-flash');
    void row.offsetHeight; // force reflow
    row.classList.add('row-flash');
}}

// localStorage helpers
function loadSavedStatuses() {{
    try {{
        var saved = localStorage.getItem('rn_tracker_statuses');
        return saved ? JSON.parse(saved) : {{}};
    }} catch(e) {{ return {{}}; }}
}}

function saveStatus(id, status) {{
    try {{
        var all = loadSavedStatuses();
        all[id] = status;
        localStorage.setItem('rn_tracker_statuses', JSON.stringify(all));
        logActivity(id, 'Status changed to ' + status);
        // Track status history
        var history = JSON.parse(localStorage.getItem('rn_tracker_status_history') || '{{}}');
        if (!history[id]) history[id] = [];
        history[id].push({{ status: status, time: new Date().toISOString() }});
        localStorage.setItem('rn_tracker_status_history', JSON.stringify(history));
    }} catch(e) {{}}
}}

function getStatusHistory(id) {{
    try {{
        var history = JSON.parse(localStorage.getItem('rn_tracker_status_history') || '{{}}');
        return history[id] || [];
    }} catch(e) {{ return []; }}
}}

function loadSavedNotes() {{
    try {{
        var saved = localStorage.getItem('rn_tracker_notes');
        return saved ? JSON.parse(saved) : {{}};
    }} catch(e) {{ return {{}}; }}
}}

function saveNote(id, note) {{
    try {{
        var all = loadSavedNotes();
        all[id] = note;
        localStorage.setItem('rn_tracker_notes', JSON.stringify(all));
    }} catch(e) {{}}
}}

function loadChecklist(id) {{
    try {{
        var all = JSON.parse(localStorage.getItem('rn_tracker_checklists') || '{{}}');
        return all[id] || [];
    }} catch(e) {{ return []; }}
}}

function addChecklistItem(id, idx) {{
    try {{
        var all = JSON.parse(localStorage.getItem('rn_tracker_checklists') || '{{}}');
        if (!all[id]) all[id] = [];
        if (all[id].indexOf(idx) === -1) all[id].push(idx);
        localStorage.setItem('rn_tracker_checklists', JSON.stringify(all));
    }} catch(e) {{}}
}}

function removeChecklistItem(id, idx) {{
    try {{
        var all = JSON.parse(localStorage.getItem('rn_tracker_checklists') || '{{}}');
        if (all[id]) all[id] = all[id].filter(function(i) {{ return i !== idx; }});
        localStorage.setItem('rn_tracker_checklists', JSON.stringify(all));
    }} catch(e) {{}}
}}

// Activity log
function logActivity(progId, action) {{
    try {{
        var log = JSON.parse(localStorage.getItem('rn_tracker_log') || '[]');
        log.unshift({{
            id: progId,
            action: action,
            time: new Date().toISOString()
        }});
        if (log.length > 50) log = log.slice(0, 50);
        localStorage.setItem('rn_tracker_log', JSON.stringify(log));
    }} catch(e) {{}}
}}

function getActivityLog(progId) {{
    try {{
        var log = JSON.parse(localStorage.getItem('rn_tracker_log') || '[]');
        if (progId) return log.filter(function(e) {{ return e.id === progId; }});
        return log;
    }} catch(e) {{ return []; }}
}}

// Favorites
function loadFavorites() {{
    try {{
        return JSON.parse(localStorage.getItem('rn_tracker_favorites') || '[]');
    }} catch(e) {{ return []; }}
}}

function saveFavorites(favs) {{
    try {{
        localStorage.setItem('rn_tracker_favorites', JSON.stringify(favs));
    }} catch(e) {{}}
}}

function toggleFav(id) {{
    var favs = loadFavorites();
    var idx = favs.indexOf(id);
    if (idx !== -1) {{
        favs.splice(idx, 1);
        logActivity(id, 'Removed from favorites');
    }} else {{
        favs.push(id);
        logActivity(id, 'Added to favorites');
    }}
    saveFavorites(favs);
    renderFavButtons();
    updateFavCount();
}}

function renderFavButtons() {{
    var favs = loadFavorites();
    document.querySelectorAll('.fav-btn').forEach(function(btn) {{
        var id = parseInt(btn.dataset.id);
        if (favs.indexOf(id) !== -1) {{
            btn.innerHTML = '\u2605';
            btn.classList.add('fav-active');
        }} else {{
            btn.innerHTML = '\u2606';
            btn.classList.remove('fav-active');
        }}
    }});
}}

function updateFavCount() {{
    var cnt = document.getElementById('fav-count');
    if (cnt) cnt.textContent = loadFavorites().length;
}}

function renderStatusSummary() {{
    var statuses = loadSavedStatuses();
    var counts = {{ 'Not Started': 0, 'In Progress': 0, 'Submitted': 0, 'Interview': 0, 'Offer': 0, 'Rejected': 0 }};
    var total = PROGRAMS.length;
    PROGRAMS.forEach(function(p) {{
        var s = statuses[p.id] || p.application_status || 'Not Started';
        if (counts.hasOwnProperty(s)) counts[s]++;
    }});
    var applied = counts['Submitted'] + counts['Interview'] + counts['Offer'];
    var bar = document.getElementById('status-summary');
    if (!bar) return;
    var html = '<div class="summary-pills">';
    if (counts['In Progress'] > 0) html += '<span class="summary-pill pill-in-progress" onclick="filterByStatus(\'In Progress\')">' + counts['In Progress'] + ' In Progress</span>';
    if (counts['Submitted'] > 0) html += '<span class="summary-pill pill-submitted" onclick="filterByStatus(\'Submitted\')">' + counts['Submitted'] + ' Submitted</span>';
    if (counts['Interview'] > 0) html += '<span class="summary-pill pill-interview" onclick="filterByStatus(\'Interview\')">' + counts['Interview'] + ' Interview</span>';
    if (counts['Offer'] > 0) html += '<span class="summary-pill pill-offer" onclick="filterByStatus(\'Offer\')">' + counts['Offer'] + ' Offer</span>';
    if (counts['Rejected'] > 0) html += '<span class="summary-pill pill-rejected" onclick="filterByStatus(\'Rejected\')">' + counts['Rejected'] + ' Rejected</span>';
    var remaining = counts['Not Started'];
    if (remaining > 0) html += '<span class="summary-pill pill-not-started">' + remaining + ' Not Started</span>';
    html += '</div>';
    bar.innerHTML = html;
    // Hide if all are Not Started
    bar.style.display = (counts['Not Started'] === total) ? 'none' : '';
    // Update nav progress bar
    var progressed = counts['In Progress'] + counts['Submitted'] + counts['Interview'] + counts['Offer'];
    var fill = document.getElementById('nav-progress-fill');
    var text = document.getElementById('nav-progress-text');
    if (fill) fill.style.width = Math.round(progressed / total * 100) + '%';
    if (text) text.textContent = progressed + '/' + total;
}}

function filterByStatus(status) {{
    resetFilters();
    var statusSel = document.querySelector('[data-instant="status"]');
    if (statusSel) statusSel.value = status;
    filterTable();
    updateUrlParams();
    showToast('Showing ' + status);
}}

function markApplied(btn) {{
    var id = parseInt(btn.dataset.id);
    var url = btn.dataset.url;
    window.open(url, '_blank');
    saveStatus(id, 'Submitted');
    logActivity(id, 'Marked as Submitted via Apply button');
    var row = btn.closest('tr');
    if (row) {{
        applyRowStatus(row, 'Submitted');
        row.dataset.status = 'Submitted';
        var sel = row.querySelector('.status-select');
        if (sel) sel.value = 'Submitted';
    }}
    renderStatusSummary();
    showToast('Opened application & marked as Submitted');
}}

function filterByRegion(region) {{
    resetFilters();
    var regionSel = document.querySelector('[data-instant="region"]');
    if (regionSel) regionSel.value = region;
    filterTable();
    updateUrlParams();
    showToast('Showing ' + region);
}}

function filterByBsn(bsn) {{
    resetFilters();
    var bsnSel = document.querySelector('[data-instant="bsn"]');
    if (bsnSel) bsnSel.value = bsn;
    filterTable();
    updateUrlParams();
    showToast('Showing BSN: ' + bsn);
}}

function filterFavorites(btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'favorites';
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Showing favorites');
}}

document.addEventListener('DOMContentLoaded', function() {{
    // Restore saved statuses from localStorage
    var savedStatuses = loadSavedStatuses();
    document.querySelectorAll('.status-select').forEach(function(sel) {{
        var id = sel.dataset.id;
        if (savedStatuses[id]) {{
            sel.value = savedStatuses[id];
        }}
        var row = sel.closest('tr');
        if (row) {{
            applyRowStatus(row, sel.value);
            row.dataset.status = sel.value;
        }}
    }});

    // Status dropdowns — save to localStorage
    document.querySelectorAll('.status-select').forEach(function(sel) {{
        sel.addEventListener('change', function() {{
            var row = this.closest('tr');
            if (row) {{
                var prevStatus = row.dataset.status || 'Not Started';
                var newStatus = this.value;
                var selRef = this;
                applyRowStatus(row, newStatus);
                row.dataset.status = newStatus;
                saveStatus(this.dataset.id, newStatus);
                logActivity(parseInt(this.dataset.id), 'Status: ' + prevStatus + ' → ' + newStatus);
                renderStatusSummary();
                if (newStatus === 'Offer') {{
                    showToast('Congratulations!');
                    launchConfetti();
                }} else {{
                    showUndoToast('Status set to ' + newStatus, function() {{
                        selRef.value = prevStatus;
                        applyRowStatus(row, prevStatus);
                        row.dataset.status = prevStatus;
                        saveStatus(selRef.dataset.id, prevStatus);
                        logActivity(parseInt(selRef.dataset.id), 'Undo: reverted to ' + prevStatus);
                        renderStatusSummary();
                    }});
                }}
            }}
        }});
    }});

    // Select all checkbox
    var selectAll = document.getElementById('select-all');
    if (selectAll) {{
        selectAll.addEventListener('change', function() {{
            var checked = this.checked;
            document.querySelectorAll('.sheet tbody tr:not([style*="display: none"]) .compare-check').forEach(function(cb) {{
                cb.checked = checked;
            }});
            updateCompareBtn();
        }});
    }}

    var lastCheckedIdx = -1;
    var allCheckboxes = Array.from(document.querySelectorAll('.compare-check'));
    allCheckboxes.forEach(function(cb, idx) {{
        cb.addEventListener('change', updateCompareBtn);
        cb.addEventListener('click', function(e) {{
            if (e.shiftKey && lastCheckedIdx >= 0) {{
                var start = Math.min(lastCheckedIdx, idx);
                var end = Math.max(lastCheckedIdx, idx);
                for (var i = start; i <= end; i++) {{
                    allCheckboxes[i].checked = cb.checked;
                }}
                updateCompareBtn();
            }}
            lastCheckedIdx = idx;
        }});
    }});

    // Restore filters from URL params
    var params = new URLSearchParams(window.location.search);
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    if (params.get('q') && searchInput) searchInput.value = params.get('q');
    if (params.get('region')) {{
        var rs = document.querySelector('[data-instant="region"]');
        if (rs) rs.value = params.get('region');
    }}
    if (params.get('city')) {{
        var cs = document.querySelector('[data-instant="city"]');
        if (cs) cs.value = params.get('city');
    }}
    if (params.get('bsn')) {{
        var bs = document.querySelector('[data-instant="bsn"]');
        if (bs) bs.value = params.get('bsn');
    }}
    if (params.get('status')) {{
        var ss = document.querySelector('[data-instant="status"]');
        if (ss) ss.value = params.get('status');
    }}
    if (params.get('cohort')) {{
        var co = document.querySelector('[data-instant="cohort-status"]');
        if (co) co.value = params.get('cohort');
    }}
    if (params.toString()) filterTable();

    // Restore saved sort or default to App Close
    if (!params.toString()) {{
        try {{
            var savedSort = JSON.parse(localStorage.getItem('rn_tracker_sort'));
            if (savedSort && savedSort.col) {{
                var th = document.querySelector('[data-col="' + savedSort.col + '"]');
                if (th) {{
                    // Set opposite direction since sortTable will toggle
                    currentSort.col = savedSort.col;
                    currentSort.asc = !savedSort.asc;
                    sortTable(th);
                }}
            }} else {{
                var closeHeader = document.querySelector('[data-label="App Close"]');
                if (closeHeader) sortTable(closeHeader);
            }}
        }} catch(ex) {{
            var closeHeader = document.querySelector('[data-label="App Close"]');
            if (closeHeader) sortTable(closeHeader);
        }}
    }}

    // Search with suggestions
    if (searchInput) {{
        searchInput.addEventListener('input', debounce(function() {{
            filterTable();
            updateUrlParams();
            showSearchSuggestions(this.value);
        }}, 150));
        searchInput.addEventListener('focus', function() {{
            if (this.value.length >= 1) showSearchSuggestions(this.value);
            else showRecentSearches();
        }});
        searchInput.addEventListener('blur', function() {{
            setTimeout(function() {{
                var sg = document.getElementById('search-suggest');
                if (sg) sg.style.display = 'none';
            }}, 200);
        }});
        searchInput.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter' && this.value.trim()) {{
                saveRecentSearch(this.value.trim());
                var sg = document.getElementById('search-suggest');
                if (sg) sg.style.display = 'none';
            }}
        }});
    }}

    // Filter dropdowns
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function(sel) {{
        sel.addEventListener('change', function() {{ filterTable(); updateUrlParams(); }});
    }});

    // Keyboard: / to search, j/k to navigate rows, Enter to open detail
    var selectedRowIdx = -1;
    document.addEventListener('keydown', function(e) {{
        if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {{
            e.preventDefault();
            toggleCommandPalette();
            return;
        }}
        if (e.key === '/' && !isEditing(e.target)) {{
            var si = document.querySelector('.sheet-filters input[type="search"]');
            if (si) {{ e.preventDefault(); si.focus(); si.select(); }}
        }}
        if (e.key === 'Escape') {{
            closeCmdPalette();
            closeQuickNote();
            document.activeElement.blur();
        }}

        if (!isEditing(e.target)) {{
            // Keyboard shortcuts
            if (e.key === 'n') {{ toggleNotifications(); return; }}
            if (e.key === 'd') {{ toggleTheme(); return; }}
            if (e.key === 'f') {{
                // Toggle favorite on selected row
                var selRow = document.querySelector('.sheet tbody tr.selected-row');
                if (selRow && selRow.dataset.id) {{
                    toggleFav(parseInt(selRow.dataset.id));
                    return;
                }}
            }}
            if (e.key === '?') {{ toggleShortcutHelp(); return; }}
            if (e.key === '1') {{ showView('table'); return; }}
            if (e.key === '2') {{ showView('cards'); return; }}
            if (e.key === '3') {{ showView('pipeline'); return; }}
            if (e.key === '4') {{ showView('calendar'); return; }}
            if (e.key === '5') {{ showView('stats'); return; }}
            if (e.key === '6') {{ showView('timeline'); return; }}

            // Modal prev/next with arrow keys
            var detailModal = document.getElementById('detail-modal');
            if (detailModal && detailModal.classList.contains('modal-visible')) {{
                if (e.key === 'ArrowLeft') {{
                    var prevBtn = detailModal.querySelector('.modal-nav button:first-child');
                    if (prevBtn && !prevBtn.disabled) prevBtn.click();
                    return;
                }}
                if (e.key === 'ArrowRight') {{
                    var nextBtn = detailModal.querySelector('.modal-nav button:last-child');
                    if (nextBtn && !nextBtn.disabled) nextBtn.click();
                    return;
                }}
            }}

            var visibleRows = Array.from(document.querySelectorAll('.sheet tbody tr')).filter(function(r) {{
                return r.style.display !== 'none';
            }});

            if (e.key === 'j' || e.key === 'ArrowDown') {{
                e.preventDefault();
                selectedRowIdx = Math.min(selectedRowIdx + 1, visibleRows.length - 1);
                highlightSelectedRow(visibleRows, selectedRowIdx);
            }}
            if (e.key === 'k' || e.key === 'ArrowUp') {{
                e.preventDefault();
                selectedRowIdx = Math.max(selectedRowIdx - 1, 0);
                highlightSelectedRow(visibleRows, selectedRowIdx);
            }}
            if (e.key === 'Enter' && selectedRowIdx >= 0 && selectedRowIdx < visibleRows.length) {{
                var id = parseInt(visibleRows[selectedRowIdx].dataset.id);
                if (id) showDetail(id);
            }}
        }}
    }});

    highlightDeadlines();
    markNotesIndicators();
    renderFavButtons();
    updateFavCount();
    renderStatusSummary();
    renderRecentViewed();
    renderUrgencyBanner();
    renderNotifications();
    renderSavedFilters();
    initRowPreview();
    renderTableTags();
    applyPins();
    updateTableFooter();

    // Close popups on outside click
    document.addEventListener('click', function(e) {{
        var panel = document.getElementById('notif-panel');
        if (panel && panel.style.display !== 'none' && !e.target.closest('.notif-nav')) {{
            panel.style.display = 'none';
        }}
        var qnote = document.querySelector('.qnote-popover');
        if (qnote && !e.target.closest('.qnote-popover') && !e.target.closest('.qnote-btn')) {{
            qnote.remove();
        }}
        var ap = document.getElementById('accent-palette');
        if (ap && ap.classList.contains('visible') && !e.target.closest('.accent-picker-wrap')) {{
            ap.classList.remove('visible');
        }}
        var fab = document.getElementById('fab-wrap');
        if (fab && fab.classList.contains('open') && !e.target.closest('.fab-wrap')) {{
            fab.classList.remove('open');
        }}
    }});

    // First-time welcome
    if (!localStorage.getItem('rn_tracker_welcomed')) {{
        setTimeout(function() {{ openModal('welcome-modal'); }}, 500);
    }}

    // Deep link: #program-5 opens detail modal for program 5
    var hash = window.location.hash;
    if (hash && hash.startsWith('#program-')) {{
        var deepId = parseInt(hash.replace('#program-', ''));
        if (deepId) setTimeout(function() {{ showDetail(deepId); }}, 100);
    }}

    // Session change detection — show "since last visit" banner
    (function() {{
        var lastVisit = localStorage.getItem('rn_tracker_last_visit');
        var now = new Date().toISOString();
        localStorage.setItem('rn_tracker_last_visit', now);
        if (!lastVisit) return;
        var lastDate = new Date(lastVisit);
        var today = new Date(); today.setHours(0,0,0,0);
        var savedStatuses = loadSavedStatuses();
        var changes = [];
        PROGRAMS.forEach(function(p) {{
            var st = savedStatuses[p.id] || p.application_status || 'Not Started';
            if (st === 'Submitted' || st === 'Interview' || st === 'Offer' || st === 'Rejected') return;
            var openD = parseDate(p.app_open_date);
            var closeD = parseDate(p.app_close_date);
            // Newly opened since last visit
            if (openD && openD > lastDate && openD <= today && closeD && closeD >= today) {{
                changes.push(p.hospital + ' just opened!');
            }}
            // Closing soon (within 3 days) that wasn't closing before
            if (closeD) {{
                var daysLeft = Math.ceil((closeD - today) / 86400000);
                if (daysLeft >= 0 && daysLeft <= 3 && closeD > lastDate) {{
                    changes.push(p.hospital + ' closes in ' + daysLeft + 'd');
                }}
            }}
        }});
        if (changes.length > 0) {{
            var banner = document.createElement('div');
            banner.className = 'session-banner';
            banner.innerHTML = '<strong>Since your last visit:</strong> ' + changes.join(' \\u2022 ') +
                ' <button onclick="this.parentElement.remove()">\\u2715</button>';
            var main = document.getElementById('main-table');
            if (main) main.insertBefore(banner, main.firstChild);
        }}
    }})();

    // Back to top button visibility + sticky header shadow
    var topBtn = document.getElementById('back-to-top');
    var thead = document.querySelector('.sheet thead');
    window.addEventListener('scroll', function() {{
        if (topBtn) {{
            if (window.scrollY > 300) {{
                topBtn.classList.add('visible');
            }} else {{
                topBtn.classList.remove('visible');
            }}
        }}
        if (thead) {{
            if (window.scrollY > 80) {{
                thead.classList.add('stuck');
            }} else {{
                thead.classList.remove('stuck');
            }}
        }}
        // Reading progress bar
        var rpBar = document.getElementById('reading-progress');
        if (rpBar) {{
            var scrollPctRP = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
            rpBar.style.width = Math.min(scrollPctRP, 100) + '%';
        }}
        // Scroll progress ring
        var ringFill = document.getElementById('scroll-ring-fill');
        if (ringFill) {{
            var scrollPct = window.scrollY / (document.documentElement.scrollHeight - window.innerHeight);
            var circumference = 2 * Math.PI * 15.5;
            var offset = circumference * (1 - Math.min(scrollPct, 1));
            ringFill.style.strokeDashoffset = offset;
        }}
    }});

    // Pipeline search/filter
    var pipeSearchInput = document.getElementById('pipeline-search');
    var pipeRegionFilter = document.getElementById('pipeline-region-filter');
    if (pipeSearchInput) {{
        pipeSearchInput.addEventListener('input', debounce(function() {{ renderPipeline(); }}, 200));
    }}
    if (pipeRegionFilter) {{
        pipeRegionFilter.addEventListener('change', function() {{ renderPipeline(); }});
    }}

    // Sortable column headers
    document.querySelectorAll('.sortable').forEach(function(th) {{
        th.addEventListener('click', function() {{
            sortTable(this);
        }});
    }});

    // Row hover preview
    var hoverTimer = null;
    var previewEl = null;
    document.querySelector('.sheet tbody').addEventListener('mouseover', function(e) {{
        var row = e.target.closest('tr');
        if (!row || !row.dataset.id) return;
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(function() {{
            var id = parseInt(row.dataset.id);
            var p = PROGRAMS.find(function(prog) {{ return prog.id === id; }});
            if (!p) return;
            if (previewEl) previewEl.remove();
            previewEl = document.createElement('div');
            previewEl.className = 'row-preview';
            var stars = '\u2605'.repeat(p.reputation) + '\u2606'.repeat(5 - p.reputation);
            var pay = p.pay_range || 'N/A';
            var specs = (p.specialty_units || []).slice(0, 3).join(', ');
            previewEl.innerHTML = '<strong>' + escHtml(p.hospital) + '</strong><br>' +
                '<span class="stars" style="font-size:0.7rem">' + stars + '</span> ' + escHtml(pay) + '<br>' +
                '<span style="color:#6b7280;font-size:0.7rem">' + escHtml(specs) + '</span>';
            var rect = row.getBoundingClientRect();
            previewEl.style.top = (rect.bottom + window.scrollY + 4) + 'px';
            previewEl.style.left = (rect.left + 60) + 'px';
            document.body.appendChild(previewEl);
        }}, 600);
    }});
    document.querySelector('.sheet tbody').addEventListener('mouseout', function(e) {{
        clearTimeout(hoverTimer);
        if (previewEl) {{ previewEl.remove(); previewEl = null; }}
    }});

    // Double-click row to open detail
    document.querySelector('.sheet tbody').addEventListener('dblclick', function(e) {{
        var row = e.target.closest('tr');
        if (row && row.dataset.id) {{
            showDetail(parseInt(row.dataset.id));
        }}
    }});

    // Right-click context menu for table rows
    var ctxMenu = document.createElement('div');
    ctxMenu.className = 'ctx-menu';
    ctxMenu.style.display = 'none';
    document.body.appendChild(ctxMenu);

    document.querySelector('.sheet tbody').addEventListener('contextmenu', function(e) {{
        var row = e.target.closest('tr');
        if (!row || !row.dataset.id) return;
        e.preventDefault();
        var id = parseInt(row.dataset.id);
        var p = PROGRAMS.find(function(prog) {{ return prog.id === id; }});
        if (!p) return;
        var favs = loadFavorites();
        var isFav = favs.indexOf(id) !== -1;
        var savedStatuses = loadSavedStatuses();
        var currentStatus = savedStatuses[id] || p.application_status || 'Not Started';
        var html = '<div class="ctx-header">' + escHtml(p.hospital) + '</div>';
        html += '<button onclick="showDetail(' + id + '); hideCtxMenu();">View Details</button>';
        html += '<button onclick="toggleFav(' + id + '); hideCtxMenu();">' + (isFav ? 'Remove from Favorites' : 'Add to Favorites') + '</button>';
        var statuses = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer', 'Rejected'];
        html += '<div class="ctx-divider"></div>';
        html += '<div class="ctx-label">Set Status</div>';
        statuses.forEach(function(s) {{
            var cls = s === currentStatus ? ' ctx-active' : '';
            html += '<button class="ctx-status' + cls + '" onclick="quickSetStatus(' + id + ', \\\'' + s + '\\\')">' + s + '</button>';
        }});
        if (p.application_url) {{
            html += '<div class="ctx-divider"></div>';
            html += '<button onclick="window.open(\\\'' + escHtml(p.application_url) + '\\\', \\\'_blank\\\'); hideCtxMenu();">Apply Now</button>';
        }}
        html += '<div class="ctx-divider"></div>';
        html += '<button onclick="navigator.clipboard.writeText(\\\'' + escHtml(p.hospital).replace(/'/g, "\\\\'") + '\\\'); hideCtxMenu(); showToast(\\\'Copied!\\\');">Copy Hospital Name</button>';
        var pins = loadPins();
        var isPinned = pins.indexOf(id) !== -1;
        html += '<button onclick="togglePin(' + id + '); hideCtxMenu();">' + (isPinned ? 'Unpin from Top' : 'Pin to Top') + '</button>';
        ctxMenu.innerHTML = html;
        var x = e.clientX, y = e.clientY;
        ctxMenu.style.display = 'block';
        // Adjust if overflowing viewport
        var rect = ctxMenu.getBoundingClientRect();
        if (x + rect.width > window.innerWidth) x = window.innerWidth - rect.width - 8;
        if (y + rect.height > window.innerHeight) y = window.innerHeight - rect.height - 8;
        ctxMenu.style.left = x + 'px';
        ctxMenu.style.top = y + 'px';
    }});

    document.addEventListener('click', function(e) {{
        if (!e.target.closest('.ctx-menu')) hideCtxMenu();
    }});

    // Note expand/collapse + hospital detail links
    document.addEventListener('click', function(e) {{
        if (e.target.classList.contains('note-expand')) {{
            e.preventDefault();
            var td = e.target.closest('td');
            td.querySelector('.note-trunc').style.display = 'none';
            td.querySelector('.note-full').style.display = '';
        }}
        if (e.target.classList.contains('note-collapse')) {{
            e.preventDefault();
            var td = e.target.closest('td');
            td.querySelector('.note-trunc').style.display = '';
            td.querySelector('.note-full').style.display = 'none';
        }}
        // Hospital name → detail modal
        if (e.target.classList.contains('hospital-link')) {{
            e.preventDefault();
            var id = parseInt(e.target.dataset.id);
            if (id) showDetail(id);
        }}
    }});

    // Swipe gesture for modal navigation on mobile
    var touchStartX = 0;
    var touchEndX = 0;
    document.addEventListener('touchstart', function(e) {{
        touchStartX = e.changedTouches[0].screenX;
    }}, {{ passive: true }});
    document.addEventListener('touchend', function(e) {{
        touchEndX = e.changedTouches[0].screenX;
        var detailModal = document.getElementById('detail-modal');
        if (detailModal && detailModal.classList.contains('modal-visible')) {{
            var diff = touchStartX - touchEndX;
            if (Math.abs(diff) > 80) {{
                if (diff > 0) {{
                    // Swipe left → next
                    var nextBtn = detailModal.querySelector('.modal-nav button:last-child');
                    if (nextBtn && !nextBtn.disabled) nextBtn.click();
                }} else {{
                    // Swipe right → prev
                    var prevBtn = detailModal.querySelector('.modal-nav button:first-child');
                    if (prevBtn && !prevBtn.disabled) prevBtn.click();
                }}
            }}
        }}
    }}, {{ passive: true }});

    // Close modals on overlay click or Escape
    document.querySelectorAll('.modal-overlay').forEach(function(overlay) {{
        overlay.addEventListener('click', function(e) {{
            if (e.target === overlay) closeModalEl(overlay);
        }});
    }});
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') {{
            document.querySelectorAll('.modal-overlay.modal-visible').forEach(function(m) {{
                closeModalEl(m);
            }});
        }}
    }});

    // Multi-tab sync: refresh UI when localStorage changes in another tab
    window.addEventListener('storage', function(e) {{
        if (!e.key || !e.key.startsWith('rn_tracker_')) return;
        if (e.key === 'rn_tracker_statuses') {{
            var saved = loadSavedStatuses();
            document.querySelectorAll('.status-select').forEach(function(sel) {{
                var id = sel.dataset.id;
                if (saved[id] && sel.value !== saved[id]) {{
                    sel.value = saved[id];
                    var row = sel.closest('tr');
                    if (row) {{ applyRowStatus(row, saved[id]); row.dataset.status = saved[id]; }}
                }}
            }});
            renderStatusSummary();
            updateTableFooter();
        }} else if (e.key === 'rn_tracker_notes') {{
            markNotesIndicators();
        }} else if (e.key === 'rn_tracker_favorites') {{
            renderFavButtons();
            updateFavCount();
        }} else if (e.key === 'rn_tracker_theme') {{
            var theme = localStorage.getItem('rn_tracker_theme') || 'light';
            document.documentElement.setAttribute('data-theme', theme);
        }} else if (e.key === 'rn_tracker_pins') {{
            applyPins();
        }}
    }});
}});

function debounce(fn, ms) {{
    var timer;
    return function() {{ clearTimeout(timer); timer = setTimeout(fn, ms); }};
}}

function isEditing(el) {{
    var tag = el.tagName.toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
}}

function filterTable() {{
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    var regionSelect = document.querySelector('.sheet-filters select[data-instant="region"]');
    var citySelect = document.querySelector('.sheet-filters select[data-instant="city"]');
    var bsnSelect = document.querySelector('.sheet-filters select[data-instant="bsn"]');
    var statusSelect = document.querySelector('.sheet-filters select[data-instant="status"]');
    var cohortStatusSelect = document.querySelector('.sheet-filters select[data-instant="cohort-status"]');

    var query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var region = regionSelect ? regionSelect.value : '';
    var city = citySelect ? citySelect.value : '';
    var bsn = bsnSelect ? bsnSelect.value : '';
    var status = statusSelect ? statusSelect.value : '';
    var cohortStatus = cohortStatusSelect ? cohortStatusSelect.value : '';

    var hasFilters = query || region || city || bsn || status || cohortStatus;
    var clearBtn = document.getElementById('clear-all-btn');
    if (clearBtn) clearBtn.style.display = hasFilters ? '' : 'none';

    var rows = document.querySelectorAll('.sheet tbody tr');
    var visibleCount = 0;

    rows.forEach(function(row) {{
        var show = true;
        if (query) {{
            var text = row.textContent.toLowerCase();
            if (text.indexOf(query) === -1) show = false;
        }}
        if (show && region) {{
            var regionCell = row.querySelector('.col-region');
            if (regionCell && regionCell.textContent.trim() !== region) show = false;
        }}
        if (show && city) {{
            if (row.dataset.city !== city) show = false;
        }}
        if (show && bsn) {{
            if (row.dataset.bsn !== bsn) show = false;
        }}
        if (show && status) {{
            var statusSel = row.querySelector('.status-select');
            if (statusSel && statusSel.value !== status) show = false;
        }}
        if (show && cohortStatus) {{
            var dateCells = row.querySelectorAll('.col-date');
            var cohortCell = dateCells.length >= 3 ? dateCells[2] : null;
            var cohortRaw = cohortCell ? (cohortCell.dataset.raw || cohortCell.textContent.trim()).toLowerCase() : '';
            var isDate = /^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(cohortRaw);
            if (cohortStatus === 'released' && !isDate) show = false;
            if (cohortStatus === 'not-released' && (isDate || cohortRaw.indexOf('rolling') !== -1 || cohortRaw.indexOf('paused') !== -1)) show = false;
            if (cohortStatus === 'rolling' && cohortRaw.indexOf('rolling') === -1) show = false;
            if (cohortStatus === 'paused' && cohortRaw.indexOf('paused') === -1) show = false;
        }}
        row.style.display = show ? '' : 'none';
        if (show) visibleCount++;
    }});

    updateCount(visibleCount, rows.length);
    highlightSearch(query);
    restripe();
    applyGrouping();
    updateTableFooter();
}}

function applyGrouping() {{
    var tbody = document.querySelector('.sheet tbody');
    if (!tbody) return;
    // Remove existing group headers
    tbody.querySelectorAll('.group-header-row').forEach(function(r) {{ r.remove(); }});

    var groupBy = (document.getElementById('group-by') || {{}}).value || '';
    if (!groupBy) return;

    var rows = Array.from(tbody.querySelectorAll('tr:not(.group-header-row)'));
    var visibleRows = rows.filter(function(r) {{ return r.style.display !== 'none'; }});

    // Get group key for each row
    function getGroupKey(row) {{
        if (groupBy === 'region') {{
            var rc = row.querySelector('.col-region');
            return rc ? rc.textContent.trim() : 'Unknown';
        }} else if (groupBy === 'status') {{
            var ss = row.querySelector('.status-select');
            return ss ? ss.value : 'Not Started';
        }} else if (groupBy === 'bsn') {{
            return row.dataset.bsn === 'Yes' ? 'BSN Required' : 'ADN Accepted';
        }}
        return '';
    }}

    // Sort visible rows by group key
    var groups = {{}};
    visibleRows.forEach(function(row) {{
        var key = getGroupKey(row);
        if (!groups[key]) groups[key] = [];
        groups[key].push(row);
    }});

    // Get sorted group names
    var groupNames = Object.keys(groups).sort(function(a, b) {{
        if (groupBy === 'status') {{
            var order = ['In Progress', 'Submitted', 'Interview', 'Offer', 'Not Started', 'Rejected'];
            return order.indexOf(a) - order.indexOf(b);
        }}
        return a.localeCompare(b);
    }});

    // Re-order rows and insert headers
    var colCount = tbody.parentElement.querySelector('thead tr').children.length;
    groupNames.forEach(function(name) {{
        var headerRow = document.createElement('tr');
        headerRow.className = 'group-header-row';
        headerRow.dataset.group = name;
        headerRow.dataset.collapsed = 'false';
        headerRow.innerHTML = '<td colspan="' + colCount + '" class="group-header-cell">' +
            '<span class="group-toggle">&#9660;</span> ' +
            '<strong>' + name + '</strong> <span class="group-count">(' + groups[name].length + ')</span></td>';
        headerRow.onclick = function() {{
            var collapsed = this.dataset.collapsed === 'true';
            this.dataset.collapsed = collapsed ? 'false' : 'true';
            this.querySelector('.group-toggle').innerHTML = collapsed ? '&#9660;' : '&#9654;';
            var grpName = this.dataset.group;
            var next = this.nextElementSibling;
            while (next && !next.classList.contains('group-header-row')) {{
                next.style.display = collapsed ? '' : 'none';
                next = next.nextElementSibling;
            }}
        }};
        tbody.appendChild(headerRow);
        groups[name].forEach(function(row) {{ tbody.appendChild(row); }});
    }});
}}

function showSearchSuggestions(query) {{
    var sg = document.getElementById('search-suggest');
    if (!sg) return;
    if (!query || query.length < 1) {{ sg.style.display = 'none'; return; }}
    var q = query.toLowerCase();
    var matches = PROGRAMS.filter(function(p) {{
        return p.hospital.toLowerCase().indexOf(q) !== -1 ||
               (p.program_name || '').toLowerCase().indexOf(q) !== -1 ||
               (p.region || '').toLowerCase().indexOf(q) !== -1;
    }}).slice(0, 6);
    if (matches.length === 0) {{ sg.style.display = 'none'; return; }}
    var html = '';
    matches.forEach(function(p) {{
        html += '<div class="suggest-item" onmousedown="selectSuggestion(\'' + p.hospital.replace(/'/g, "\\\\'") + '\')">';
        html += '<strong>' + p.hospital + '</strong> <span class="suggest-region">' + p.region + '</span>';
        html += '</div>';
    }});
    sg.innerHTML = html;
    sg.style.display = 'block';
}}

function showRecentSearches() {{
    var sg = document.getElementById('search-suggest');
    if (!sg) return;
    var recent = JSON.parse(localStorage.getItem('rn_tracker_recent_searches') || '[]');
    if (recent.length === 0) {{ sg.style.display = 'none'; return; }}
    var html = '<div class="suggest-header">Recent</div>';
    recent.slice(0, 5).forEach(function(s) {{
        html += '<div class="suggest-item suggest-recent" onmousedown="selectSuggestion(\'' + s.replace(/'/g, "\\\\'") + '\')">';
        html += s;
        html += '</div>';
    }});
    sg.innerHTML = html;
    sg.style.display = 'block';
}}

function selectSuggestion(val) {{
    var si = document.getElementById('main-search');
    if (si) {{ si.value = val; filterTable(); updateUrlParams(); saveRecentSearch(val); }}
    var sg = document.getElementById('search-suggest');
    if (sg) sg.style.display = 'none';
}}

function saveRecentSearch(val) {{
    var recent = JSON.parse(localStorage.getItem('rn_tracker_recent_searches') || '[]');
    recent = recent.filter(function(s) {{ return s !== val; }});
    recent.unshift(val);
    if (recent.length > 10) recent = recent.slice(0, 10);
    localStorage.setItem('rn_tracker_recent_searches', JSON.stringify(recent));
}}

function highlightSearch(query) {{
    // Clear previous highlights
    document.querySelectorAll('mark.search-highlight').forEach(function(m) {{
        var parent = m.parentNode;
        parent.replaceChild(document.createTextNode(m.textContent), m);
        parent.normalize();
    }});
    if (!query || query.length < 2) return;
    // Highlight in visible cells (skip selects, inputs, links with data-id)
    var rows = document.querySelectorAll('.sheet tbody tr');
    rows.forEach(function(row) {{
        if (row.style.display === 'none') return;
        row.querySelectorAll('td').forEach(function(td) {{
            if (td.querySelector('select') || td.querySelector('input') || td.classList.contains('col-check') || td.classList.contains('col-apply')) return;
            highlightTextInNode(td, query);
        }});
    }});
}}

function highlightTextInNode(node, query) {{
    if (node.nodeType === 3) {{
        var idx = node.textContent.toLowerCase().indexOf(query);
        if (idx >= 0) {{
            var mark = document.createElement('mark');
            mark.className = 'search-highlight';
            var after = node.splitText(idx);
            var matched = after.splitText(query.length);
            mark.appendChild(after.cloneNode(true));
            after.parentNode.replaceChild(mark, after);
        }}
    }} else if (node.nodeType === 1 && node.tagName !== 'MARK' && node.tagName !== 'SELECT' && node.tagName !== 'INPUT') {{
        Array.from(node.childNodes).forEach(function(child) {{
            highlightTextInNode(child, query);
        }});
    }}
}}

function updateCount(visible, total) {{
    var countEl = document.querySelector('.sheet-count');
    if (!countEl) return;
    countEl.textContent = visible + ' of ' + total + ' rows';
    if (visible < total) {{
        countEl.classList.add('count-changed');
    }} else {{
        countEl.classList.remove('count-changed');
    }}
    var noResults = document.getElementById('no-results');
    if (noResults) {{
        noResults.classList.toggle('visible', visible === 0);
    }}
}}

function resetFilters() {{
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    if (searchInput) searchInput.value = '';
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function(sel) {{
        sel.value = '';
    }});
    window._specialFilter = null;
    clearChipActive();
}}

function clearAllFilters() {{
    resetFilters();
    filterTable();
    updateUrlParams();
    showToast('Filters cleared');
}}

function clearChipActive() {{
    document.querySelectorAll('.chip').forEach(function(c) {{ c.classList.remove('chip-active'); }});
}}

function filterOpen(btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'open';
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Showing open programs');
}}

function filterUpcoming(btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'upcoming';
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Showing upcoming programs');
}}

function filterCohort(range, btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'cohort-' + range;
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Showing ' + range.replace('-', '\u2013').toUpperCase() + ' 2026 cohorts');
}}

// Filter presets
function saveFilterPreset() {{
    var search = (document.querySelector('.sheet-filters input[type="search"]') || {{}}).value || '';
    var region = (document.querySelector('[data-instant="region"]') || {{}}).value || '';
    var city = (document.querySelector('[data-instant="city"]') || {{}}).value || '';
    var bsn = (document.querySelector('[data-instant="bsn"]') || {{}}).value || '';
    var status = (document.querySelector('[data-instant="status"]') || {{}}).value || '';
    var name = prompt('Name this filter preset:');
    if (!name || !name.trim()) return;
    var presets = loadFilterPresets();
    presets.push({{ name: name.trim(), search: search, region: region, city: city, bsn: bsn, status: status }});
    localStorage.setItem('rn_tracker_filter_presets', JSON.stringify(presets));
    renderSavedFilters();
    showToast('Filter saved: ' + name.trim());
}}

function loadFilterPresets() {{
    try {{
        return JSON.parse(localStorage.getItem('rn_tracker_filter_presets') || '[]');
    }} catch(e) {{ return []; }}
}}

function applyFilterPreset(idx) {{
    var presets = loadFilterPresets();
    if (idx < 0 || idx >= presets.length) return;
    var p = presets[idx];
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    if (searchInput) searchInput.value = p.search || '';
    var regionSel = document.querySelector('[data-instant="region"]');
    if (regionSel) regionSel.value = p.region || '';
    var citySel = document.querySelector('[data-instant="city"]');
    if (citySel) citySel.value = p.city || '';
    var bsnSel = document.querySelector('[data-instant="bsn"]');
    if (bsnSel) bsnSel.value = p.bsn || '';
    var statusSel = document.querySelector('[data-instant="status"]');
    if (statusSel) statusSel.value = p.status || '';
    window._specialFilter = null;
    filterTable();
    updateUrlParams();
    showToast('Loaded: ' + p.name);
}}

function deleteFilterPreset(idx) {{
    var presets = loadFilterPresets();
    presets.splice(idx, 1);
    localStorage.setItem('rn_tracker_filter_presets', JSON.stringify(presets));
    renderSavedFilters();
    showToast('Filter deleted');
}}

function renderSavedFilters() {{
    var container = document.getElementById('saved-filters-menu');
    if (!container) return;
    var presets = loadFilterPresets();
    if (presets.length === 0) {{
        container.innerHTML = '';
        return;
    }}
    var html = '';
    presets.forEach(function(p, i) {{
        html += '<div class="saved-filter-item">';
        html += '<button type="button" onclick="applyFilterPreset(' + i + '); toggleMoreMenu();">' + escHtml(p.name) + '</button>';
        html += '<button type="button" class="saved-filter-delete" onclick="deleteFilterPreset(' + i + ')" title="Delete">&times;</button>';
        html += '</div>';
    }});
    container.innerHTML = html;
}}

function toggleFocusMode(btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'focus';
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Focus Mode: hiding rejected & closed');
}}

function filterApplyNow(btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    window._specialFilter = 'apply-now';
    filterTableSpecial();
    btn.classList.add('chip-active');
    showToast('Showing programs you can apply to right now');
}}

function filterBsn(val, btn) {{
    if (btn.classList.contains('chip-active')) {{
        clearAllFilters();
        return;
    }}
    resetFilters();
    var bsnSelect = document.querySelector('[data-instant="bsn"]');
    if (bsnSelect) bsnSelect.value = val;
    filterTable();
    updateUrlParams();
    btn.classList.add('chip-active');
    showToast('Showing ' + val + ' BSN programs');
}}

function filterTableSpecial() {{
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var rows = document.querySelectorAll('.sheet tbody tr');
    var visibleCount = 0;

    rows.forEach(function(row) {{
        var dateCells = row.querySelectorAll('.col-date');
        var show = false;

        if (window._specialFilter === 'apply-now') {{
            if (dateCells.length >= 2) {{
                var openRawA = dateCells[0].dataset.raw || '';
                var closeRawA = dateCells[1].dataset.raw || '';
                var openDateA = parseDate(openRawA);
                var closeDateA = parseDate(closeRawA);
                var hasApplyLink = row.querySelector('.apply-link') !== null;
                if (openDateA && openDateA <= today && closeDateA && closeDateA >= today && hasApplyLink) {{
                    show = true;
                }}
            }}
        }} else if (window._specialFilter === 'favorites') {{
            var favs = loadFavorites();
            var rowId = parseInt(row.dataset.id);
            if (favs.indexOf(rowId) !== -1) show = true;
        }} else if (window._specialFilter === 'open') {{
            if (dateCells.length >= 2) {{
                var openRaw = dateCells[0].dataset.raw || '';
                var closeRaw = dateCells[1].dataset.raw || '';
                var openDate = parseDate(openRaw);
                var closeDate = parseDate(closeRaw);
                if (openDate && openDate <= today && closeDate && closeDate >= today) {{
                    show = true;
                }}
            }}
        }} else if (window._specialFilter === 'upcoming') {{
            if (dateCells.length >= 2) {{
                var closeRaw2 = dateCells[1].dataset.raw || '';
                var closeDate2 = parseDate(closeRaw2);
                if (closeDate2 && closeDate2 >= today) {{
                    show = true;
                }}
            }}
        }} else if (window._specialFilter === 'focus') {{
            // Focus mode: hide rejected and closed deadlines
            var statusSel = row.querySelector('.status-select');
            var rowStatus = statusSel ? statusSel.value : 'Not Started';
            if (rowStatus === 'Rejected') {{ show = false; }}
            else {{
                show = true;
                // Also hide if deadline has passed and not already applied
                if (dateCells.length >= 2 && rowStatus === 'Not Started') {{
                    var closeRawF = dateCells[1].dataset.raw || '';
                    var closeDateF = parseDate(closeRawF);
                    if (closeDateF && closeDateF < today) {{ show = false; }}
                }}
            }}
        }} else if (window._specialFilter === 'cohort-jul-sep' || window._specialFilter === 'cohort-oct-dec') {{
            if (dateCells.length >= 3) {{
                var cohortRaw = dateCells[2].dataset.raw || '';
                var cohortDate = parseDate(cohortRaw);
                if (cohortDate) {{
                    var m = cohortDate.getMonth() + 1;
                    var y = cohortDate.getFullYear();
                    if (window._specialFilter === 'cohort-jul-sep' && y === 2026 && m >= 7 && m <= 9) show = true;
                    if (window._specialFilter === 'cohort-oct-dec' && y === 2026 && m >= 10 && m <= 12) show = true;
                }}
            }}
        }}

        row.style.display = show ? '' : 'none';
        if (show) visibleCount++;
    }});

    updateCount(visibleCount, rows.length);
    var clearBtn = document.getElementById('clear-all-btn');
    if (clearBtn) clearBtn.style.display = '';
    restripe();
}}

function highlightDeadlines() {{
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    document.querySelectorAll('.sheet tbody tr').forEach(function(row) {{
        var dateCells = row.querySelectorAll('.col-date');
        if (dateCells.length >= 2) {{
            var closeCell = dateCells[1];
            var closeRaw = closeCell.dataset.raw || closeCell.textContent.trim();
            var displayText = closeCell.textContent.trim();
            if (closeRaw) {{
                var closeDate = parseDate(closeRaw);
                if (closeDate) {{
                    var daysLeft = Math.ceil((closeDate - today) / (1000 * 60 * 60 * 24));
                    if (daysLeft < 0) {{
                        closeCell.innerHTML = displayText + ' <span class="deadline-past">closed</span>';
                    }} else if (daysLeft <= 7) {{
                        closeCell.innerHTML = displayText + ' <span class="deadline-urgent">' + daysLeft + 'd</span>';
                        row.classList.add('urgent-row');
                    }} else if (daysLeft <= 14) {{
                        closeCell.innerHTML = displayText + ' <span class="deadline-warning">' + daysLeft + 'd</span>';
                        row.classList.add('warning-row');
                    }} else if (daysLeft <= 30) {{
                        closeCell.innerHTML = displayText + ' <span class="deadline-soon">' + daysLeft + 'd</span>';
                    }}
                }}
            }}

            var openCell = dateCells[0];
            var openRaw = openCell.dataset.raw || openCell.textContent.trim();
            var openDisplay = openCell.textContent.trim();
            if (openRaw && closeRaw) {{
                var openDate = parseDate(openRaw);
                var closeDate2 = parseDate(closeRaw);
                if (openDate && closeDate2 && openDate <= today && closeDate2 >= today) {{
                    openCell.innerHTML = openDisplay + ' <span class="badge-open">OPEN</span>';
                }} else if (openDate) {{
                    var daysToOpen = Math.ceil((openDate - today) / (1000 * 60 * 60 * 24));
                    if (daysToOpen > 0 && daysToOpen <= 7) {{
                        openCell.innerHTML = openDisplay + ' <span class="countdown-badge" data-target="' + openRaw + '"></span>';
                    }}
                }}
            }}
        }}
    }});
    // Start live countdown timers
    updateCountdowns();
    setInterval(updateCountdowns, 60000);
}}

function updateCountdowns() {{
    document.querySelectorAll('.countdown-badge').forEach(function(badge) {{
        var target = badge.dataset.target;
        if (!target) return;
        var d = parseDate(target);
        if (!d) return;
        var now = new Date();
        var diff = d.getTime() - now.getTime();
        if (diff <= 0) {{
            badge.textContent = 'NOW';
            badge.className = 'badge-open';
            return;
        }}
        var days = Math.floor(diff / (1000 * 60 * 60 * 24));
        var hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        var mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        if (days > 0) {{
            badge.textContent = days + 'd ' + hours + 'h';
        }} else {{
            badge.textContent = hours + 'h ' + mins + 'm';
        }}
    }});
}}

function showQuickNote(id, btn) {{
    // Remove any existing quick note popover
    var existing = document.querySelector('.qnote-popover');
    if (existing) existing.remove();

    var notes = loadSavedNotes();
    var currentNote = notes[id] || '';
    var popover = document.createElement('div');
    popover.className = 'qnote-popover';
    popover.innerHTML = '<textarea class="qnote-textarea" placeholder="Add a note...">' + currentNote.replace(/</g, '&lt;') + '</textarea>' +
        '<div class="qnote-actions"><button onclick="saveQuickNote(' + id + ')">Save</button><button onclick="closeQuickNote()">Cancel</button></div>';

    // Position near the button
    var rect = btn.getBoundingClientRect();
    popover.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    popover.style.left = Math.max(8, rect.left + window.scrollX - 100) + 'px';
    document.body.appendChild(popover);
    popover.querySelector('textarea').focus();
}}

function saveQuickNote(id) {{
    var popover = document.querySelector('.qnote-popover');
    if (!popover) return;
    var note = popover.querySelector('textarea').value;
    saveNote(id, note);
    logActivity(id, note ? 'Updated notes' : 'Cleared notes');
    closeQuickNote();
    markNotesIndicators();
    showToast('Note saved');
}}

function insertNoteTemplate(text) {{
    var ta = document.getElementById('modal-notes');
    if (!ta) return;
    var current = ta.value.trim();
    ta.value = current ? current + '\\n' + text : text;
    ta.dispatchEvent(new Event('input'));
    ta.focus();
}}

function closeQuickNote() {{
    var popover = document.querySelector('.qnote-popover');
    if (popover) popover.remove();
}}

function inlineEditNote(td) {{
    if (td.querySelector('.inline-note-edit')) return;
    var id = parseInt(td.dataset.id);
    var notes = loadSavedNotes();
    var current = notes[id] || '';
    var originalHTML = td.innerHTML;

    var ta = document.createElement('textarea');
    ta.className = 'inline-note-edit';
    ta.value = current;
    ta.placeholder = 'Add a note...';
    td.innerHTML = '';
    td.appendChild(ta);
    ta.focus();
    ta.style.height = Math.max(48, ta.scrollHeight) + 'px';

    function save() {{
        var val = ta.value.trim();
        saveNote(id, val);
        logActivity(id, val ? 'Updated notes' : 'Cleared notes');
        td.innerHTML = val ? val.replace(/</g, '&lt;').replace(/\\n/g, '<br>') : '';
        markNotesIndicators();
        showToast('Note saved');
    }}

    ta.addEventListener('blur', save);
    ta.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') {{
            td.innerHTML = originalHTML;
            return;
        }}
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {{
            e.preventDefault();
            save();
        }}
    }});
}}

function jumpToOpen() {{
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var rows = document.querySelectorAll('.sheet tbody tr');
    for (var i = 0; i < rows.length; i++) {{
        var row = rows[i];
        if (row.style.display === 'none') continue;
        var dateCells = row.querySelectorAll('.col-date');
        if (dateCells.length >= 2) {{
            var openRaw = dateCells[0].dataset.raw || '';
            var closeRaw = dateCells[1].dataset.raw || '';
            var openDate = parseDate(openRaw);
            var closeDate = parseDate(closeRaw);
            if (openDate && closeDate && openDate <= today && closeDate >= today) {{
                row.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                row.classList.add('selected-row');
                setTimeout(function() {{ row.classList.remove('selected-row'); }}, 2000);
                showToast('Jumped to: ' + (row.querySelector('.hospital-link') || {{}}).textContent);
                return;
            }}
        }}
    }}
    showToast('No open programs visible');
}}

function batchApplyOpen() {{
    var today = new Date(); today.setHours(0,0,0,0);
    var savedStatuses = loadSavedStatuses();
    var openProgs = PROGRAMS.filter(function(p) {{
        var st = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (st === 'Submitted' || st === 'Interview' || st === 'Offer' || st === 'Rejected') return false;
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        return openD && closeD && openD <= today && closeD >= today && p.application_url;
    }});
    if (openProgs.length === 0) {{
        showToast('No open programs with application URLs');
        return;
    }}
    if (!confirm('Open ' + openProgs.length + ' application URLs in new tabs?')) return;
    openProgs.forEach(function(p, i) {{
        setTimeout(function() {{ window.open(p.application_url, '_blank'); }}, i * 300);
    }});
    showToast(openProgs.length + ' application tabs opened');
}}

function markNotesIndicators() {{
    var notes = loadSavedNotes();
    document.querySelectorAll('.sheet tbody tr').forEach(function(row) {{
        var id = row.dataset.id;
        if (id && notes[id] && notes[id].trim()) {{
            var hospCell = row.querySelector('.hospital-link');
            if (hospCell && !hospCell.querySelector('.has-notes-dot')) {{
                var dot = document.createElement('span');
                dot.className = 'has-notes-dot';
                dot.title = 'Has notes';
                hospCell.appendChild(dot);
            }}
        }}
    }});
}}

// Row hover preview
var hoverTimer = null;
var hoverCard = null;

function showRowPreview(row, e) {{
    hideRowPreview();
    var id = parseInt(row.dataset.id);
    var prog = window.PROGRAMS.find(function(p) {{ return p.id === id; }});
    if (!prog) return;

    var st = (loadSavedStatuses()[id] || prog.application_status || 'Not Started');
    var stars = '';
    for (var i = 0; i < 5; i++) stars += i < (prog.reputation || 0) ? '\\u2605' : '\\u2606';
    var notes = loadSavedNotes()[id] || '';

    var card = document.createElement('div');
    card.className = 'row-preview-card';
    card.innerHTML = '<div class="rpc-header"><strong>' + prog.hospital + '</strong><span class="rpc-status rpc-status-' + st.toLowerCase().replace(/\\s+/g, '-') + '">' + st + '</span></div>' +
        '<div class="rpc-body">' +
        '<div class="rpc-row"><span class="rpc-label">Rep</span><span class="rpc-stars">' + stars + '</span></div>' +
        (prog.pay_range ? '<div class="rpc-row"><span class="rpc-label">Pay</span><span>' + prog.pay_range + '</span></div>' : '') +
        (prog.app_open_date ? '<div class="rpc-row"><span class="rpc-label">Opens</span><span>' + prog.app_open_date + '</span></div>' : '') +
        (prog.app_close_date ? '<div class="rpc-row"><span class="rpc-label">Closes</span><span>' + prog.app_close_date + '</span></div>' : '') +
        (prog.cohort_start ? '<div class="rpc-row"><span class="rpc-label">Cohort</span><span>' + prog.cohort_start + '</span></div>' : '') +
        (notes ? '<div class="rpc-notes">' + notes.substring(0, 100) + (notes.length > 100 ? '...' : '') + '</div>' : '') +
        '</div>';

    var rect = row.getBoundingClientRect();
    card.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    card.style.left = Math.max(8, rect.left + window.scrollX + 56) + 'px';
    document.body.appendChild(card);
    hoverCard = card;
    requestAnimationFrame(function() {{ card.classList.add('visible'); }});
}}

function hideRowPreview() {{
    if (hoverTimer) {{ clearTimeout(hoverTimer); hoverTimer = null; }}
    if (hoverCard) {{ hoverCard.remove(); hoverCard = null; }}
}}

function initRowPreview() {{
    var tbody = document.querySelector('.sheet tbody');
    if (!tbody) return;
    tbody.addEventListener('mouseover', function(e) {{
        var row = e.target.closest('tr');
        if (!row || row === hoverCard) return;
        hideRowPreview();
        hoverTimer = setTimeout(function() {{ showRowPreview(row, e); }}, 600);
    }});
    tbody.addEventListener('mouseout', function(e) {{
        var row = e.target.closest('tr');
        if (row) hideRowPreview();
    }});
}}

function parseDate(str) {{
    if (!str) return null;
    var parts = str.match(/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
    if (parts) return new Date(parseInt(parts[1]), parseInt(parts[2]) - 1, parseInt(parts[3]));
    parts = str.match(/^(\\d{{1,2}})\\/(\\d{{1,2}})\\/(\\d{{4}})/);
    if (parts) return new Date(parseInt(parts[3]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    return null;
}}

var currentSort = {{ col: null, asc: true }};

function sortTable(th) {{
    var colIdx = parseInt(th.dataset.col);
    var sortType = th.dataset.sort;
    var label = th.dataset.label || 'column';
    var tbody = document.querySelector('.sheet tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));

    // Toggle direction if same column, otherwise default asc (desc for pay/rep)
    if (currentSort.col === colIdx) {{
        currentSort.asc = !currentSort.asc;
    }} else {{
        currentSort.col = colIdx;
        currentSort.asc = (sortType === 'pay' || sortType === 'stars') ? false : true;
    }}

    // Update arrow indicators
    document.querySelectorAll('.sortable').forEach(function(h) {{
        h.classList.remove('sort-asc', 'sort-desc');
        var arrow = h.querySelector('.sort-arrow');
        if (arrow) arrow.innerHTML = '\u21C5';
    }});
    th.classList.add(currentSort.asc ? 'sort-asc' : 'sort-desc');
    var activeArrow = th.querySelector('.sort-arrow');
    if (activeArrow) activeArrow.innerHTML = currentSort.asc ? '\u25B2' : '\u25BC';

    rows.sort(function(a, b) {{
        var cellA = a.querySelectorAll('td')[colIdx];
        var cellB = b.querySelectorAll('td')[colIdx];
        if (!cellA || !cellB) return 0;

        var valA, valB;

        if (sortType === 'date') {{
            var rawA = cellA.dataset.raw || cellA.textContent.trim();
            var rawB = cellB.dataset.raw || cellB.textContent.trim();
            valA = parseSortDate(rawA);
            valB = parseSortDate(rawB);
            if (!valA && !valB) return 0;
            if (!valA) return 1;
            if (!valB) return -1;
        }} else if (sortType === 'pay') {{
            valA = parsePay(cellA.textContent.trim());
            valB = parsePay(cellB.textContent.trim());
            if (!valA && !valB) return 0;
            if (!valA) return 1;
            if (!valB) return -1;
        }} else if (sortType === 'stars') {{
            valA = (cellA.textContent.match(/\u2605/g) || []).length;
            valB = (cellB.textContent.match(/\u2605/g) || []).length;
        }} else if (sortType === 'num') {{
            valA = parseFloat(cellA.textContent) || 0;
            valB = parseFloat(cellB.textContent) || 0;
        }} else if (sortType === 'status') {{
            var statusSel = cellA.querySelector('select');
            var statusSelB = cellB.querySelector('select');
            valA = statusSel ? statusSel.value : cellA.textContent.trim();
            valB = statusSelB ? statusSelB.value : cellB.textContent.trim();
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }} else {{
            valA = cellA.textContent.trim().toLowerCase();
            valB = cellB.textContent.trim().toLowerCase();
        }}

        var cmp;
        if (typeof valA === 'number' && typeof valB === 'number') {{
            cmp = valA - valB;
        }} else {{
            cmp = valA < valB ? -1 : valA > valB ? 1 : 0;
        }}

        return currentSort.asc ? cmp : -cmp;
    }});

    rows.forEach(function(row) {{ tbody.appendChild(row); }});
    restripe();
    try {{ localStorage.setItem('rn_tracker_sort', JSON.stringify(currentSort)); }} catch(ex) {{}}
    showToast('Sorted by ' + label + (currentSort.asc ? ' \u25B2' : ' \u25BC'));
}}

function restripe() {{
    var rows = document.querySelectorAll('.sheet tbody tr');
    var i = 0;
    rows.forEach(function(row) {{
        if (row.style.display !== 'none') {{
            row.classList.remove('even-row', 'odd-row');
            row.classList.add(i % 2 === 0 ? 'odd-row' : 'even-row');
            i++;
        }}
    }});
}}

function updateTableFooter() {{
    var rows = document.querySelectorAll('.sheet tbody tr:not(.group-header-row)');
    var visible = Array.from(rows).filter(function(r) {{ return r.style.display !== 'none'; }});
    var count = visible.length;
    if (count === 0) return;

    var statuses = {{}};
    var payTotal = 0, payCount = 0;
    var openNow = 0, upcoming = 0;
    var today = new Date(); today.setHours(0,0,0,0);

    visible.forEach(function(row) {{
        // Status counts
        var ss = row.querySelector('.status-select');
        var st = ss ? ss.value : 'Not Started';
        statuses[st] = (statuses[st] || 0) + 1;

        // Pay average
        var payCell = row.cells[11];
        if (payCell) {{
            var pm = payCell.textContent.match(/(\\d[\\d.,]+)\\/hr/);
            if (pm) {{ payTotal += parseFloat(pm[1].replace(',', '')); payCount++; }}
        }}

        // Open/upcoming
        var dateCells = row.querySelectorAll('.col-date');
        if (dateCells.length >= 2) {{
            var openRaw = dateCells[0].dataset.raw || '';
            var closeRaw = dateCells[1].dataset.raw || '';
            var od = parseDate(openRaw), cd = parseDate(closeRaw);
            if (od && cd) {{
                if (od <= today && cd >= today) openNow++;
                else if (od > today) {{ var diff = (od - today) / 86400000; if (diff <= 30) upcoming++; }}
            }}
        }}
    }});

    var el = function(id) {{ return document.getElementById(id); }};
    var lbl = el('tfoot-open');
    if (lbl) lbl.textContent = openNow + ' open';
    var lbl2 = el('tfoot-close');
    if (lbl2) lbl2.textContent = upcoming + ' soon';

    if (payCount > 0) {{
        var avg = (payTotal / payCount).toFixed(2);
        var payEl = el('tfoot-pay');
        if (payEl) payEl.textContent = 'Avg $' + avg + '/hr';
    }}

    // Status summary
    var statusParts = [];
    ['In Progress', 'Submitted', 'Interview', 'Offer'].forEach(function(s) {{
        if (statuses[s]) statusParts.push(statuses[s] + ' ' + s.charAt(0));
    }});
    var statusEl = el('tfoot-status');
    if (statusEl) statusEl.textContent = statusParts.join(', ') || count + ' shown';

    var summaryLabel = document.querySelector('.summary-label');
    if (summaryLabel) summaryLabel.textContent = count + ' of ' + rows.length + ' shown';
}}

function parseSortDate(str) {{
    if (!str) return null;
    var m = str.match(/(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
    if (m) return new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3])).getTime();
    m = str.match(/(\\d{{1,2}})\\/(\\d{{1,2}})\\/(\\d{{4}})/);
    if (m) return new Date(parseInt(m[3]), parseInt(m[1]) - 1, parseInt(m[2])).getTime();
    return null;
}}

function parsePay(str) {{
    if (!str || str === '\u2014') return null;
    var m = str.match(/(\\d[\\d.,]+)/);
    if (m) return parseFloat(m[1].replace(',', ''));
    return null;
}}

function updateCompareBtn() {{
    var btn = document.getElementById('compare-btn');
    if (!btn) return;
    var checked = document.querySelectorAll('.compare-check:checked');
    btn.disabled = checked.length < 2;
    btn.textContent = checked.length >= 2 ? 'Compare ' + checked.length : 'Compare';
    // Show/hide bulk action bar
    var bulkBar = document.getElementById('bulk-bar');
    if (bulkBar) {{
        if (checked.length > 0) {{
            bulkBar.style.display = 'flex';
            bulkBar.querySelector('.bulk-count').textContent = checked.length + ' selected';
        }} else {{
            bulkBar.style.display = 'none';
        }}
    }}
}}

function applySortPreset(preset) {{
    if (!preset) return;
    if (preset === 'smart') {{
        smartSort();
        document.getElementById('sort-preset').value = '';
        return;
    }}
    var colMap = {{
        'deadline': {{ col: 8, label: 'App Close' }},
        'pay-high': {{ col: 11, label: 'Pay' }},
        'rep-high': {{ col: 10, label: 'Reputation' }},
        'opening': {{ col: 7, label: 'App Open' }},
        'cohort': {{ col: 9, label: 'Cohort' }},
        'hospital': {{ col: 2, label: 'Hospital' }}
    }};
    var cfg = colMap[preset];
    if (!cfg) return;
    var th = document.querySelector('[data-col="' + cfg.col + '"]');
    if (th) {{
        // Set sort direction: asc for dates/text, desc for pay/rep
        var wantDesc = (preset === 'pay-high' || preset === 'rep-high');
        currentSort.col = cfg.col;
        currentSort.asc = wantDesc; // sortTable will toggle, so set opposite
        sortTable(th);
    }}
    document.getElementById('sort-preset').value = '';
}}

function smartSort() {{
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var savedStatuses = loadSavedStatuses();
    var tbody = document.querySelector('.sheet tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort(function(a, b) {{
        var aId = parseInt(a.dataset.id), bId = parseInt(b.dataset.id);
        var aP = PROGRAMS.find(function(p) {{ return p.id === aId; }});
        var bP = PROGRAMS.find(function(p) {{ return p.id === bId; }});
        if (!aP || !bP) return 0;
        var aScore = computeSmartScore(aP, savedStatuses, today);
        var bScore = computeSmartScore(bP, savedStatuses, today);
        return bScore - aScore;
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
    restripe();
    showToast('Sorted by smart match score');
}}

function computeSmartScore(p, statuses, today) {{
    var score = 0;
    var status = statuses[p.id] || p.application_status || 'Not Started';
    // Priority: unapplied programs with upcoming deadlines score highest
    if (status === 'Rejected') return -100;
    if (status === 'Offer') return -50; // Already got it, low priority
    if (status === 'Interview') score += 40;
    if (status === 'Submitted') score += 20;
    if (status === 'In Progress') score += 30;
    if (status === 'Not Started') score += 10;
    // Reputation bonus
    score += (p.reputation || 0) * 5;
    // Pay bonus
    var payMatch = (p.pay_range || '').match(/(\\d[\\d.,]+)/);
    if (payMatch) score += Math.min(20, parseFloat(payMatch[1].replace(',','')) / 5);
    // Deadline proximity — closer = higher (max 40 points)
    var closeDate = parseDate(p.app_close_date);
    if (closeDate) {{
        var daysLeft = Math.ceil((closeDate - today) / (1000 * 60 * 60 * 24));
        if (daysLeft < 0) score -= 30; // Closed
        else if (daysLeft <= 7) score += 40;
        else if (daysLeft <= 14) score += 30;
        else if (daysLeft <= 30) score += 20;
        else if (daysLeft <= 60) score += 10;
    }}
    // Open now bonus
    var openDate = parseDate(p.app_open_date);
    if (openDate && closeDate && openDate <= today && closeDate >= today) {{
        score += 50;
    }}
    // Has apply URL
    if (p.application_url) score += 5;
    return score;
}}

function bulkSetStatus() {{
    var sel = document.getElementById('bulk-status-select');
    var status = sel.value;
    if (!status) return;
    var checked = document.querySelectorAll('.compare-check:checked');
    checked.forEach(function(cb) {{
        var id = parseInt(cb.value);
        saveStatus(id, status);
        var row = cb.closest('tr');
        if (row) {{
            applyRowStatus(row, status);
            row.dataset.status = status;
            var tableSel = row.querySelector('.status-select');
            if (tableSel) tableSel.value = status;
        }}
    }});
    renderStatusSummary();
    sel.value = '';
    showToast(checked.length + ' programs set to ' + status);
}}

function bulkToggleFavorite() {{
    var checked = document.querySelectorAll('.compare-check:checked');
    var favs = loadFavorites();
    checked.forEach(function(cb) {{
        var id = parseInt(cb.value);
        if (favs.indexOf(id) === -1) favs.push(id);
    }});
    saveFavorites(favs);
    renderFavButtons();
    updateFavCount();
    showToast(checked.length + ' programs added to favorites');
}}

function clearSelection() {{
    document.querySelectorAll('.compare-check:checked').forEach(function(cb) {{
        cb.checked = false;
    }});
    var selectAll = document.getElementById('select-all');
    if (selectAll) selectAll.checked = false;
    updateCompareBtn();
}}

// Command palette
var cmdSelectedIdx = 0;
function toggleCommandPalette() {{
    var overlay = document.getElementById('cmd-overlay');
    if (overlay.style.display === 'none') {{
        overlay.style.display = 'flex';
        var input = document.getElementById('cmd-input');
        input.value = '';
        input.focus();
        renderCmdResults('');
    }} else {{
        closeCmdPalette();
    }}
}}

function closeCmdPalette() {{
    document.getElementById('cmd-overlay').style.display = 'none';
}}

function renderCmdResults(query) {{
    var results = [];
    var q = query.toLowerCase().trim();

    // Actions (always available)
    var actions = [
        {{ label: 'Switch to Table View', action: function() {{ showView('table'); }}, icon: '\\u2637' }},
        {{ label: 'Switch to Cards View', action: function() {{ showView('cards'); }}, icon: '\\u2637' }},
        {{ label: 'Switch to Pipeline View', action: function() {{ showView('pipeline'); }}, icon: '\\u2637' }},
        {{ label: 'Switch to Calendar View', action: function() {{ showView('calendar'); }}, icon: '\\u2637' }},
        {{ label: 'Switch to Stats View', action: function() {{ showView('stats'); }}, icon: '\\u2637' }},
        {{ label: 'Switch to Timeline View', action: function() {{ showView('timeline'); }}, icon: '\\u2637' }},
        {{ label: 'Toggle Dark Mode', action: function() {{ toggleTheme(); }}, icon: '\\u263E' }},
        {{ label: 'Toggle Focus Mode', action: function() {{ toggleFocusMode(); }}, icon: '\\u25C9' }},
        {{ label: 'Export CSV', action: function() {{ exportCSV(); }}, icon: '\\u21E9' }},
        {{ label: 'Copy Summary', action: function() {{ exportSummary(); }}, icon: '\\u270E' }},
        {{ label: 'Activity Feed', action: function() {{ showActivityFeed(); }}, icon: '\\u2630' }},
        {{ label: 'Backup Data', action: function() {{ backupData(); }}, icon: '\\u2B07' }},
        {{ label: 'Smart Sort', action: function() {{ smartSort(); }}, icon: '\\u2B50' }},
        {{ label: 'Jump to Open Programs', action: function() {{ jumpToOpen(); }}, icon: '\\u2193' }},
        {{ label: 'Batch Apply All Open', action: function() {{ batchApplyOpen(); }}, icon: '\\u2197' }},
        {{ label: 'Progress Card', action: function() {{ showProgressCard(); }}, icon: '\\u2588' }},
        {{ label: 'Download Progress Card', action: function() {{ downloadProgressCard(); }}, icon: '\\u21E9' }}
    ];

    // Programs
    PROGRAMS.forEach(function(p) {{
        results.push({{ label: p.hospital, desc: p.region + ' — ' + (p.pay_range || 'No pay info'), action: function() {{ showDetail(p.id); }}, icon: '\\u2B24', type: 'program' }});
    }});

    // Add actions
    actions.forEach(function(a) {{ a.type = 'action'; results.push(a); }});

    // Filter
    if (q) {{
        results = results.filter(function(r) {{ return r.label.toLowerCase().indexOf(q) !== -1 || (r.desc || '').toLowerCase().indexOf(q) !== -1; }});
    }} else {{
        // Show top actions first, then programs
        results = actions.concat(PROGRAMS.slice(0, 10).map(function(p) {{
            return {{ label: p.hospital, desc: p.region, action: function() {{ showDetail(p.id); }}, icon: '\\u2B24', type: 'program' }};
        }}));
    }}

    results = results.slice(0, 15);
    cmdSelectedIdx = 0;

    var container = document.getElementById('cmd-results');
    var html = '';
    results.forEach(function(r, i) {{
        html += '<div class="cmd-item' + (i === 0 ? ' cmd-active' : '') + '" data-idx="' + i + '" onmousedown="executeCmdItem(' + i + ')" onmouseover="setCmdActive(' + i + ')">';
        html += '<span class="cmd-icon">' + (r.icon || '') + '</span>';
        html += '<span class="cmd-label">' + r.label + '</span>';
        if (r.desc) html += '<span class="cmd-desc">' + r.desc + '</span>';
        html += '<span class="cmd-type">' + (r.type === 'program' ? 'Program' : 'Action') + '</span>';
        html += '</div>';
    }});
    if (results.length === 0) html = '<div class="cmd-empty">No results found</div>';
    container.innerHTML = html;
    window._cmdResults = results;
}}

function setCmdActive(idx) {{
    cmdSelectedIdx = idx;
    document.querySelectorAll('.cmd-item').forEach(function(el, i) {{
        el.classList.toggle('cmd-active', i === idx);
    }});
}}

function executeCmdItem(idx) {{
    var results = window._cmdResults || [];
    if (results[idx] && results[idx].action) {{
        closeCmdPalette();
        results[idx].action();
    }}
}}

// Command palette keyboard nav
(function() {{
    var input = document.getElementById('cmd-input');
    if (!input) return;
    input.addEventListener('input', function() {{ renderCmdResults(this.value); }});
    input.addEventListener('keydown', function(e) {{
        var items = document.querySelectorAll('.cmd-item');
        if (e.key === 'ArrowDown') {{
            e.preventDefault();
            cmdSelectedIdx = Math.min(cmdSelectedIdx + 1, items.length - 1);
            setCmdActive(cmdSelectedIdx);
        }} else if (e.key === 'ArrowUp') {{
            e.preventDefault();
            cmdSelectedIdx = Math.max(cmdSelectedIdx - 1, 0);
            setCmdActive(cmdSelectedIdx);
        }} else if (e.key === 'Enter') {{
            e.preventDefault();
            executeCmdItem(cmdSelectedIdx);
        }}
    }});
}})();

// Swipe gestures for mobile view switching
(function() {{
    var viewOrder = ['table', 'cards', 'pipeline', 'calendar', 'stats', 'timeline'];
    var touchStartX = 0, touchStartY = 0, touchEndX = 0, touchEndY = 0;
    var swipeThreshold = 80;

    document.addEventListener('touchstart', function(e) {{
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
    }}, {{ passive: true }});

    document.addEventListener('touchend', function(e) {{
        touchEndX = e.changedTouches[0].screenX;
        touchEndY = e.changedTouches[0].screenY;
        var dx = touchEndX - touchStartX;
        var dy = touchEndY - touchStartY;
        // Only trigger if horizontal swipe is dominant and exceeds threshold
        if (Math.abs(dx) > swipeThreshold && Math.abs(dx) > Math.abs(dy) * 1.5) {{
            // Don't swipe when inside scrollable containers or modals
            if (e.target.closest('.sheet-wrapper') || e.target.closest('.modal-overlay') ||
                e.target.closest('.cmd-palette') || e.target.closest('.pipeline-col-body')) return;
            var current = window._currentView || 'table';
            var idx = viewOrder.indexOf(current);
            if (dx < 0 && idx < viewOrder.length - 1) {{
                // Swipe left = next view
                showView(viewOrder[idx + 1]);
            }} else if (dx > 0 && idx > 0) {{
                // Swipe right = previous view
                showView(viewOrder[idx - 1]);
            }}
        }}
    }}, {{ passive: true }});
}})();

window._currentView = 'table';

function loadPins() {{
    try {{ return JSON.parse(localStorage.getItem('rn_tracker_pins') || '[]'); }} catch(e) {{ return []; }}
}}

function togglePin(id) {{
    var pins = loadPins();
    var idx = pins.indexOf(id);
    if (idx !== -1) {{
        pins.splice(idx, 1);
        showToast('Unpinned');
    }} else {{
        pins.push(id);
        showToast('Pinned to top');
    }}
    localStorage.setItem('rn_tracker_pins', JSON.stringify(pins));
    applyPins();
}}

function applyPins() {{
    var pins = loadPins();
    if (pins.length === 0) return;
    var tbody = document.querySelector('.sheet tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    // Move pinned rows to top in order
    pins.slice().reverse().forEach(function(pinId) {{
        var row = rows.find(function(r) {{ return parseInt(r.dataset.id) === pinId; }});
        if (row) {{
            tbody.insertBefore(row, tbody.firstChild);
            row.classList.add('pinned-row');
        }}
    }});
    // Mark pinned rows
    rows.forEach(function(r) {{
        if (pins.indexOf(parseInt(r.dataset.id)) !== -1) {{
            r.classList.add('pinned-row');
        }} else {{
            r.classList.remove('pinned-row');
        }}
    }});
}}

function toggleFab() {{
    var wrap = document.getElementById('fab-wrap');
    wrap.classList.toggle('open');
}}

function closeFab() {{
    document.getElementById('fab-wrap').classList.remove('open');
}}

function goCompare() {{
    var checked = document.querySelectorAll('.compare-check:checked');
    if (checked.length < 2) return;
    var ids = Array.from(checked).map(function(cb) {{ return parseInt(cb.value); }});
    var progs = ids.map(function(id) {{ return PROGRAMS.find(function(p) {{ return p.id === id; }}); }}).filter(Boolean);
    if (progs.length < 2) return;

    var fields = [
        ['Program', 'program_name'],
        ['Region', 'region'],
        ['City', 'city'],
        ['BSN Required', 'bsn_required'],
        ['App Open', 'app_open_date'],
        ['App Close', 'app_close_date'],
        ['Cohort Start', 'cohort_start'],
        ['Reputation', '_stars'],
        ['Pay', 'pay_range'],
        ['Length', '_length'],
        ['Specialties', '_specs'],
        ['Requirements', 'requirements'],
        ['Notes', 'personal_notes']
    ];

    var html = '<h2>Compare Programs</h2>';

    // Radar chart
    html += buildRadarChart(progs);

    html += '<div class="compare-scroll"><table class="compare-table"><thead><tr><th></th>';
    progs.forEach(function(p) {{
        html += '<th>' + escHtml(p.hospital) + '</th>';
    }});
    html += '</tr></thead><tbody>';

    // Find best values for highlighting
    var maxRep = Math.max.apply(null, progs.map(function(p) {{ return p.reputation || 0; }}));
    var parsedPays = progs.map(function(p) {{
        var m = (p.pay_range || '').match(/(\\d[\\d.,]+)/);
        return m ? parseFloat(m[1].replace(',', '')) : 0;
    }});
    var maxPay = Math.max.apply(null, parsedPays);

    fields.forEach(function(f) {{
        html += '<tr><td class="compare-label">' + f[0] + '</td>';
        progs.forEach(function(p, i) {{
            var val = '';
            var best = false;
            if (f[1] === '_stars') {{
                val = '\u2605'.repeat(p.reputation) + '\u2606'.repeat(5 - p.reputation);
                if (p.reputation === maxRep && maxRep > 0) best = true;
            }} else if (f[1] === '_length') {{
                val = p.program_length_months + ' months';
            }} else if (f[1] === '_specs') {{
                val = (p.specialty_units || []).join(', ');
            }} else if (f[1] === 'pay_range') {{
                val = p[f[1]] || '';
                if (parsedPays[i] === maxPay && maxPay > 0) best = true;
            }} else {{
                val = p[f[1]] || '';
            }}
            var cls = best ? ' class="compare-best"' : '';
            html += '<td' + cls + '>' + escHtml(val).replace(/\\n/g, '<br>') + '</td>';
        }});
        html += '</tr>';
    }});

    html += '</tbody></table></div>';
    document.getElementById('compare-body').innerHTML = html;
    openModal('compare-modal');
}}

function buildRadarChart(progs) {{
    var size = 240, cx = size / 2, cy = size / 2, r = 90;
    var axes = ['Reputation', 'Pay', 'Length', 'Deadline', 'Specialties'];
    var n = axes.length;
    var colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899'];
    var today = new Date(); today.setHours(0,0,0,0);

    // Normalize values to 0-1 for each program
    var maxPay = 0;
    progs.forEach(function(p) {{
        var m = (p.pay_range || '').match(/(\\d[\\d.,]+)/);
        if (m) {{ var v = parseFloat(m[1].replace(',','')); if (v > maxPay) maxPay = v; }}
    }});

    function getValues(p) {{
        var rep = (p.reputation || 0) / 5;
        var m = (p.pay_range || '').match(/(\\d[\\d.,]+)/);
        var pay = m && maxPay > 0 ? parseFloat(m[1].replace(',','')) / maxPay : 0;
        var len = Math.min((p.program_length_months || 0) / 24, 1);
        var close = parseDate(p.app_close_date);
        var deadline = 0;
        if (close) {{
            var dl = Math.ceil((close - today) / (1000*60*60*24));
            if (dl >= 0 && dl <= 180) deadline = 1 - (dl / 180);
        }}
        var specs = Math.min((p.specialty_units || []).length / 10, 1);
        return [rep, pay, len, deadline, specs];
    }}

    var svg = '<div class="radar-wrap"><svg viewBox="0 0 ' + size + ' ' + size + '" class="radar-svg">';
    // Grid circles
    for (var level = 1; level <= 4; level++) {{
        var lr = r * level / 4;
        svg += '<circle cx="' + cx + '" cy="' + cy + '" r="' + lr + '" fill="none" stroke="#e5e7eb" stroke-width="0.5"/>';
    }}
    // Axis lines and labels
    for (var i = 0; i < n; i++) {{
        var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
        var x = cx + r * Math.cos(angle);
        var y = cy + r * Math.sin(angle);
        svg += '<line x1="' + cx + '" y1="' + cy + '" x2="' + x + '" y2="' + y + '" stroke="#d1d5db" stroke-width="0.5"/>';
        var lx = cx + (r + 18) * Math.cos(angle);
        var ly = cy + (r + 18) * Math.sin(angle);
        svg += '<text x="' + lx + '" y="' + ly + '" text-anchor="middle" dominant-baseline="middle" font-size="8" fill="#6b7280">' + axes[i] + '</text>';
    }}
    // Program polygons
    progs.forEach(function(p, pi) {{
        var vals = getValues(p);
        var points = '';
        for (var i = 0; i < n; i++) {{
            var angle = (Math.PI * 2 * i / n) - Math.PI / 2;
            var vr = r * vals[i];
            var x = cx + vr * Math.cos(angle);
            var y = cy + vr * Math.sin(angle);
            points += x + ',' + y + ' ';
        }}
        var color = colors[pi % colors.length];
        svg += '<polygon points="' + points.trim() + '" fill="' + color + '" fill-opacity="0.15" stroke="' + color + '" stroke-width="1.5"/>';
    }});
    svg += '</svg>';
    // Legend
    svg += '<div class="radar-legend">';
    progs.forEach(function(p, pi) {{
        svg += '<span class="radar-legend-item"><span class="radar-legend-dot" style="background:' + colors[pi % colors.length] + '"></span>' + p.hospital + '</span>';
    }});
    svg += '</div></div>';
    return svg;
}}

function closeCompareModal() {{
    closeModalEl(document.getElementById('compare-modal'));
}}

function shareUrl() {{
    var url = window.location.href;
    if (navigator.clipboard) {{
        navigator.clipboard.writeText(url).then(function() {{
            showToast('URL copied to clipboard!');
        }});
    }} else {{
        // Fallback
        var input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('URL copied!');
    }}
}}

function exportICS() {{
    var today = new Date();
    var lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CA RN Tracker//EN', 'CALSCALE:GREGORIAN'];
    PROGRAMS.forEach(function(p) {{
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        var cohortD = parseDate(p.cohort_start);

        if (openD) {{
            lines.push('BEGIN:VEVENT');
            lines.push('DTSTART;VALUE=DATE:' + fmtICS(openD));
            lines.push('DTEND;VALUE=DATE:' + fmtICS(new Date(openD.getTime() + 86400000)));
            lines.push('SUMMARY:' + p.hospital + ' - App Opens');
            lines.push('DESCRIPTION:Application window opens for ' + p.program_name + '\\nRegion: ' + p.region);
            if (p.application_url) lines.push('URL:' + p.application_url);
            lines.push('BEGIN:VALARM');
            lines.push('TRIGGER:-P1D');
            lines.push('ACTION:DISPLAY');
            lines.push('DESCRIPTION:' + p.hospital + ' application opens tomorrow!');
            lines.push('END:VALARM');
            lines.push('END:VEVENT');
        }}

        if (closeD) {{
            lines.push('BEGIN:VEVENT');
            lines.push('DTSTART;VALUE=DATE:' + fmtICS(closeD));
            lines.push('DTEND;VALUE=DATE:' + fmtICS(new Date(closeD.getTime() + 86400000)));
            lines.push('SUMMARY:DEADLINE: ' + p.hospital + ' - App Closes');
            lines.push('DESCRIPTION:Application deadline for ' + p.program_name + '\\nRegion: ' + p.region);
            if (p.application_url) lines.push('URL:' + p.application_url);
            lines.push('BEGIN:VALARM');
            lines.push('TRIGGER:-P3D');
            lines.push('ACTION:DISPLAY');
            lines.push('DESCRIPTION:' + p.hospital + ' deadline in 3 days!');
            lines.push('END:VALARM');
            lines.push('BEGIN:VALARM');
            lines.push('TRIGGER:-P1D');
            lines.push('ACTION:DISPLAY');
            lines.push('DESCRIPTION:' + p.hospital + ' deadline TOMORROW!');
            lines.push('END:VALARM');
            lines.push('END:VEVENT');
        }}

        if (cohortD) {{
            lines.push('BEGIN:VEVENT');
            lines.push('DTSTART;VALUE=DATE:' + fmtICS(cohortD));
            lines.push('DTEND;VALUE=DATE:' + fmtICS(new Date(cohortD.getTime() + 86400000)));
            lines.push('SUMMARY:' + p.hospital + ' - Cohort Starts');
            lines.push('DESCRIPTION:Residency cohort begins at ' + p.program_name);
            lines.push('END:VEVENT');
        }}
    }});
    lines.push('END:VCALENDAR');

    var blob = new Blob([lines.join('\\r\\n')], {{type: 'text/calendar'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'ca_rn_programs.ics';
    a.click();
    showToast('Calendar exported! Import into Google Calendar, Apple Calendar, or Outlook.');
}}

function fmtICS(d) {{
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + m + day;
}}

function exportCSV() {{
    var checklistLabels = ['Review requirements', 'Prepare resume/CV', 'Write cover letter', 'Gather references', 'Submit application', 'Follow up'];
    var csv = 'Hospital,Program,Region,City,BSN Required,App Open,App Close,Cohort,Reputation,Pay,Length (mo),Specialties,Requirements,Status,Checklist Progress,Notes,URL\\n';
    var savedStatuses = loadSavedStatuses();
    var savedNotes = loadSavedNotes();
    PROGRAMS.forEach(function(p) {{
        var status = savedStatuses[p.id] || p.application_status || 'Not Started';
        var cl = loadChecklist(p.id);
        var clText = cl.length + '/' + checklistLabels.length;
        var notes = savedNotes[p.id] !== undefined ? savedNotes[p.id] : (p.personal_notes || '');
        var vals = [
            p.hospital,
            p.program_name,
            p.region,
            p.city,
            p.bsn_required,
            p.app_open_date,
            p.app_close_date,
            p.cohort_start,
            p.reputation,
            p.pay_range,
            p.program_length_months,
            (p.specialty_units || []).join('; '),
            p.requirements,
            status,
            clText,
            notes.replace(/\\n/g, ' '),
            p.application_url
        ];
        csv += vals.map(function(v) {{ return '"' + String(v || '').replace(/"/g, '""') + '"'; }}).join(',') + '\\n';
    }});
    var blob = new Blob([csv], {{type: 'text/csv'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'ca_rn_programs.csv';
    a.click();
    showToast('CSV exported');
}}

function updateUrlParams() {{
    var params = new URLSearchParams();
    var si = document.querySelector('.sheet-filters input[type="search"]');
    if (si && si.value) params.set('q', si.value);
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function(sel) {{
        if (sel.value) {{
            var key = sel.dataset.instant === 'cohort-status' ? 'cohort' : sel.dataset.instant;
            params.set(key, sel.value);
        }}
    }});
    var newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
    history.replaceState(null, '', newUrl);
}}

function highlightSelectedRow(rows, idx) {{
    document.querySelectorAll('.sheet tbody tr.selected-row').forEach(function(r) {{
        r.classList.remove('selected-row');
    }});
    if (idx >= 0 && idx < rows.length) {{
        rows[idx].classList.add('selected-row');
        rows[idx].scrollIntoView({{ block: 'nearest' }});
    }}
}}

function toggleMoreMenu() {{
    var menu = document.getElementById('more-menu');
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    // Close col menu when toggling more menu
    if (menu.style.display === 'none') {{
        document.getElementById('col-menu').style.display = 'none';
    }}
}}

function toggleColMenu() {{
    var colMenu = document.getElementById('col-menu');
    colMenu.style.display = colMenu.style.display === 'none' ? 'block' : 'none';
}}

// Close menus when clicking outside
document.addEventListener('click', function(e) {{
    var moreWrap = document.querySelector('.more-actions-wrap');
    if (moreWrap && !moreWrap.contains(e.target)) {{
        var moreMenu = document.getElementById('more-menu');
        var colMenu = document.getElementById('col-menu');
        if (moreMenu) moreMenu.style.display = 'none';
        if (colMenu) colMenu.style.display = 'none';
    }}
}});

// Column visibility toggle
document.addEventListener('change', function(e) {{
    if (e.target.dataset.toggleCol) {{
        var colClass = e.target.dataset.toggleCol;
        var show = e.target.checked;
        var display = show ? '' : 'none';
        document.querySelectorAll('.' + colClass).forEach(function(el) {{
            el.style.display = display;
        }});
        // Save preferences
        try {{
            var prefs = JSON.parse(localStorage.getItem('rn_tracker_cols') || '{{}}');
            prefs[colClass] = show;
            localStorage.setItem('rn_tracker_cols', JSON.stringify(prefs));
        }} catch(ex) {{}}
    }}
}});

// Restore column visibility preferences on load
(function() {{
    try {{
        var prefs = JSON.parse(localStorage.getItem('rn_tracker_cols') || '{{}}');
        Object.keys(prefs).forEach(function(colClass) {{
            if (!prefs[colClass]) {{
                document.querySelectorAll('.' + colClass).forEach(function(el) {{
                    el.style.display = 'none';
                }});
                var cb = document.querySelector('[data-toggle-col="' + colClass + '"]');
                if (cb) cb.checked = false;
            }}
        }});
    }} catch(ex) {{}}
}})();

function backupData() {{
    var data = {{
        statuses: loadSavedStatuses(),
        notes: loadSavedNotes(),
        checklists: JSON.parse(localStorage.getItem('rn_tracker_checklists') || '{{}}'),
        favorites: loadFavorites(),
        tags: JSON.parse(localStorage.getItem('rn_tracker_tags') || '{{}}'),
        activityLog: JSON.parse(localStorage.getItem('rn_tracker_log') || '[]'),
        dismissedNotifs: JSON.parse(localStorage.getItem('rn_tracker_notif_dismissed') || '[]'),
        theme: localStorage.getItem('rn_tracker_theme') || 'light',
        density: localStorage.getItem('rn_tracker_density') || 'normal',
        cols: JSON.parse(localStorage.getItem('rn_tracker_cols') || '{{}}'),
        accent: localStorage.getItem('rn_tracker_accent') || null,
        recentSearches: JSON.parse(localStorage.getItem('rn_tracker_recent_searches') || '[]'),
        pins: JSON.parse(localStorage.getItem('rn_tracker_pins') || '[]'),
        statusHistory: JSON.parse(localStorage.getItem('rn_tracker_status_history') || '{{}}'),
        exported: new Date().toISOString()
    }};
    var blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'rn_tracker_backup_' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
    showToast('Backup saved');
}}

function restoreData(input) {{
    var file = input.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {{
        try {{
            var data = JSON.parse(e.target.result);
            if (data.statuses) localStorage.setItem('rn_tracker_statuses', JSON.stringify(data.statuses));
            if (data.notes) localStorage.setItem('rn_tracker_notes', JSON.stringify(data.notes));
            if (data.checklists) localStorage.setItem('rn_tracker_checklists', JSON.stringify(data.checklists));
            if (data.theme) localStorage.setItem('rn_tracker_theme', data.theme);
            if (data.density) localStorage.setItem('rn_tracker_density', data.density);
            if (data.favorites) localStorage.setItem('rn_tracker_favorites', JSON.stringify(data.favorites));
            if (data.tags) localStorage.setItem('rn_tracker_tags', JSON.stringify(data.tags));
            if (data.activityLog) localStorage.setItem('rn_tracker_log', JSON.stringify(data.activityLog));
            if (data.dismissedNotifs) localStorage.setItem('rn_tracker_notif_dismissed', JSON.stringify(data.dismissedNotifs));
            if (data.cols) localStorage.setItem('rn_tracker_cols', JSON.stringify(data.cols));
            if (data.accent) localStorage.setItem('rn_tracker_accent', data.accent);
            if (data.recentSearches) localStorage.setItem('rn_tracker_recent_searches', JSON.stringify(data.recentSearches));
            if (data.pins) localStorage.setItem('rn_tracker_pins', JSON.stringify(data.pins));
            if (data.statusHistory) localStorage.setItem('rn_tracker_status_history', JSON.stringify(data.statusHistory));
            showToast('Data restored! Reloading...');
            setTimeout(function() {{ window.location.reload(); }}, 1000);
        }} catch(ex) {{
            showToast('Error: Invalid backup file');
        }}
    }};
    reader.readAsText(file);
    input.value = '';
}}

function toggleTheme() {{
    var html = document.documentElement;
    var btn = document.getElementById('theme-toggle');
    var current = localStorage.getItem('rn_tracker_theme') || 'light';
    var next;
    if (current === 'light') {{ next = 'dark'; }}
    else if (current === 'dark') {{ next = 'auto'; }}
    else {{ next = 'light'; }}
    localStorage.setItem('rn_tracker_theme', next);
    applyTheme(next);
}}

function applyTheme(theme) {{
    var html = document.documentElement;
    var btn = document.getElementById('theme-toggle');
    var resolved = theme;
    if (theme === 'auto') {{
        resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    html.dataset.theme = resolved;
    if (btn) {{
        if (theme === 'light') btn.textContent = 'Dark';
        else if (theme === 'dark') btn.textContent = 'Auto';
        else btn.textContent = 'Light';
    }}
}}

// Restore theme preference
(function() {{
    try {{
        var theme = localStorage.getItem('rn_tracker_theme') || 'light';
        applyTheme(theme);
        // Listen for system preference changes in auto mode
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function() {{
            if (localStorage.getItem('rn_tracker_theme') === 'auto') {{
                applyTheme('auto');
            }}
        }});
    }} catch(ex) {{}}
}})();

// Accent color picker
function toggleAccentPalette() {{
    var p = document.getElementById('accent-palette');
    p.classList.toggle('visible');
}}

function setAccent(main, light, dark) {{
    document.documentElement.style.setProperty('--accent', main);
    document.documentElement.style.setProperty('--accent-light', light);
    document.documentElement.style.setProperty('--accent-dark', dark);
    document.getElementById('accent-swatch').style.background = main;
    localStorage.setItem('rn_tracker_accent', JSON.stringify({{main: main, light: light, dark: dark}}));
    // Mark active dot
    document.querySelectorAll('.accent-dot').forEach(function(d) {{
        d.classList.toggle('active', d.style.background === main || d.style.backgroundColor === main);
    }});
    document.getElementById('accent-palette').classList.remove('visible');
}}

// Restore accent preference
(function() {{
    try {{
        var saved = JSON.parse(localStorage.getItem('rn_tracker_accent'));
        if (saved) {{
            document.documentElement.style.setProperty('--accent', saved.main);
            document.documentElement.style.setProperty('--accent-light', saved.light);
            document.documentElement.style.setProperty('--accent-dark', saved.dark);
            var sw = document.getElementById('accent-swatch');
            if (sw) sw.style.background = saved.main;
        }}
    }} catch(ex) {{}}
}})();

function toggleDensity() {{
    var table = document.querySelector('.sheet');
    var btn = document.getElementById('density-btn');
    if (table.classList.contains('density-compact')) {{
        table.classList.remove('density-compact');
        btn.textContent = 'Compact';
        localStorage.setItem('rn_tracker_density', 'normal');
    }} else {{
        table.classList.add('density-compact');
        btn.textContent = 'Comfortable';
        localStorage.setItem('rn_tracker_density', 'compact');
    }}
}}

// Restore density preference
(function() {{
    try {{
        if (localStorage.getItem('rn_tracker_density') === 'compact') {{
            document.querySelector('.sheet').classList.add('density-compact');
            var btn = document.getElementById('density-btn');
            if (btn) btn.textContent = 'Comfortable';
        }}
    }} catch(ex) {{}}
}})();

function escHtml(str) {{
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function getVisibleProgramIds() {{
    return Array.from(document.querySelectorAll('.sheet tbody tr')).filter(function(r) {{
        return r.style.display !== 'none';
    }}).map(function(r) {{ return parseInt(r.dataset.id); }});
}}

// Tags
function loadTags(id) {{
    try {{
        var all = JSON.parse(localStorage.getItem('rn_tracker_tags') || '{{}}');
        return all[id] || [];
    }} catch(e) {{ return []; }}
}}

function saveTags(id, tags) {{
    try {{
        var all = JSON.parse(localStorage.getItem('rn_tracker_tags') || '{{}}');
        all[id] = tags;
        localStorage.setItem('rn_tracker_tags', JSON.stringify(all));
    }} catch(e) {{}}
}}

function renderTableTags() {{
    var allTags = JSON.parse(localStorage.getItem('rn_tracker_tags') || '{{}}');
    document.querySelectorAll('.sheet tbody tr').forEach(function(row) {{
        var id = row.dataset.id;
        var tags = allTags[id] || [];
        var hospCell = row.querySelector('.col-hospital');
        if (!hospCell) return;
        // Remove old tags
        hospCell.querySelectorAll('.table-tag').forEach(function(t) {{ t.remove(); }});
        if (tags.length > 0) {{
            var tagHtml = '';
            tags.slice(0, 2).forEach(function(t) {{
                tagHtml += '<span class="table-tag">' + t + '</span>';
            }});
            if (tags.length > 2) tagHtml += '<span class="table-tag table-tag-more">+' + (tags.length - 2) + '</span>';
            var wrap = document.createElement('span');
            wrap.className = 'table-tags-wrap';
            wrap.innerHTML = tagHtml;
            hospCell.appendChild(wrap);
        }}
    }});
}}

function addTagFromSelect(id, sel) {{
    var val = sel.value;
    if (!val) return;
    if (val === '__custom') {{
        var custom = prompt('Enter custom tag:');
        if (!custom || !custom.trim()) {{ sel.value = ''; return; }}
        val = custom.trim();
    }}
    var tags = loadTags(id);
    if (tags.indexOf(val) === -1) {{
        tags.push(val);
        saveTags(id, tags);
        logActivity(id, 'Added tag: ' + val);
    }}
    sel.value = '';
    showDetail(id); // re-render
    renderTableTags();
    showToast('Tag added');
}}

function removeTag(id, tag) {{
    var tags = loadTags(id);
    tags = tags.filter(function(t) {{ return t !== tag; }});
    saveTags(id, tags);
    logActivity(id, 'Removed tag: ' + tag);
    showDetail(id); // re-render
    renderTableTags();
    showToast('Tag removed');
}}

function findSimilarPrograms(prog, limit) {{
    var scores = [];
    PROGRAMS.forEach(function(p) {{
        if (p.id === prog.id) return;
        var score = 0;
        // Same region
        if (p.region === prog.region) score += 3;
        // Similar reputation
        var repDiff = Math.abs((p.reputation || 0) - (prog.reputation || 0));
        if (repDiff === 0) score += 2;
        else if (repDiff === 1) score += 1;
        // Similar pay
        var payA = parsePay(prog.pay_range || '');
        var payB = parsePay(p.pay_range || '');
        if (payA && payB) {{
            var payDiff = Math.abs(payA - payB);
            if (payDiff < 5) score += 2;
            else if (payDiff < 10) score += 1;
        }}
        // Same BSN requirement
        if (p.bsn_required === prog.bsn_required) score += 1;
        // Overlapping specialties
        var specA = prog.specialty_units || [];
        var specB = p.specialty_units || [];
        specA.forEach(function(s) {{
            if (specB.indexOf(s) !== -1) score += 1;
        }});
        if (score > 0) scores.push({{ prog: p, score: score }});
    }});
    scores.sort(function(a, b) {{ return b.score - a.score; }});
    return scores.slice(0, limit).map(function(s) {{ return s.prog; }});
}}

// Detail modal
function showDetail(id) {{
    var p = PROGRAMS.find(function(prog) {{ return prog.id === id; }});
    if (!p) return;

    var stars = '\u2605'.repeat(p.reputation) + '\u2606'.repeat(5 - p.reputation);
    var specs = (p.specialty_units || []).join(', ') || 'N/A';
    var infoSessions = (p.info_session_dates || []).join(', ') || 'None listed';
    var notes = escHtml(p.personal_notes || '').replace(/\\n/g, '<br>');
    var repNotes = escHtml(p.reputation_notes || '').replace(/\\n/g, '<br>');

    var bsnCls = p.bsn_required === 'No' ? 'bsn-no' : p.bsn_required === 'Preferred' ? 'bsn-pref' : 'bsn-req';

    var html = '<div class="detail-modal-header">';
    html += '<h2>' + escHtml(p.hospital) + '</h2>';
    html += '<p class="detail-program-name">' + escHtml(p.program_name) + '</p>';
    // Status selector in modal
    var savedStatuses = loadSavedStatuses();
    var currentStatus = savedStatuses[p.id] || p.application_status || 'Not Started';
    var modalStatuses = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer', 'Rejected'];
    var statusOpts = '';
    modalStatuses.forEach(function(s) {{
        statusOpts += '<option value="' + s + '"' + (s === currentStatus ? ' selected' : '') + '>' + s + '</option>';
    }});
    var statusSelCls = selectStatusClasses[currentStatus] || '';

    // Readiness score
    var readinessScore = 0;
    var statusPoints2 = {{ 'Not Started': 0, 'In Progress': 10, 'Submitted': 30, 'Interview': 35, 'Offer': 40, 'Rejected': 0 }};
    readinessScore += (statusPoints2[currentStatus] || 0);
    readinessScore += Math.round(savedChecklist.length / 6 * 40);
    if (currentNotes && currentNotes.trim()) readinessScore += 10;
    if (loadFavorites().indexOf(p.id) !== -1) readinessScore += 10;
    var readinessColor = readinessScore >= 70 ? '#22c55e' : readinessScore >= 40 ? '#f59e0b' : '#ef4444';

    html += '<div class="detail-meta"><span class="stars">' + stars + '</span>';
    html += ' <span class="' + bsnCls + '">' + escHtml(p.bsn_required || 'N/A') + ' BSN</span>';
    html += ' <select class="modal-status-select ' + statusSelCls + '" id="modal-status" data-id="' + p.id + '">' + statusOpts + '</select>';
    html += ' <span class="readiness-badge" style="background:' + readinessColor + '">' + readinessScore + '% ready</span>';
    if (p.last_updated) {{
        html += ' <span class="detail-updated">Updated: ' + escHtml(p.last_updated) + '</span>';
    }}
    html += '</div>';
    html += '</div>';

    // Progress pipeline
    var stages = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer'];
    var stageIdx = stages.indexOf(currentStatus);
    if (currentStatus === 'Rejected') stageIdx = -2; // special handling
    html += '<div class="progress-pipeline">';
    stages.forEach(function(stage, i) {{
        var cls = 'pp-step';
        if (currentStatus === 'Rejected') {{
            cls += ' pp-rejected';
        }} else if (i < stageIdx) {{
            cls += ' pp-done';
        }} else if (i === stageIdx) {{
            cls += ' pp-current';
        }}
        html += '<div class="' + cls + '">';
        html += '<div class="pp-dot"></div>';
        html += '<span class="pp-label">' + stage + '</span>';
        html += '</div>';
        if (i < stages.length - 1) {{
            html += '<div class="pp-line' + (i < stageIdx ? ' pp-line-done' : '') + '"></div>';
        }}
    }});
    if (currentStatus === 'Rejected') {{
        html += '<div class="pp-line pp-line-rejected"></div>';
        html += '<div class="pp-step pp-rejected-step"><div class="pp-dot"></div><span class="pp-label">Rejected</span></div>';
    }}
    html += '</div>';

    // Status history
    var sHistory = getStatusHistory(p.id);
    if (sHistory.length > 0) {{
        html += '<details class="status-history"><summary>Status History (' + sHistory.length + ')</summary>';
        html += '<div class="sh-entries">';
        sHistory.slice().reverse().slice(0, 10).forEach(function(entry) {{
            var t = new Date(entry.time);
            var dateStr = t.toLocaleDateString() + ' ' + t.toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}});
            html += '<div class="sh-entry"><span class="sh-status">' + entry.status + '</span><span class="sh-time">' + dateStr + '</span></div>';
        }});
        html += '</div></details>';
    }}

    // Compute deadline status for modal
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var modalOpenDate = parseDate(p.app_open_date);
    var modalCloseDate = parseDate(p.app_close_date);
    var deadlineHtml = '';
    if (modalOpenDate && modalCloseDate) {{
        if (modalCloseDate < today) {{
            deadlineHtml = ' <span class="deadline-past">closed</span>';
        }} else if (modalOpenDate <= today && modalCloseDate >= today) {{
            var dLeft = Math.ceil((modalCloseDate - today) / (1000*60*60*24));
            deadlineHtml = ' <span class="badge-open">OPEN</span> <span class="deadline-soon">' + dLeft + 'd left</span>';
        }} else if (modalOpenDate > today) {{
            var dUntil = Math.ceil((modalOpenDate - today) / (1000*60*60*24));
            deadlineHtml = ' <span class="deadline-soon">opens in ' + dUntil + 'd</span>';
        }}
    }}

    html += '<div class="detail-grid">';

    html += '<div class="detail-section"><h3>Dates' + deadlineHtml + '</h3><dl>';
    html += '<dt>App Open</dt><dd>' + escHtml(p.app_open_date || 'TBD') + '</dd>';
    html += '<dt>App Close</dt><dd>' + escHtml(p.app_close_date || 'TBD') + '</dd>';
    html += '<dt>Cohort Start</dt><dd>' + escHtml(p.cohort_start || 'TBD') + '</dd>';
    html += '<dt>Info Sessions</dt><dd>' + escHtml(infoSessions) + '</dd>';
    html += '</dl>';
    // App window progress bar
    if (modalOpenDate && modalCloseDate && modalOpenDate <= today && modalCloseDate >= today) {{
        var totalWindow = (modalCloseDate - modalOpenDate) / 86400000;
        var elapsed = (today - modalOpenDate) / 86400000;
        var remaining = totalWindow - elapsed;
        var elapsedPct = Math.min(Math.round(elapsed / totalWindow * 100), 100);
        html += '<div class="window-progress">';
        html += '<div class="window-progress-label">' + Math.round(remaining) + ' of ' + Math.round(totalWindow) + ' days remaining</div>';
        html += '<div class="window-progress-bar"><div class="window-progress-fill" style="width:' + elapsedPct + '%"></div></div>';
        html += '</div>';
    }}
    html += '</div>';

    html += '<div class="detail-section"><h3>Details</h3><dl>';
    html += '<dt>Region</dt><dd>' + escHtml(p.region) + '</dd>';
    html += '<dt>City</dt><dd>' + escHtml(p.city) + '</dd>';
    html += '<dt>Pay</dt><dd>' + escHtml(p.pay_range || 'N/A') + '</dd>';
    html += '<dt>Length</dt><dd>' + (p.program_length_months || 'N/A') + ' months</dd>';
    html += '</dl></div>';

    html += '</div>';

    // Mini timeline bar
    var tlStart = new Date(2026, 1, 1);
    var tlEnd = new Date(2027, 0, 31);
    var tlTotal = tlEnd - tlStart;
    function tlPct(d) {{ return Math.max(0, Math.min(100, ((d - tlStart) / tlTotal) * 100)); }}
    html += '<div class="mini-timeline"><div class="mini-tl-track">';
    // Month markers
    var tlMonths = ['F','M','A','M','J','J','A','S','O','N','D','J'];
    for (var mi = 0; mi < 12; mi++) {{
        var mDate = new Date(2026, mi + 1, 1);
        html += '<span class="mini-tl-month" style="left:' + tlPct(mDate) + '%">' + tlMonths[mi] + '</span>';
    }}
    // Today marker
    var todayPct = tlPct(today);
    html += '<div class="mini-tl-today" style="left:' + todayPct + '%"></div>';
    // App window bar
    var oD = parseDate(p.app_open_date);
    var cD = parseDate(p.app_close_date);
    if (oD && cD) {{
        var barL = tlPct(oD);
        var barW = Math.max(tlPct(cD) - barL, 1);
        html += '<div class="mini-tl-bar" style="left:' + barL + '%;width:' + barW + '%" title="App window"></div>';
    }}
    // Cohort marker
    var coD = parseDate(p.cohort_start);
    if (coD) {{
        html += '<div class="mini-tl-cohort" style="left:' + tlPct(coD) + '%" title="Cohort start"></div>';
    }}
    html += '</div></div>';

    html += '<div class="detail-section"><h3>Specialties</h3><p>' + escHtml(specs) + '</p></div>';
    html += '<div class="detail-section"><h3>Requirements</h3><p>' + escHtml(p.requirements || 'N/A').replace(/\\n/g, '<br>') + '</p></div>';

    if (repNotes) {{
        html += '<div class="detail-section"><h3>Reputation Notes</h3><p class="detail-rep-notes">' + repNotes + '</p></div>';
    }}

    // Editable notes — load saved notes from localStorage
    var savedNotes = loadSavedNotes();
    var currentNotes = savedNotes[p.id] !== undefined ? savedNotes[p.id] : (p.personal_notes || '');
    html += '<div class="detail-section"><h3>Your Notes</h3>';
    html += '<div class="note-templates">';
    var noteTemplates = ['Need references', 'Resume updated', 'Cover letter drafted', 'Waiting for response', 'Interview scheduled', 'Strong match', 'Backup option'];
    noteTemplates.forEach(function(t) {{
        html += '<button class="note-tpl-btn" onclick="insertNoteTemplate(\'' + t + '\')">' + t + '</button>';
    }});
    html += '</div>';
    html += '<textarea id="modal-notes" class="modal-notes-input" rows="4" placeholder="Add your notes here...">' + escHtml(currentNotes) + '</textarea>';
    html += '<small class="notes-hint">Notes are saved to your browser automatically.</small>';
    html += '</div>';

    // Application checklist
    var checklistItems = ['Review requirements', 'Prepare resume/CV', 'Write cover letter', 'Gather references', 'Submit application', 'Follow up'];
    var savedChecklist = loadChecklist(p.id);
    html += '<div class="detail-section"><h3>Application Checklist</h3>';
    html += '<ul class="app-checklist" id="modal-checklist">';
    checklistItems.forEach(function(item, i) {{
        var checked = savedChecklist.indexOf(i) !== -1;
        var cls = checked ? ' checked-label' : '';
        html += '<li><input type="checkbox" data-idx="' + i + '"' + (checked ? ' checked' : '') + '><span class="' + cls + '">' + item + '</span></li>';
    }});
    html += '</ul>';
    var done = savedChecklist.length;
    var pct = Math.round(done / checklistItems.length * 100);
    html += '<div class="checklist-progress-bar"><div class="checklist-progress-fill" style="width:' + pct + '%"></div></div>';
    html += '<div class="checklist-progress">' + done + ' of ' + checklistItems.length + ' complete (' + pct + '%)</div>';
    html += '</div>';

    // Tags
    var savedTags = loadTags(p.id);
    var presetTags = ['Top Pick', 'Backup', 'Good Location', 'Great Pay', 'Dream Job', 'Research More'];
    html += '<div class="detail-section"><h3>Tags</h3>';
    html += '<div class="tag-container" id="modal-tags">';
    savedTags.forEach(function(t) {{
        html += '<span class="tag-pill">' + escHtml(t) + ' <button onclick="removeTag(' + p.id + ', \\\'' + escHtml(t).replace(/'/g, "\\\\'") + '\\\')" class="tag-remove">&times;</button></span>';
    }});
    html += '<div class="tag-add-wrap">';
    html += '<select id="tag-select" onchange="addTagFromSelect(' + p.id + ', this)">';
    html += '<option value="">+ Add tag</option>';
    presetTags.forEach(function(t) {{
        if (savedTags.indexOf(t) === -1) {{
            html += '<option value="' + escHtml(t) + '">' + escHtml(t) + '</option>';
        }}
    }});
    html += '<option value="__custom">Custom...</option>';
    html += '</select>';
    html += '</div></div></div>';

    // Similar programs
    var similar = findSimilarPrograms(p, 4);
    if (similar.length > 0) {{
        html += '<div class="detail-section"><h3>Similar Programs</h3>';
        html += '<div class="similar-programs">';
        similar.forEach(function(sp) {{
            var spStars = '\u2605'.repeat(sp.reputation) + '\u2606'.repeat(5 - sp.reputation);
            html += '<a href="#" class="similar-card" onclick="showDetail(' + sp.id + '); return false;">';
            html += '<strong>' + escHtml(sp.hospital) + '</strong>';
            html += '<span class="stars" style="font-size:0.65rem">' + spStars + '</span>';
            html += '<span style="font-size:0.7rem;color:#6b7280">' + escHtml(sp.region) + '</span>';
            html += '</a>';
        }});
        html += '</div></div>';
    }}

    // Activity log
    var actLog = getActivityLog(id);
    if (actLog.length > 0) {{
        html += '<div class="detail-section"><h3>Activity Log</h3>';
        html += '<div class="activity-log">';
        actLog.slice(0, 10).forEach(function(entry) {{
            var d = new Date(entry.time);
            var timeStr = d.toLocaleDateString('en-US', {{month:'short',day:'numeric'}}) + ' ' + d.toLocaleTimeString('en-US', {{hour:'numeric',minute:'2-digit'}});
            html += '<div class="activity-entry">';
            html += '<span class="activity-dot"></span>';
            html += '<span class="activity-text">' + escHtml(entry.action) + '</span>';
            html += '<span class="activity-time">' + timeStr + '</span>';
            html += '</div>';
        }});
        html += '</div></div>';
    }}

    if (p.application_url) {{
        html += '<div class="detail-actions"><a href="' + escHtml(p.application_url) + '" target="_blank" class="apply-btn-modal">Apply Now &rarr;</a></div>';
    }}

    // Prev/Next navigation
    var visibleIds = getVisibleProgramIds();
    var currentIdx = visibleIds.indexOf(id);
    var prevId = currentIdx > 0 ? visibleIds[currentIdx - 1] : null;
    var nextId = currentIdx < visibleIds.length - 1 ? visibleIds[currentIdx + 1] : null;
    html += '<div class="modal-nav">';
    html += '<button onclick="showDetail(' + (prevId || 0) + ')"' + (prevId ? '' : ' disabled') + '>&larr; Previous</button>';
    html += '<span style="color:#9ca3af;font-size:0.75rem">' + (currentIdx + 1) + ' of ' + visibleIds.length + '</span>';
    html += '<button onclick="showDetail(' + (nextId || 0) + ')"' + (nextId ? '' : ' disabled') + '>Next &rarr;</button>';
    html += '</div>';

    document.getElementById('modal-body').innerHTML = html;
    openModal('detail-modal');
    history.replaceState(null, '', '#program-' + id);
    trackRecentView(id);

    // Auto-save notes on input
    var notesArea = document.getElementById('modal-notes');
    if (notesArea) {{
        var saveTimer;
        notesArea.addEventListener('input', function() {{
            clearTimeout(saveTimer);
            saveTimer = setTimeout(function() {{
                saveNote(p.id, notesArea.value);
            }}, 500);
        }});
    }}

    // Modal status change handler
    var modalStatusSel = document.getElementById('modal-status');
    if (modalStatusSel) {{
        modalStatusSel.addEventListener('change', function() {{
            var newStatus = this.value;
            var progId = parseInt(this.dataset.id);
            // Save to localStorage
            saveStatus(progId, newStatus);
            // Update table row
            var row = document.querySelector('tr[data-id="' + progId + '"]');
            if (row) {{
                applyRowStatus(row, newStatus);
                row.dataset.status = newStatus;
                var tableSel = row.querySelector('.status-select');
                if (tableSel) tableSel.value = newStatus;
            }}
            // Update modal select styling
            Object.values(selectStatusClasses).forEach(function(c) {{ modalStatusSel.classList.remove(c); }});
            if (selectStatusClasses[newStatus]) modalStatusSel.classList.add(selectStatusClasses[newStatus]);
            renderStatusSummary();
            if (newStatus === 'Offer') {{
                showToast('Congratulations! 🎉');
                launchConfetti();
            }} else {{
                showToast('Status updated');
            }}
        }});
    }}

    // Checklist change handler
    var checklist = document.getElementById('modal-checklist');
    if (checklist) {{
        checklist.addEventListener('change', function(e) {{
            if (e.target.type === 'checkbox') {{
                var idx = parseInt(e.target.dataset.idx);
                var span = e.target.nextElementSibling;
                if (e.target.checked) {{
                    span.classList.add('checked-label');
                    addChecklistItem(p.id, idx);
                }} else {{
                    span.classList.remove('checked-label');
                    removeChecklistItem(p.id, idx);
                }}
                var allCbs = checklist.querySelectorAll('input[type="checkbox"]');
                var checkedCount = checklist.querySelectorAll('input[type="checkbox"]:checked').length;
                var pctDone = Math.round(checkedCount / allCbs.length * 100);
                var progDiv = checklist.parentElement.querySelector('.checklist-progress');
                if (progDiv) progDiv.textContent = checkedCount + ' of ' + allCbs.length + ' complete (' + pctDone + '%)';
                var progBar = checklist.parentElement.querySelector('.checklist-progress-fill');
                if (progBar) progBar.style.width = pctDone + '%';
            }}
        }});
    }}
}}

function openModal(id) {{
    var el = document.getElementById(id);
    el.style.display = 'flex';
    // Force reflow then add class for animation
    el.offsetHeight;
    el.classList.add('modal-visible');
    document.body.style.overflow = 'hidden';
    // Focus first focusable element
    setTimeout(function() {{
        var focusable = el.querySelector('button, [href], input, select, textarea');
        if (focusable) focusable.focus();
    }}, 100);
}}

function closeModalEl(el) {{
    el.classList.remove('modal-visible');
    document.body.style.overflow = '';
    setTimeout(function() {{ el.style.display = 'none'; }}, 200);
}}

// Urgency banner
function renderUrgencyBanner() {{
    var banner = document.getElementById('urgency-banner');
    if (!banner) return;
    var today = new Date(); today.setHours(0,0,0,0);
    var savedStatuses = loadSavedStatuses();
    var urgent = [];
    var opening = [];

    PROGRAMS.forEach(function(p) {{
        var status = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (status === 'Submitted' || status === 'Interview' || status === 'Offer' || status === 'Rejected') return;

        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        if (!closeD) return;

        var daysLeft = Math.ceil((closeD - today) / (1000 * 60 * 60 * 24));

        if (openD && openD <= today && closeD >= today) {{
            if (daysLeft <= 7) {{
                urgent.push({{ prog: p, days: daysLeft, type: 'closing' }});
            }}
        }}

        // Opening soon
        if (openD && openD > today) {{
            var daysUntilOpen = Math.ceil((openD - today) / (1000 * 60 * 60 * 24));
            if (daysUntilOpen <= 3) {{
                opening.push({{ prog: p, days: daysUntilOpen, type: 'opening' }});
            }}
        }}
    }});

    if (urgent.length === 0 && opening.length === 0) {{
        banner.style.display = 'none';
        return;
    }}

    var html = '';
    urgent.sort(function(a, b) {{ return a.days - b.days; }});
    opening.sort(function(a, b) {{ return a.days - b.days; }});

    if (urgent.length > 0) {{
        html += '<div class="urgency-section urgency-critical">';
        html += '<strong>&#9888; Closing Soon:</strong> ';
        html += urgent.map(function(u) {{
            return '<a href="#" onclick="showDetail(' + u.prog.id + '); return false;">' + escHtml(u.prog.hospital) + '</a> <span class="urgency-days">' + u.days + 'd</span>';
        }}).join(' &bull; ');
        html += '</div>';
    }}

    if (opening.length > 0) {{
        html += '<div class="urgency-section urgency-opening">';
        html += '<strong>&#128276; Opening Soon:</strong> ';
        html += opening.map(function(o) {{
            return '<a href="#" onclick="showDetail(' + o.prog.id + '); return false;">' + escHtml(o.prog.hospital) + '</a> <span class="urgency-days">in ' + o.days + 'd</span>';
        }}).join(' &bull; ');
        html += '</div>';
    }}

    banner.innerHTML = html;
    banner.style.display = '';
}}

// Notifications panel
function buildNotifications() {{
    var notifs = [];
    var today = new Date(); today.setHours(0,0,0,0);
    var savedStatuses = loadSavedStatuses();

    PROGRAMS.forEach(function(p) {{
        var status = savedStatuses[p.id] || p.application_status || 'Not Started';
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        var cohortD = parseDate(p.cohort_start_date);

        // Closing within 7 days
        if (closeD && status !== 'Submitted' && status !== 'Interview' && status !== 'Offer' && status !== 'Rejected') {{
            var daysLeft = Math.ceil((closeD - today) / (1000*60*60*24));
            if (daysLeft >= 0 && daysLeft <= 7) {{
                notifs.push({{ id: p.id, type: 'urgent', icon: '\\u26A0\\uFE0F', text: escHtml(p.hospital) + ' closes in ' + daysLeft + ' day' + (daysLeft !== 1 ? 's' : ''), sort: daysLeft }});
            }}
        }}

        // Opening within 7 days
        if (openD && status === 'Not Started') {{
            var daysUntil = Math.ceil((openD - today) / (1000*60*60*24));
            if (daysUntil > 0 && daysUntil <= 7) {{
                notifs.push({{ id: p.id, type: 'opening', icon: '\\uD83D\\uDD14', text: escHtml(p.hospital) + ' opens in ' + daysUntil + ' day' + (daysUntil !== 1 ? 's' : ''), sort: 10 + daysUntil }});
            }}
        }}

        // Currently open + not started
        if (openD && closeD && openD <= today && closeD >= today && status === 'Not Started') {{
            notifs.push({{ id: p.id, type: 'action', icon: '\\uD83D\\uDCCB', text: escHtml(p.hospital) + ' is OPEN — apply now!', sort: 5 }});
        }}

        // Submitted > 14 days ago — follow up reminder
        if (status === 'Submitted') {{
            var log = getActivityLog(p.id);
            var submitEntry = log.find(function(e) {{ return e.action.indexOf('Submitted') !== -1; }});
            if (submitEntry) {{
                var submitDate = new Date(submitEntry.time);
                var daysSince = Math.ceil((today - submitDate) / (1000*60*60*24));
                if (daysSince >= 14) {{
                    notifs.push({{ id: p.id, type: 'followup', icon: '\\uD83D\\uDCE7', text: escHtml(p.hospital) + ' — submitted ' + daysSince + ' days ago, follow up?', sort: 20 }});
                }}
            }}
        }}

        // Interview scheduled — get ready
        if (status === 'Interview') {{
            notifs.push({{ id: p.id, type: 'interview', icon: '\\uD83C\\uDFAF', text: escHtml(p.hospital) + ' — interview prep!', sort: 3 }});
        }}

        // Cohort starts within 60 days
        if (cohortD) {{
            var daysToCohort = Math.ceil((cohortD - today) / (1000*60*60*24));
            if (daysToCohort > 0 && daysToCohort <= 60 && (status === 'Offer')) {{
                notifs.push({{ id: p.id, type: 'cohort', icon: '\\uD83C\\uDF93', text: escHtml(p.hospital) + ' cohort starts in ' + daysToCohort + ' days', sort: 30 }});
            }}
        }}
    }});

    notifs.sort(function(a, b) {{ return a.sort - b.sort; }});
    return notifs;
}}

function renderNotifications() {{
    var notifs = buildNotifications();
    var dismissed = [];
    try {{ dismissed = JSON.parse(localStorage.getItem('rn_tracker_notif_dismissed') || '[]'); }} catch(e) {{}}
    notifs = notifs.filter(function(n) {{ return dismissed.indexOf(n.id + ':' + n.type) === -1; }});

    var countEl = document.getElementById('notif-count');
    if (countEl) {{
        if (notifs.length > 0) {{
            countEl.textContent = notifs.length;
            countEl.style.display = '';
        }} else {{
            countEl.style.display = 'none';
        }}
    }}

    var list = document.getElementById('notif-list');
    if (!list) return;
    if (notifs.length === 0) {{
        list.innerHTML = '<div class="notif-empty">All clear! No notifications.</div>';
        return;
    }}
    var html = '';
    notifs.forEach(function(n) {{
        html += '<div class="notif-item notif-' + n.type + '">';
        html += '<span class="notif-icon">' + n.icon + '</span>';
        html += '<a href="#" class="notif-text" onclick="showDetail(' + n.id + '); toggleNotifications(); return false;">' + n.text + '</a>';
        html += '<button class="notif-dismiss" onclick="dismissNotification(' + n.id + ', \\\'' + n.type + '\\\')" title="Dismiss">&times;</button>';
        html += '</div>';
    }});
    list.innerHTML = html;
}}

function toggleNotifications() {{
    var panel = document.getElementById('notif-panel');
    if (!panel) return;
    if (panel.style.display === 'none') {{
        renderNotifications();
        panel.style.display = '';
    }} else {{
        panel.style.display = 'none';
    }}
}}

function dismissNotification(id, type) {{
    try {{
        var dismissed = JSON.parse(localStorage.getItem('rn_tracker_notif_dismissed') || '[]');
        var key = id + ':' + type;
        if (dismissed.indexOf(key) === -1) dismissed.push(key);
        localStorage.setItem('rn_tracker_notif_dismissed', JSON.stringify(dismissed));
        renderNotifications();
    }} catch(e) {{}}
}}

function clearNotifications() {{
    var notifs = buildNotifications();
    var dismissed = [];
    try {{ dismissed = JSON.parse(localStorage.getItem('rn_tracker_notif_dismissed') || '[]'); }} catch(e) {{}}
    notifs.forEach(function(n) {{
        var key = n.id + ':' + n.type;
        if (dismissed.indexOf(key) === -1) dismissed.push(key);
    }});
    localStorage.setItem('rn_tracker_notif_dismissed', JSON.stringify(dismissed));
    renderNotifications();
}}

// Recently viewed
function trackRecentView(id) {{
    try {{
        var recent = JSON.parse(localStorage.getItem('rn_tracker_recent') || '[]');
        recent = recent.filter(function(r) {{ return r !== id; }});
        recent.unshift(id);
        if (recent.length > 5) recent = recent.slice(0, 5);
        localStorage.setItem('rn_tracker_recent', JSON.stringify(recent));
        renderRecentViewed();
    }} catch(e) {{}}
}}

function renderRecentViewed() {{
    var container = document.getElementById('recent-viewed');
    if (!container) return;
    try {{
        var recent = JSON.parse(localStorage.getItem('rn_tracker_recent') || '[]');
        if (recent.length === 0) {{
            container.style.display = 'none';
            return;
        }}
        container.style.display = '';
        var html = '<span class="recent-label">Recent:</span>';
        recent.forEach(function(id) {{
            var p = PROGRAMS.find(function(prog) {{ return prog.id === id; }});
            if (p) {{
                html += '<a href="#" class="recent-item" onclick="showDetail(' + p.id + '); return false;">' + escHtml(p.hospital) + '</a>';
            }}
        }});
        container.innerHTML = html;
    }} catch(e) {{}}
}}

// View toggle
function showView(view) {{
    var tableView = document.querySelector('.sheet-page');
    var pipelineView = document.getElementById('pipeline-view');
    var cardsView = document.getElementById('cards-view');
    var navTable = document.getElementById('nav-table');
    var navPipeline = document.getElementById('nav-pipeline');
    var navCards = document.getElementById('nav-cards');

    var calendarView = document.getElementById('calendar-view');
    var statsView = document.getElementById('stats-view');
    var timelineView = document.getElementById('timeline-view');
    var navCalendar = document.getElementById('nav-calendar');
    var navStats = document.getElementById('nav-stats');
    var navTimeline = document.getElementById('nav-timeline');

    // Hide all
    var allViews = [tableView, pipelineView, cardsView, calendarView, statsView, timelineView];
    allViews.forEach(function(v) {{ if (v) {{ v.style.display = 'none'; v.classList.remove('view-enter'); }} }});
    [navTable, navPipeline, navCards, navCalendar, navStats, navTimeline].forEach(function(n) {{ if (n) n.classList.remove('active'); }});

    var target = null;
    if (view === 'cards') {{
        target = cardsView; navCards.classList.add('active'); renderCards();
    }} else if (view === 'pipeline') {{
        target = pipelineView; navPipeline.classList.add('active'); renderPipeline();
    }} else if (view === 'calendar') {{
        target = calendarView; navCalendar.classList.add('active'); renderCalendar();
    }} else if (view === 'timeline') {{
        target = timelineView; navTimeline.classList.add('active'); renderTimeline();
    }} else if (view === 'stats') {{
        target = statsView; navStats.classList.add('active'); renderStats();
    }} else {{
        target = tableView; navTable.classList.add('active');
    }}
    if (target) {{
        target.style.display = (target === tableView) ? '' : 'block';
        requestAnimationFrame(function() {{ target.classList.add('view-enter'); }});
    }}
    // Update mobile bottom nav
    document.querySelectorAll('.mnav-btn').forEach(function(btn) {{
        btn.classList.toggle('mnav-active', btn.dataset.view === view);
    }});
    window._currentView = view;
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
    announce('Switched to ' + view + ' view');
}}

// Pipeline drag and drop
function onPipelineDragStart(e) {{
    e.dataTransfer.setData('text/plain', e.target.dataset.progId);
    e.target.classList.add('pipeline-dragging');
    // Highlight all drop targets
    document.querySelectorAll('.pipeline-col-body').forEach(function(col) {{
        col.classList.add('pipeline-drop-target');
    }});
}}

function onPipelineDragEnd(e) {{
    e.target.classList.remove('pipeline-dragging');
    document.querySelectorAll('.pipeline-col-body').forEach(function(col) {{
        col.classList.remove('pipeline-drop-target');
        col.classList.remove('pipeline-drop-hover');
    }});
}}

function onPipelineDragOver(e) {{
    e.preventDefault();
    e.currentTarget.classList.add('pipeline-drop-hover');
}}

function onPipelineDragLeave(e) {{
    e.currentTarget.classList.remove('pipeline-drop-hover');
}}

function onPipelineDrop(e) {{
    e.preventDefault();
    var progId = parseInt(e.dataTransfer.getData('text/plain'));
    var newStatus = e.currentTarget.dataset.status;
    if (!progId || !newStatus) return;

    // Update status
    saveStatus(progId, newStatus);

    // Update table row if it exists
    var row = document.querySelector('tr[data-id="' + progId + '"]');
    if (row) {{
        applyRowStatus(row, newStatus);
        row.dataset.status = newStatus;
        var sel = row.querySelector('.status-select');
        if (sel) sel.value = newStatus;
    }}

    renderStatusSummary();
    renderNotifications();
    renderPipeline();
    showToast('Moved to ' + newStatus);
}}

function renderCards() {{
    var grid = document.getElementById('cards-grid');
    if (!grid) return;
    var savedStatuses = loadSavedStatuses();
    var savedNotes = loadSavedNotes();
    var favs = loadFavorites();
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var searchVal = (document.getElementById('cards-search') || {{}}).value || '';
    var regionVal = (document.getElementById('cards-region-filter') || {{}}).value || '';
    var sortVal = (document.getElementById('cards-sort') || {{}}).value || 'deadline';

    var progs = PROGRAMS.filter(function(p) {{
        if (searchVal && (p.hospital + ' ' + p.program_name + ' ' + p.region).toLowerCase().indexOf(searchVal.toLowerCase()) === -1) return false;
        if (regionVal && p.region !== regionVal) return false;
        return true;
    }});

    // Sort
    progs.sort(function(a, b) {{
        if (sortVal === 'reputation') return (b.reputation || 0) - (a.reputation || 0);
        if (sortVal === 'pay') {{
            var ap = parsePay(a.pay_range || ''), bp = parsePay(b.pay_range || '');
            return (bp || 0) - (ap || 0);
        }}
        if (sortVal === 'smart') {{
            return computeSmartScore(b, savedStatuses, today) - computeSmartScore(a, savedStatuses, today);
        }}
        // Default: deadline
        var ad = parseDate(a.app_close_date), bd = parseDate(b.app_close_date);
        if (!ad && !bd) return 0;
        if (!ad) return 1;
        if (!bd) return -1;
        return ad - bd;
    }});

    var html = '';
    progs.forEach(function(p) {{
        var st = savedStatuses[p.id] || p.application_status || 'Not Started';
        var stCls = st.toLowerCase().replace(/\\s+/g, '-');
        var stars = '';
        for (var i = 0; i < 5; i++) stars += i < (p.reputation || 0) ? '\\u2605' : '\\u2606';
        var isFav = favs.indexOf(p.id) !== -1;
        var note = savedNotes[p.id] || '';
        var tags = loadTags(p.id);

        var deadlineInfo = '';
        var closeDate = parseDate(p.app_close_date);
        if (closeDate) {{
            var daysLeft = Math.ceil((closeDate - today) / (1000 * 60 * 60 * 24));
            if (daysLeft < 0) deadlineInfo = '<span class="card-badge card-badge-closed">Closed</span>';
            else if (daysLeft <= 3) deadlineInfo = '<span class="card-badge card-badge-urgent">' + daysLeft + 'd left</span>';
            else if (daysLeft <= 7) deadlineInfo = '<span class="card-badge card-badge-warning">' + daysLeft + 'd left</span>';
            else if (daysLeft <= 30) deadlineInfo = '<span class="card-badge card-badge-soon">' + daysLeft + 'd</span>';
        }}
        var openDate = parseDate(p.app_open_date);
        if (openDate && closeDate && openDate <= today && closeDate >= today) {{
            deadlineInfo = '<span class="card-badge card-badge-open">OPEN NOW</span>';
        }}

        html += '<div class="prog-card prog-card-' + stCls + '" tabindex="0" role="button" aria-label="' + escHtml(p.hospital) + '" onclick="showDetail(' + p.id + ')" onkeydown="if(event.key===\'Enter\')showDetail(' + p.id + ')">';
        html += '<div class="prog-card-header">';
        html += '<select class="card-status-select card-st-' + stCls + '" data-id="' + p.id + '" onchange="updateCardStatus(this); event.stopPropagation();" onclick="event.stopPropagation()">';
        ['Not Started','In Progress','Submitted','Interview','Offer','Rejected'].forEach(function(opt) {{
            html += '<option value="' + opt + '"' + (opt === st ? ' selected' : '') + '>' + opt + '</option>';
        }});
        html += '</select>';
        if (isFav) html += '<span class="prog-card-fav">\\u2605</span>';
        html += '</div>';
        html += '<h3 class="prog-card-name">' + p.hospital + '</h3>';
        html += '<div class="prog-card-program">' + (p.program_name || '') + '</div>';
        html += '<div class="prog-card-meta">';
        html += '<span class="prog-card-stars">' + stars + '</span>';
        html += '<span class="prog-card-region">' + p.region + '</span>';
        html += '</div>';
        if (p.pay_range) html += '<div class="prog-card-pay">' + p.pay_range + '</div>';
        html += '<div class="prog-card-dates">';
        if (p.app_open_date) html += '<span>Open: ' + p.app_open_date + '</span>';
        if (p.app_close_date) html += '<span>Close: ' + p.app_close_date + '</span>';
        html += '</div>';
        if (deadlineInfo) html += '<div class="prog-card-deadline">' + deadlineInfo + '</div>';
        if (tags.length) {{
            html += '<div class="prog-card-tags">';
            tags.forEach(function(t) {{ html += '<span class="prog-card-tag">' + t + '</span>'; }});
            html += '</div>';
        }}
        if (note) html += '<div class="prog-card-note">' + note.substring(0, 80) + (note.length > 80 ? '...' : '') + '</div>';
        if (p.application_url) html += '<a href="' + p.application_url + '" target="_blank" class="prog-card-apply" onclick="event.stopPropagation()">Apply &rarr;</a>';
        html += '</div>';
    }});

    grid.innerHTML = html;
}}

function updateCardStatus(sel) {{
    var id = sel.dataset.id;
    var newStatus = sel.value;
    saveStatus(id, newStatus);
    logActivity(parseInt(id), 'Status changed to ' + newStatus);
    renderStatusSummary();
    updateTableFooter();
    // Update table row if it exists
    var tableRow = document.querySelector('.sheet tbody tr[data-id="' + id + '"]');
    if (tableRow) {{
        var tableSel = tableRow.querySelector('.status-select');
        if (tableSel) tableSel.value = newStatus;
        applyRowStatus(tableRow, newStatus);
        tableRow.dataset.status = newStatus;
    }}
    showToast('Status: ' + newStatus);
    if (newStatus === 'Offer') launchConfetti();
}}

// Cards view filter listeners
(function() {{
    var s = document.getElementById('cards-search');
    if (s) s.addEventListener('input', debounce(renderCards, 200));
    var r = document.getElementById('cards-region-filter');
    if (r) r.addEventListener('change', renderCards);
}})();

function renderPipeline() {{
    var savedStatuses = loadSavedStatuses();
    var columns = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer', 'Rejected'];
    var grouped = {{}};
    columns.forEach(function(c) {{ grouped[c] = []; }});

    var pSearch = (document.getElementById('pipeline-search') || {{}}).value || '';
    var pRegion = (document.getElementById('pipeline-region-filter') || {{}}).value || '';
    pSearch = pSearch.toLowerCase().trim();

    PROGRAMS.forEach(function(p) {{
        // Apply filters
        if (pSearch && (p.hospital + ' ' + p.program_name + ' ' + p.region).toLowerCase().indexOf(pSearch) === -1) return;
        if (pRegion && p.region !== pRegion) return;
        var status = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (!grouped[status]) grouped[status] = [];
        grouped[status].push(p);
    }});

    var favs = loadFavorites();

    var html = '';
    columns.forEach(function(col) {{
        var items = grouped[col];
        var colClass = col.toLowerCase().replace(/ /g, '-');
        html += '<div class="pipeline-col">';
        html += '<div class="pipeline-col-header pipeline-header-' + colClass + '">';
        html += '<span>' + col + '</span>';
        html += '<span class="pipeline-count">' + items.length + '</span>';
        html += '</div>';
        html += '<div class="pipeline-col-body" data-status="' + col + '" ondragover="onPipelineDragOver(event)" ondrop="onPipelineDrop(event)" ondragleave="onPipelineDragLeave(event)">';
        items.forEach(function(p) {{
            var isFav = favs.indexOf(p.id) !== -1;
            var stars = '\u2605'.repeat(p.reputation) + '\u2606'.repeat(5 - p.reputation);
            var deadlineHtml = '';
            var today = new Date(); today.setHours(0,0,0,0);
            var closeDate = parseDate(p.app_close_date);
            var openDate = parseDate(p.app_open_date);
            if (openDate && closeDate) {{
                if (closeDate < today) {{
                    deadlineHtml = '<span class="deadline-past">closed</span>';
                }} else if (openDate <= today && closeDate >= today) {{
                    var dLeft = Math.ceil((closeDate - today) / (1000*60*60*24));
                    deadlineHtml = '<span class="badge-open">OPEN</span> <span class="deadline-soon">' + dLeft + 'd</span>';
                }} else {{
                    var dUntil = Math.ceil((openDate - today) / (1000*60*60*24));
                    deadlineHtml = '<span class="deadline-soon">in ' + dUntil + 'd</span>';
                }}
            }}
            html += '<div class="pipeline-card' + (isFav ? ' pipeline-fav' : '') + '" draggable="true" data-prog-id="' + p.id + '" ondragstart="onPipelineDragStart(event)" ondragend="onPipelineDragEnd(event)" onclick="showDetail(' + p.id + ')">';
            html += '<div class="pipeline-card-title">' + (isFav ? '<span class="fav-star">\u2605</span> ' : '') + escHtml(p.hospital) + '</div>';
            html += '<div class="pipeline-card-meta">';
            html += '<span class="stars" style="font-size:0.65rem">' + stars + '</span>';
            if (p.pay_range) {{
                var payM = p.pay_range.match(/(\\$[\\d.,]+\\/hr)/);
                if (payM) html += ' <span style="color:#6b7280;font-size:0.7rem">' + payM[1] + '</span>';
            }}
            html += '</div>';
            if (deadlineHtml) html += '<div class="pipeline-card-deadline">' + deadlineHtml + '</div>';
            html += '<div class="pipeline-card-region" style="font-size:0.68rem;color:#9ca3af">' + escHtml(p.region) + '</div>';
            html += '</div>';
        }});
        if (items.length === 0) {{
            html += '<div class="pipeline-empty">';
            if (col === 'Offer') html += '<div style="font-size:1.5rem;margin-bottom:4px">🎯</div>';
            else if (col === 'Submitted') html += '<div style="font-size:1.5rem;margin-bottom:4px">📮</div>';
            else if (col === 'Interview') html += '<div style="font-size:1.5rem;margin-bottom:4px">🎤</div>';
            html += 'No programs</div>';
        }}
        html += '</div></div>';
    }});

    document.getElementById('pipeline-container').innerHTML = html;
}}

// Stats view
function renderStats() {{
    var savedStatuses = loadSavedStatuses();
    var favs = loadFavorites();
    var today = new Date(); today.setHours(0,0,0,0);

    // Status counts
    var statusCounts = {{}};
    ['Not Started','In Progress','Submitted','Interview','Offer','Rejected'].forEach(function(s) {{ statusCounts[s] = 0; }});
    PROGRAMS.forEach(function(p) {{
        var s = savedStatuses[p.id] || p.application_status || 'Not Started';
        statusCounts[s] = (statusCounts[s] || 0) + 1;
    }});

    // Region counts
    var regionCounts = {{}};
    PROGRAMS.forEach(function(p) {{ regionCounts[p.region] = (regionCounts[p.region] || 0) + 1; }});

    // BSN counts
    var bsnCounts = {{}};
    PROGRAMS.forEach(function(p) {{ bsnCounts[p.bsn_required || 'Unknown'] = (bsnCounts[p.bsn_required || 'Unknown'] || 0) + 1; }});

    // Pay distribution
    var payBuckets = {{ 'Under $50/hr': 0, '$50-60/hr': 0, '$60-70/hr': 0, '$70-80/hr': 0, '$80+/hr': 0, 'Unknown': 0 }};
    PROGRAMS.forEach(function(p) {{
        var m = (p.pay_range || '').match(/(\\d[\\d.,]+)\\/hr/);
        if (m) {{
            var val = parseFloat(m[1].replace(',', ''));
            if (val < 50) payBuckets['Under $50/hr']++;
            else if (val < 60) payBuckets['$50-60/hr']++;
            else if (val < 70) payBuckets['$60-70/hr']++;
            else if (val < 80) payBuckets['$70-80/hr']++;
            else payBuckets['$80+/hr']++;
        }} else {{
            payBuckets['Unknown']++;
        }}
    }});

    // Deadline timeline
    var openNow = 0, upcoming30 = 0, future = 0, closed = 0, tbd = 0;
    PROGRAMS.forEach(function(p) {{
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        if (!openD || !closeD) {{ tbd++; return; }}
        if (closeD < today) {{ closed++; }}
        else if (openD <= today && closeD >= today) {{ openNow++; }}
        else if (closeD.getTime() - today.getTime() <= 30 * 86400000) {{ upcoming30++; }}
        else {{ future++; }}
    }});

    // Reputation distribution
    var repCounts = {{1:0, 2:0, 3:0, 4:0, 5:0}};
    PROGRAMS.forEach(function(p) {{ repCounts[p.reputation || 1] = (repCounts[p.reputation || 1] || 0) + 1; }});

    var total = PROGRAMS.length;

    function barChart(title, data, colors) {{
        var maxVal = Math.max.apply(null, Object.values(data));
        var html = '<div class="stats-card"><h3>' + title + '</h3>';
        Object.keys(data).forEach(function(key) {{
            var val = data[key];
            var pct = maxVal > 0 ? Math.round(val / maxVal * 100) : 0;
            var color = colors ? (colors[key] || '#3b82f6') : '#3b82f6';
            html += '<div class="stats-bar-row">';
            html += '<span class="stats-bar-label">' + key + '</span>';
            html += '<div class="stats-bar-track"><div class="stats-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>';
            html += '<span class="stats-bar-value">' + val + '</span>';
            html += '</div>';
        }});
        html += '</div>';
        return html;
    }}

    var statusColors = {{
        'Not Started': '#9ca3af', 'In Progress': '#f59e0b', 'Submitted': '#3b82f6',
        'Interview': '#8b5cf6', 'Offer': '#22c55e', 'Rejected': '#ef4444'
    }};

    var regionColors = {{}};
    Object.keys(regionCounts).forEach(function(r) {{
        if (r.indexOf('Bay') !== -1) regionColors[r] = '#3b82f6';
        else if (r.indexOf('SoCal') !== -1 || r.indexOf('LA') !== -1 || r.indexOf('Orange') !== -1 || r.indexOf('Diego') !== -1) regionColors[r] = '#f59e0b';
        else if (r.indexOf('Central') !== -1) regionColors[r] = '#22c55e';
        else if (r.indexOf('Sacr') !== -1 || r.indexOf('NorCal') !== -1) regionColors[r] = '#8b5cf6';
        else if (r.indexOf('Inland') !== -1) regionColors[r] = '#ef4444';
        else regionColors[r] = '#6b7280';
    }});

    var bsnColors = {{ 'No': '#22c55e', 'Preferred': '#f59e0b', 'Yes': '#ef4444', 'Unknown': '#9ca3af' }};
    var payColors = {{ 'Under $50/hr': '#ef4444', '$50-60/hr': '#f59e0b', '$60-70/hr': '#3b82f6', '$70-80/hr': '#8b5cf6', '$80+/hr': '#22c55e', 'Unknown': '#9ca3af' }};

    // Weekly digest
    var weekStart = new Date(today);
    weekStart.setDate(weekStart.getDate() - weekStart.getDay()); // Sunday
    var weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    var nextWeekEnd = new Date(weekEnd);
    nextWeekEnd.setDate(nextWeekEnd.getDate() + 7);

    var closingThisWeek = [];
    var openingThisWeek = [];
    var closingNextWeek = [];
    var openingNextWeek = [];

    PROGRAMS.forEach(function(p) {{
        var s = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (s === 'Rejected' || s === 'Offer') return;
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        if (closeD && closeD >= weekStart && closeD <= weekEnd) closingThisWeek.push(p);
        if (openD && openD >= weekStart && openD <= weekEnd) openingThisWeek.push(p);
        if (closeD && closeD > weekEnd && closeD <= nextWeekEnd) closingNextWeek.push(p);
        if (openD && openD > weekEnd && openD <= nextWeekEnd) openingNextWeek.push(p);
    }});

    var recentLog = getActivityLog().filter(function(e) {{
        var t = new Date(e.time);
        return t >= weekStart;
    }});

    var html = '';
    if (closingThisWeek.length > 0 || openingThisWeek.length > 0 || closingNextWeek.length > 0 || recentLog.length > 0) {{
        html += '<div class="weekly-digest">';
        html += '<h3>This Week\'s Digest</h3>';
        html += '<div class="digest-grid">';

        if (closingThisWeek.length > 0) {{
            html += '<div class="digest-card digest-urgent"><span class="digest-icon">\\u26A0\\uFE0F</span><div><strong>Closing This Week</strong>';
            closingThisWeek.forEach(function(p) {{
                var cd = parseDate(p.app_close_date);
                var dleft = cd ? Math.ceil((cd - today) / (1000*60*60*24)) : 0;
                html += '<div><a href="#" onclick="showDetail(' + p.id + '); return false;">' + escHtml(p.hospital) + '</a> <small>(' + dleft + 'd)</small></div>';
            }});
            html += '</div></div>';
        }}

        if (openingThisWeek.length > 0) {{
            html += '<div class="digest-card digest-opening"><span class="digest-icon">\\uD83D\\uDCC5</span><div><strong>Opening This Week</strong>';
            openingThisWeek.forEach(function(p) {{
                html += '<div><a href="#" onclick="showDetail(' + p.id + '); return false;">' + escHtml(p.hospital) + '</a></div>';
            }});
            html += '</div></div>';
        }}

        if (closingNextWeek.length > 0) {{
            html += '<div class="digest-card digest-upcoming"><span class="digest-icon">\\uD83D\\uDD52</span><div><strong>Closing Next Week</strong>';
            closingNextWeek.forEach(function(p) {{
                html += '<div><a href="#" onclick="showDetail(' + p.id + '); return false;">' + escHtml(p.hospital) + '</a></div>';
            }});
            html += '</div></div>';
        }}

        if (recentLog.length > 0) {{
            html += '<div class="digest-card digest-activity"><span class="digest-icon">\\uD83D\\uDCDD</span><div><strong>Your Activity (' + recentLog.length + ')</strong>';
            recentLog.slice(0, 3).forEach(function(e) {{
                var prog = PROGRAMS.find(function(p) {{ return p.id === e.id; }});
                html += '<div>' + (prog ? escHtml(prog.hospital) : 'Unknown') + ': ' + escHtml(e.action) + '</div>';
            }});
            if (recentLog.length > 3) html += '<div style="color:#9ca3af">+' + (recentLog.length - 3) + ' more</div>';
            html += '</div></div>';
        }}

        html += '</div></div>';
    }}

    html += '<div class="stats-header">';
    html += '<h2>Program Analytics</h2>';
    html += '<div class="stats-summary-cards">';
    html += '<div class="stats-num-card"><span class="stats-big-num">' + total + '</span><span>Total Programs</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num stat-green">' + openNow + '</span><span>Open Now</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num" style="color:#f59e0b">' + upcoming30 + '</span><span>Closing in 30d</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num" style="color:#8b5cf6">' + favs.length + '</span><span>Favorites</span></div>';
    html += '</div>';

    // Goal tracker
    var goalTarget = parseInt(localStorage.getItem('rn_tracker_goal') || '10');
    var applied = (statusCounts['Submitted'] || 0) + (statusCounts['Interview'] || 0) + (statusCounts['Offer'] || 0);
    var goalPct = Math.min(Math.round(applied / goalTarget * 100), 100);
    html += '<div class="goal-widget">';
    html += '<div class="goal-header">';
    html += '<span class="goal-title">Application Goal</span>';
    html += '<button class="goal-edit-btn" onclick="editGoal()">Edit</button>';
    html += '</div>';
    html += '<div class="goal-bar-wrap">';
    html += '<div class="goal-bar"><div class="goal-fill" style="width:' + goalPct + '%"></div></div>';
    html += '<span class="goal-text">' + applied + ' / ' + goalTarget + ' applied (' + goalPct + '%)</span>';
    html += '</div>';
    html += '</div>';

    html += '</div>';

    // Top recommendations
    var recScores = [];
    PROGRAMS.forEach(function(p) {{
        var s = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (s === 'Offer' || s === 'Rejected') return;
        var score = 0;
        // Reputation weight (0-25)
        score += (p.reputation || 1) * 5;
        // Pay weight (0-20)
        var payMatch = (p.pay_range || '').match(/(\\d[\\d.,]+)\\/hr/);
        if (payMatch) {{
            var payVal = parseFloat(payMatch[1].replace(',', ''));
            score += Math.min(payVal / 5, 20);
        }}
        // Deadline proximity bonus (0-20) — closer = more urgent = higher score
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        if (openD && closeD && openD <= today && closeD >= today) {{
            var daysLeft = Math.ceil((closeD - today) / (1000*60*60*24));
            score += Math.max(20 - daysLeft, 5);
        }} else if (openD && openD > today) {{
            var daysUntil = Math.ceil((openD - today) / (1000*60*60*24));
            if (daysUntil <= 30) score += 10;
        }}
        // BSN bonus (no BSN = more accessible)
        if (p.bsn_required === 'No') score += 5;
        // Has apply URL
        if (p.application_url) score += 3;
        // Not yet started penalty
        if (s === 'In Progress' || s === 'Submitted') score += 5;
        recScores.push({{ prog: p, score: score, status: s }});
    }});
    recScores.sort(function(a, b) {{ return b.score - a.score; }});
    var topRecs = recScores.slice(0, 5);
    if (topRecs.length > 0) {{
        html += '<div class="rec-section"><h3>Recommended Next Actions</h3>';
        html += '<div class="rec-list">';
        topRecs.forEach(function(r, i) {{
            var p = r.prog;
            var stars = '\\u2605'.repeat(p.reputation) + '\\u2606'.repeat(5 - p.reputation);
            var openD = parseDate(p.app_open_date);
            var closeD = parseDate(p.app_close_date);
            var badge = '';
            if (openD && closeD && openD <= today && closeD >= today) {{
                badge = '<span class="rec-badge rec-badge-open">OPEN NOW</span>';
            }} else if (openD && openD > today) {{
                var du = Math.ceil((openD - today) / (1000*60*60*24));
                if (du <= 14) badge = '<span class="rec-badge rec-badge-soon">Opens in ' + du + 'd</span>';
            }}
            html += '<div class="rec-card" onclick="showDetail(' + p.id + ')">';
            html += '<span class="rec-rank">#' + (i+1) + '</span>';
            html += '<div class="rec-info">';
            html += '<div class="rec-name">' + escHtml(p.hospital) + ' ' + badge + '</div>';
            html += '<div class="rec-meta"><span class="stars" style="font-size:0.65rem">' + stars + '</span>';
            if (p.pay_range) {{
                var pm = p.pay_range.match(/(\\$[\\d.,]+\\/hr)/);
                if (pm) html += ' <span style="color:#6b7280;font-size:0.72rem">' + pm[1] + '</span>';
            }}
            html += ' <span style="color:#9ca3af;font-size:0.68rem">' + escHtml(p.region) + '</span>';
            html += '</div></div>';
            html += '<span class="rec-score">' + Math.round(r.score) + '</span>';
            html += '</div>';
        }});
        html += '</div></div>';
    }}

    html += '<div class="stats-grid">';
    html += barChart('Application Status', statusCounts, statusColors);
    html += barChart('By Region', regionCounts, regionColors);
    html += barChart('BSN Requirement', bsnCounts, bsnColors);
    html += barChart('Pay Distribution', payBuckets, payColors);

    // Timeline status
    var timelineData = {{ 'Open Now': openNow, 'Upcoming (30d)': upcoming30, 'Future': future, 'Closed': closed, 'TBD': tbd }};
    var timelineColors = {{ 'Open Now': '#22c55e', 'Upcoming (30d)': '#f59e0b', 'Future': '#3b82f6', 'Closed': '#9ca3af', 'TBD': '#d1d5db' }};
    html += barChart('Application Timeline', timelineData, timelineColors);

    // Rep distribution
    var repData = {{}};
    [5,4,3,2,1].forEach(function(r) {{ repData['\u2605'.repeat(r) + '\u2606'.repeat(5-r)] = repCounts[r]; }});
    html += barChart('Reputation Distribution', repData, null);

    // Application funnel
    html += '<div class="stats-card"><h3>Application Funnel</h3>';
    html += '<div class="funnel">';
    var funnelStages = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer'];
    var funnelColors = ['#9ca3af', '#f59e0b', '#3b82f6', '#8b5cf6', '#22c55e'];
    var maxFunnel = Math.max.apply(null, funnelStages.map(function(s) {{ return statusCounts[s] || 0; }})) || 1;
    funnelStages.forEach(function(stage, i) {{
        var count = statusCounts[stage] || 0;
        var widthPct = Math.max(Math.round(count / maxFunnel * 100), count > 0 ? 12 : 4);
        html += '<div class="funnel-row">';
        html += '<div class="funnel-bar" style="width:' + widthPct + '%;background:' + funnelColors[i] + '">';
        html += '<span class="funnel-label">' + stage + '</span>';
        html += '<span class="funnel-count">' + count + '</span>';
        html += '</div>';
        if (i < funnelStages.length - 1) {{
            var nextCount = statusCounts[funnelStages[i+1]] || 0;
            var convRate = count > 0 ? Math.round(nextCount / count * 100) : 0;
            html += '<div class="funnel-arrow">' + convRate + '%</div>';
        }}
        html += '</div>';
    }});
    if (statusCounts['Rejected'] > 0) {{
        html += '<div class="funnel-rejected"><span>Rejected: ' + statusCounts['Rejected'] + '</span></div>';
    }}
    html += '</div></div>';

    // Data quality card
    var missingPay = 0, missingDates = 0, missingUrl = 0, missingCohort = 0;
    var incomplete = [];
    PROGRAMS.forEach(function(p) {{
        var issues = [];
        if (!p.pay_range || p.pay_range === 'TBD' || p.pay_range === '') {{ missingPay++; issues.push('pay'); }}
        if (!p.app_open_date || !p.app_close_date || p.app_open_date === 'TBD' || p.app_close_date === 'TBD') {{ missingDates++; issues.push('dates'); }}
        if (!p.application_url || p.application_url === '') {{ missingUrl++; issues.push('URL'); }}
        if (!p.cohort_start_date || p.cohort_start_date === 'TBD') {{ missingCohort++; issues.push('cohort'); }}
        if (issues.length > 0) incomplete.push({{ prog: p, issues: issues }});
    }});
    var completeness = Math.round(((total * 4 - missingPay - missingDates - missingUrl - missingCohort) / (total * 4)) * 100);
    html += '<div class="stats-card"><h3>Data Quality</h3>';
    html += '<div class="dq-score"><div class="dq-ring" style="--pct:' + completeness + '"><span>' + completeness + '%</span></div><div class="dq-label">Complete</div></div>';
    var dqData = {{ 'Missing Pay': missingPay, 'Missing Dates': missingDates, 'Missing Apply URL': missingUrl, 'Missing Cohort': missingCohort }};
    var dqColors = {{ 'Missing Pay': '#ef4444', 'Missing Dates': '#f59e0b', 'Missing Apply URL': '#8b5cf6', 'Missing Cohort': '#6b7280' }};
    Object.keys(dqData).forEach(function(key) {{
        if (dqData[key] > 0) {{
            html += '<div class="stats-bar-row"><span class="stats-bar-label">' + key + '</span>';
            html += '<div class="stats-bar-track"><div class="stats-bar-fill" style="width:' + Math.round(dqData[key]/total*100) + '%;background:' + dqColors[key] + '"></div></div>';
            html += '<span class="stats-bar-value">' + dqData[key] + '/' + total + '</span></div>';
        }}
    }});
    if (incomplete.length > 0) {{
        html += '<div class="dq-list"><strong>Needs attention:</strong>';
        incomplete.slice(0, 5).forEach(function(item) {{
            html += '<div class="dq-item"><a href="#" onclick="showDetail(' + item.prog.id + '); return false;">' + escHtml(item.prog.hospital) + '</a> <span class="dq-issues">' + item.issues.join(', ') + '</span></div>';
        }});
        if (incomplete.length > 5) html += '<div class="dq-item" style="color:#9ca3af">+' + (incomplete.length - 5) + ' more</div>';
        html += '</div>';
    }}
    html += '</div>';

    // Pay vs Reputation scatter plot
    html += '<div class="stats-card stats-card-wide"><h3>Pay vs. Reputation</h3>';
    html += '<div class="scatter-wrap">';
    var svgW = 500, svgH = 300, pad = 40;
    html += '<svg class="scatter-svg" viewBox="0 0 ' + svgW + ' ' + svgH + '" preserveAspectRatio="xMidYMid meet">';
    // Axes
    html += '<line x1="' + pad + '" y1="' + (svgH - pad) + '" x2="' + (svgW - 10) + '" y2="' + (svgH - pad) + '" stroke="#d1d5db" stroke-width="1"/>';
    html += '<line x1="' + pad + '" y1="10" x2="' + pad + '" y2="' + (svgH - pad) + '" stroke="#d1d5db" stroke-width="1"/>';
    // Axis labels
    html += '<text x="' + (svgW / 2) + '" y="' + (svgH - 5) + '" text-anchor="middle" fill="#6b7280" font-size="11">Pay ($/hr)</text>';
    html += '<text x="12" y="' + (svgH / 2) + '" text-anchor="middle" fill="#6b7280" font-size="11" transform="rotate(-90,12,' + (svgH / 2) + ')">Reputation</text>';
    // Grid lines
    for (var gi = 1; gi <= 5; gi++) {{
        var gy = svgH - pad - (gi / 5) * (svgH - pad - 10);
        html += '<line x1="' + pad + '" y1="' + gy + '" x2="' + (svgW - 10) + '" y2="' + gy + '" stroke="#f3f4f6" stroke-width="1"/>';
        html += '<text x="' + (pad - 4) + '" y="' + (gy + 4) + '" text-anchor="end" fill="#9ca3af" font-size="9">' + gi + '</text>';
    }}
    // Pay scale ticks ($30-$90)
    for (var pi = 30; pi <= 90; pi += 10) {{
        var px = pad + ((pi - 30) / 60) * (svgW - pad - 10);
        html += '<text x="' + px + '" y="' + (svgH - pad + 14) + '" text-anchor="middle" fill="#9ca3af" font-size="9">$' + pi + '</text>';
    }}
    // Plot programs
    var regionDotColors = {{'Bay Area':'#3b82f6','SoCal LA':'#f59e0b','SoCal Orange':'#f97316','San Diego':'#ef4444','Central Valley':'#22c55e','Sacramento':'#8b5cf6','NorCal':'#8b5cf6','Inland Empire':'#ec4899'}};
    PROGRAMS.forEach(function(p) {{
        var pm = (p.pay_range || '').match(/(\\d[\\d.,]+)\\/hr/);
        if (!pm) return;
        var payVal = parseFloat(pm[1].replace(',',''));
        var rep = p.reputation || 1;
        var x = pad + ((payVal - 30) / 60) * (svgW - pad - 10);
        var y = svgH - pad - (rep / 5) * (svgH - pad - 10);
        x = Math.max(pad, Math.min(svgW - 10, x));
        y = Math.max(10, Math.min(svgH - pad, y));
        var st = savedStatuses[p.id] || p.application_status || 'Not Started';
        var dotColor = '#9ca3af';
        Object.keys(regionDotColors).forEach(function(rk) {{ if (p.region.indexOf(rk) !== -1) dotColor = regionDotColors[rk]; }});
        var opacity = st === 'Rejected' ? '0.3' : st === 'Offer' ? '1' : '0.7';
        html += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="6" fill="' + dotColor + '" opacity="' + opacity + '" stroke="#fff" stroke-width="1.5">';
        html += '<title>' + escHtml(p.hospital) + '\\n$' + payVal.toFixed(2) + '/hr — ' + rep + ' stars\\n' + p.region + ' — ' + st + '</title>';
        html += '</circle>';
    }});
    html += '</svg>';
    // Legend
    html += '<div class="scatter-legend">';
    Object.keys(regionDotColors).forEach(function(r) {{
        html += '<span class="scatter-legend-item"><span class="scatter-legend-dot" style="background:' + regionDotColors[r] + '"></span>' + r + '</span>';
    }});
    html += '</div>';
    html += '</div></div>';

    // Region x Status heatmap
    html += '<div class="stats-card stats-card-wide"><h3>Region x Status Heatmap</h3>';
    html += '<div class="heatmap-scroll"><table class="heatmap-table"><thead><tr><th></th>';
    var hStatuses = ['Not Started','In Progress','Submitted','Interview','Offer','Rejected'];
    hStatuses.forEach(function(s) {{ html += '<th>' + s + '</th>'; }});
    html += '<th>Total</th></tr></thead><tbody>';
    var allRegions = Object.keys(regionCounts).sort();
    allRegions.forEach(function(reg) {{
        html += '<tr><td class="heatmap-label">' + reg + '</td>';
        var regTotal = 0;
        hStatuses.forEach(function(st) {{
            var count = 0;
            PROGRAMS.forEach(function(p) {{
                if (p.region === reg) {{
                    var ps = savedStatuses[p.id] || p.application_status || 'Not Started';
                    if (ps === st) count++;
                }}
            }});
            regTotal += count;
            var intensity = count === 0 ? '' : ' style="background:rgba(37,99,235,' + Math.min(0.15 + count * 0.15, 0.8) + ');color:' + (count > 3 ? '#fff' : '#1f2937') + '"';
            html += '<td class="heatmap-cell"' + intensity + '>' + (count || '') + '</td>';
        }});
        html += '<td class="heatmap-total">' + regTotal + '</td></tr>';
    }});
    html += '</tbody></table></div></div>';

    html += '</div>';

    // My Journey timeline
    var allLog = JSON.parse(localStorage.getItem('rn_tracker_log') || '[]');
    if (allLog.length > 0) {{
        html += '<div class="stats-card"><h3>My Application Journey</h3>';
        html += '<div class="journey-timeline">';
        // Group by date
        var grouped = {{}};
        allLog.slice().reverse().forEach(function(entry) {{
            var dateStr = entry.timestamp ? entry.timestamp.substring(0, 10) : 'Unknown';
            if (!grouped[dateStr]) grouped[dateStr] = [];
            grouped[dateStr].push(entry);
        }});
        var dates = Object.keys(grouped).sort().reverse().slice(0, 14); // Last 14 days
        dates.forEach(function(date) {{
            html += '<div class="journey-date">';
            html += '<div class="journey-date-label">' + date + '</div>';
            html += '<div class="journey-entries">';
            grouped[date].slice(0, 8).forEach(function(e) {{
                var prog = PROGRAMS.find(function(p) {{ return p.id === e.programId; }});
                var progName = prog ? prog.hospital : 'Program #' + e.programId;
                var icon = '&#9679;';
                if (e.action && e.action.indexOf('Status') !== -1) icon = '&#9654;';
                if (e.action && e.action.indexOf('note') !== -1) icon = '&#9998;';
                if (e.action && e.action.indexOf('tag') !== -1) icon = '&#9733;';
                if (e.action && e.action.indexOf('fav') !== -1) icon = '&#9829;';
                html += '<div class="journey-entry">';
                html += '<span class="journey-icon">' + icon + '</span>';
                html += '<span class="journey-prog">' + progName + '</span>';
                html += '<span class="journey-action">' + (e.action || '') + '</span>';
                if (e.timestamp) html += '<span class="journey-time">' + e.timestamp.substring(11, 16) + '</span>';
                html += '</div>';
            }});
            if (grouped[date].length > 8) html += '<div class="journey-more">+' + (grouped[date].length - 8) + ' more</div>';
            html += '</div></div>';
        }});
        html += '</div></div>';
    }}

    html += '</div>';

    document.getElementById('stats-dashboard').innerHTML = html;
}}

// Calendar view
var calMonth = new Date().getMonth();
var calYear = new Date().getFullYear();

function calPrev() {{ calMonth--; if (calMonth < 0) {{ calMonth = 11; calYear--; }} renderCalendar(); }}
function calNext() {{ calMonth++; if (calMonth > 11) {{ calMonth = 0; calYear++; }} renderCalendar(); }}
function calToday() {{ var now = new Date(); calMonth = now.getMonth(); calYear = now.getFullYear(); renderCalendar(); }}

function renderTimeline() {{
    var container = document.getElementById('gantt-container');
    if (!container) return;
    var savedStatuses = loadSavedStatuses();
    var today = new Date(); today.setHours(0,0,0,0);
    var regionFilter = (document.getElementById('timeline-region-filter') || {{}}).value || '';
    var sortBy = (document.getElementById('timeline-sort') || {{}}).value || 'open';

    // Timeline range: Feb 2026 to Jan 2027
    var tlStart = new Date(2026, 1, 1);
    var tlEnd = new Date(2027, 0, 31);
    var tlDays = Math.ceil((tlEnd - tlStart) / 86400000);

    // Filter programs
    var progs = PROGRAMS.filter(function(p) {{
        if (regionFilter && p.region !== regionFilter) return false;
        return parseDate(p.app_open_date) || parseDate(p.app_close_date) || parseDate(p.cohort_start);
    }});

    // Sort
    progs.sort(function(a, b) {{
        if (sortBy === 'close') {{
            var ac = parseDate(a.app_close_date), bc = parseDate(b.app_close_date);
            if (!ac) return 1; if (!bc) return -1; return ac - bc;
        }} else if (sortBy === 'hospital') {{
            return a.hospital.localeCompare(b.hospital);
        }} else if (sortBy === 'reputation') {{
            return (b.reputation || 0) - (a.reputation || 0);
        }} else {{
            var ao = parseDate(a.app_open_date), bo = parseDate(b.app_open_date);
            if (!ao) return 1; if (!bo) return -1; return ao - bo;
        }}
    }});

    function dayPos(d) {{
        return Math.max(0, Math.min(100, ((d - tlStart) / (tlEnd - tlStart)) * 100));
    }}

    var html = '<div class="gantt-header">';
    // Month headers
    for (var m = 1; m <= 12; m++) {{
        var mStart = new Date(2026, m, 1);
        var mEnd = new Date(2026, m + 1, 0);
        if (m === 12) {{ mStart = new Date(2026, 11, 1); mEnd = new Date(2026, 11, 31); }}
        var months = ['','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        if (m <= 12) {{
            var left = dayPos(mStart);
            var width = dayPos(mEnd) - left;
            html += '<div class="gantt-month" style="left:' + left + '%;width:' + width + '%">' + months[m] + '</div>';
        }}
    }}
    // Jan 2027
    var jan27Start = new Date(2027, 0, 1);
    html += '<div class="gantt-month" style="left:' + dayPos(jan27Start) + '%;width:' + (100 - dayPos(jan27Start)) + '%">Jan 27</div>';
    html += '</div>';

    // Today line
    if (today >= tlStart && today <= tlEnd) {{
        html += '<div class="gantt-today-line" style="left:' + dayPos(today) + '%"><span class="gantt-today-label">Today</span></div>';
    }}

    // Rows
    progs.forEach(function(p) {{
        var st = savedStatuses[p.id] || p.application_status || 'Not Started';
        var stCls = st.toLowerCase().replace(/\\s+/g, '-');
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        var cohortD = parseDate(p.cohort_start);
        var stars = '';
        for (var i = 0; i < (p.reputation || 0); i++) stars += '\\u2605';

        html += '<div class="gantt-row gantt-st-' + stCls + '" onclick="showDetail(' + p.id + ')">';
        html += '<div class="gantt-row-label"><span class="gantt-hospital">' + escHtml(p.hospital) + '</span>';
        html += '<span class="gantt-stars">' + stars + '</span></div>';
        html += '<div class="gantt-row-track">';

        // App window bar
        if (openD && closeD) {{
            var l = dayPos(openD);
            var r = dayPos(closeD);
            var w = Math.max(r - l, 0.5);
            var barColor = 'var(--accent,#3b82f6)';
            if (st === 'Submitted') barColor = '#3b82f6';
            else if (st === 'Interview') barColor = '#8b5cf6';
            else if (st === 'Offer') barColor = '#22c55e';
            else if (st === 'Rejected') barColor = '#ef4444';
            html += '<div class="gantt-bar" style="left:' + l + '%;width:' + w + '%;background:' + barColor + '" title="App window: ' + (p.app_open_date || '') + ' to ' + (p.app_close_date || '') + '"></div>';
        }}

        // Cohort marker
        if (cohortD) {{
            html += '<div class="gantt-cohort-marker" style="left:' + dayPos(cohortD) + '%" title="Cohort: ' + (p.cohort_start || '') + '"></div>';
        }}

        html += '</div></div>';
    }});

    container.innerHTML = html;
}}

function renderCalendar() {{
    var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    var title = document.getElementById('cal-month-title');
    if (title) title.textContent = months[calMonth] + ' ' + calYear;

    var firstDay = new Date(calYear, calMonth, 1).getDay();
    var daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    var today = new Date(); today.setHours(0,0,0,0);

    // Collect events for this month
    var calRegion = (document.getElementById('cal-region-filter') || {{}}).value || '';
    var events = {{}};
    PROGRAMS.forEach(function(p) {{
        if (calRegion && p.region !== calRegion) return;
        var openD = parseDate(p.app_open_date);
        var closeD = parseDate(p.app_close_date);
        var cohortD = parseDate(p.cohort_start);

        // Mark each day in the open window
        if (openD && closeD) {{
            var d = new Date(openD);
            while (d <= closeD) {{
                if (d.getMonth() === calMonth && d.getFullYear() === calYear) {{
                    var day = d.getDate();
                    if (!events[day]) events[day] = [];
                    // Only add the hospital once per day
                    var existing = events[day].find(function(e) {{ return e.id === p.id && e.type === 'open'; }});
                    if (!existing) {{
                        events[day].push({{id: p.id, hospital: p.hospital, type: 'open'}});
                    }}
                }}
                d.setDate(d.getDate() + 1);
            }}
        }}

        // Close date marker
        if (closeD && closeD.getMonth() === calMonth && closeD.getFullYear() === calYear) {{
            var cDay = closeD.getDate();
            if (!events[cDay]) events[cDay] = [];
            events[cDay].push({{id: p.id, hospital: p.hospital, type: 'close'}});
        }}

        // Cohort start marker
        if (cohortD && cohortD.getMonth() === calMonth && cohortD.getFullYear() === calYear) {{
            var coDay = cohortD.getDate();
            if (!events[coDay]) events[coDay] = [];
            events[coDay].push({{id: p.id, hospital: p.hospital, type: 'cohort'}});
        }}
    }});

    var html = '<div class="cal-header-row">';
    ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(function(d) {{
        html += '<div class="cal-header-cell">' + d + '</div>';
    }});
    html += '</div>';

    html += '<div class="cal-body">';
    var dayCount = 0;
    for (var w = 0; w < 6; w++) {{
        if (dayCount >= daysInMonth && w > 0) break;
        html += '<div class="cal-row">';
        for (var dow = 0; dow < 7; dow++) {{
            var dayNum = w * 7 + dow - firstDay + 1;
            if (dayNum < 1 || dayNum > daysInMonth) {{
                html += '<div class="cal-cell cal-empty"></div>';
            }} else {{
                var isToday = (dayNum === today.getDate() && calMonth === today.getMonth() && calYear === today.getFullYear());
                var dayEvents = events[dayNum] || [];
                var cls = 'cal-cell' + (isToday ? ' cal-today' : '') + (dayEvents.length > 0 ? ' cal-has-events' : '');
                html += '<div class="' + cls + '">';
                html += '<span class="cal-day-num">' + dayNum + '</span>';
                if (dayEvents.length > 0) {{
                    html += '<div class="cal-events">';
                    // Deduplicate and limit to 3
                    var shown = {{}};
                    var count = 0;
                    dayEvents.forEach(function(ev) {{
                        if (shown[ev.id + ev.type] || count >= 3) return;
                        shown[ev.id + ev.type] = true;
                        count++;
                        var dotCls = ev.type === 'close' ? 'cal-evt-close' : ev.type === 'cohort' ? 'cal-evt-cohort' : 'cal-evt-open';
                        html += '<a href="#" class="cal-event ' + dotCls + '" onclick="showDetail(' + ev.id + '); return false;" title="' + escHtml(ev.hospital) + '">' + escHtml(ev.hospital.substring(0, 12)) + '</a>';
                    }});
                    if (dayEvents.length > 3) {{
                        html += '<span class="cal-more">+' + (dayEvents.length - 3) + ' more</span>';
                    }}
                    html += '</div>';
                }}
                html += '</div>';
                dayCount = dayNum;
            }}
        }}
        html += '</div>';
    }}
    html += '</div>';

    document.getElementById('cal-grid').innerHTML = html;
}}

function dismissWelcome() {{
    localStorage.setItem('rn_tracker_welcomed', 'true');
    closeModalEl(document.getElementById('welcome-modal'));
}}

function toggleShortcutHelp() {{
    var modal = document.getElementById('shortcuts-modal');
    if (modal.classList.contains('modal-visible')) {{
        closeModalEl(modal);
    }} else {{
        openModal('shortcuts-modal');
    }}
}}

function closeModal() {{
    closeModalEl(document.getElementById('detail-modal'));
    if (window.location.hash.startsWith('#program-')) {{
        history.replaceState(null, '', window.location.pathname + window.location.search);
    }}
}}

function launchConfetti() {{
    var colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#ff922b', '#cc5de8'];
    var canvas = document.createElement('canvas');
    canvas.className = 'confetti-canvas';
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.body.appendChild(canvas);
    var ctx = canvas.getContext('2d');
    var particles = [];
    for (var i = 0; i < 80; i++) {{
        particles.push({{
            x: Math.random() * canvas.width,
            y: -20 - Math.random() * 200,
            w: 4 + Math.random() * 6,
            h: 6 + Math.random() * 8,
            color: colors[Math.floor(Math.random() * colors.length)],
            vx: (Math.random() - 0.5) * 4,
            vy: 2 + Math.random() * 4,
            rot: Math.random() * 360,
            vr: (Math.random() - 0.5) * 10
        }});
    }}
    var startTime = Date.now();
    function animate() {{
        var elapsed = Date.now() - startTime;
        if (elapsed > 3000) {{
            canvas.remove();
            return;
        }}
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(function(p) {{
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.1;
            p.rot += p.vr;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot * Math.PI / 180);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = Math.max(0, 1 - elapsed / 3000);
            ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
            ctx.restore();
        }});
        requestAnimationFrame(animate);
    }}
    animate();
}}

function exportSummary() {{
    var savedStatuses = loadSavedStatuses();
    var today = new Date();
    var lines = [];
    lines.push('CA New Grad RN Application Summary');
    lines.push('Generated: ' + today.toLocaleDateString('en-US', {{weekday:'long', year:'numeric', month:'long', day:'numeric'}}));
    lines.push('');

    var statuses = ['Interview', 'Submitted', 'In Progress', 'Offer', 'Not Started', 'Rejected'];
    statuses.forEach(function(status) {{
        var progs = PROGRAMS.filter(function(p) {{
            return (savedStatuses[p.id] || p.application_status || 'Not Started') === status;
        }});
        if (progs.length === 0) return;
        lines.push('## ' + status + ' (' + progs.length + ')');
        progs.forEach(function(p) {{
            var stars = '\\u2605'.repeat(p.reputation) + '\\u2606'.repeat(5 - p.reputation);
            var line = '- ' + p.hospital;
            if (p.pay_range) {{
                var pm = p.pay_range.match(/(\\$[\\d.,]+\\/hr)/);
                if (pm) line += ' | ' + pm[1];
            }}
            line += ' | ' + p.region + ' | ' + stars;
            var closeD = parseDate(p.app_close_date);
            if (closeD) {{
                var daysLeft = Math.ceil((closeD - today) / (1000*60*60*24));
                if (daysLeft >= 0 && daysLeft <= 30) {{
                    line += ' | closes in ' + daysLeft + 'd';
                }}
            }}
            lines.push(line);
        }});
        lines.push('');
    }});

    var goalTarget = parseInt(localStorage.getItem('rn_tracker_goal') || '10');
    var applied = PROGRAMS.filter(function(p) {{
        var s = savedStatuses[p.id] || 'Not Started';
        return s === 'Submitted' || s === 'Interview' || s === 'Offer';
    }}).length;
    lines.push('Goal Progress: ' + applied + '/' + goalTarget + ' (' + Math.round(applied/goalTarget*100) + '%)');

    var text = lines.join('\\n');
    navigator.clipboard.writeText(text).then(function() {{
        showToast('Summary copied to clipboard!');
    }});
}}

function generateProgressCard() {{
    var savedStatuses = loadSavedStatuses();
    var today = new Date();
    var statusCounts = {{ 'Not Started': 0, 'In Progress': 0, 'Submitted': 0, 'Interview': 0, 'Offer': 0, 'Rejected': 0 }};
    PROGRAMS.forEach(function(p) {{
        var s = savedStatuses[p.id] || p.application_status || 'Not Started';
        if (statusCounts[s] !== undefined) statusCounts[s]++;
    }});
    var goalTarget = parseInt(localStorage.getItem('rn_tracker_goal') || '10');
    var applied = statusCounts['Submitted'] + statusCounts['Interview'] + statusCounts['Offer'];
    var goalPct = Math.min(Math.round(applied / goalTarget * 100), 100);

    // NCLEX countdown
    var nclexDate = new Date(2026, 4, 1);
    var nclexDays = Math.max(0, Math.ceil((nclexDate - today) / 86400000));

    // Find next deadline
    var nextDeadline = null;
    var nextDeadlineHospital = '';
    PROGRAMS.forEach(function(p) {{
        var cd = parseDate(p.app_close_date);
        if (cd && cd >= today) {{
            if (!nextDeadline || cd < nextDeadline) {{
                nextDeadline = cd;
                nextDeadlineHospital = p.hospital;
            }}
        }}
    }});

    var canvas = document.createElement('canvas');
    var W = 800, H = 520;
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext('2d');

    // Background gradient
    var grad = ctx.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, '#0f172a');
    grad.addColorStop(1, '#1e293b');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // Decorative accent line at top
    var accentGrad = ctx.createLinearGradient(0, 0, W, 0);
    accentGrad.addColorStop(0, '#3b82f6');
    accentGrad.addColorStop(0.5, '#8b5cf6');
    accentGrad.addColorStop(1, '#ec4899');
    ctx.fillStyle = accentGrad;
    ctx.fillRect(0, 0, W, 4);

    // Title
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 26px system-ui, -apple-system, sans-serif';
    ctx.fillText('CA New Grad RN — Application Progress', 32, 48);

    // Date
    ctx.fillStyle = '#94a3b8';
    ctx.font = '14px system-ui, -apple-system, sans-serif';
    ctx.fillText(today.toLocaleDateString('en-US', {{weekday:'long', year:'numeric', month:'long', day:'numeric'}}), 32, 72);

    // Goal progress arc
    var cx = 130, cy = 170, r = 58;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 10;
    ctx.stroke();

    var startAngle = -Math.PI / 2;
    var endAngle = startAngle + (goalPct / 100) * Math.PI * 2;
    var arcGrad = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r);
    arcGrad.addColorStop(0, '#3b82f6');
    arcGrad.addColorStop(1, '#8b5cf6');
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, endAngle);
    ctx.strokeStyle = arcGrad;
    ctx.lineWidth = 10;
    ctx.lineCap = 'round';
    ctx.stroke();
    ctx.lineCap = 'butt';

    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 32px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(goalPct + '%', cx, cy + 8);
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(applied + '/' + goalTarget + ' applied', cx, cy + 28);
    ctx.textAlign = 'left';

    // Status boxes
    var statuses = [
        {{ label: 'Submitted', count: statusCounts['Submitted'], color: '#22c55e', bg: '#052e16' }},
        {{ label: 'Interview', count: statusCounts['Interview'], color: '#3b82f6', bg: '#172554' }},
        {{ label: 'Offer', count: statusCounts['Offer'], color: '#eab308', bg: '#422006' }},
        {{ label: 'In Progress', count: statusCounts['In Progress'], color: '#a78bfa', bg: '#2e1065' }},
        {{ label: 'Not Started', count: statusCounts['Not Started'], color: '#94a3b8', bg: '#1e293b' }},
        {{ label: 'Rejected', count: statusCounts['Rejected'], color: '#ef4444', bg: '#450a0a' }}
    ];

    var boxW = 110, boxH = 70, boxGap = 12, startX = 240, startY = 110;
    statuses.forEach(function(st, i) {{
        var col = i % 3;
        var row = Math.floor(i / 3);
        var bx = startX + col * (boxW + boxGap);
        var by = startY + row * (boxH + boxGap);

        ctx.fillStyle = st.bg;
        roundRect(ctx, bx, by, boxW, boxH, 8);
        ctx.fill();

        ctx.fillStyle = st.color;
        ctx.font = 'bold 28px system-ui, sans-serif';
        ctx.fillText(st.count.toString(), bx + 12, by + 36);
        ctx.font = '12px system-ui, sans-serif';
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(st.label, bx + 12, by + 56);
    }});

    // NCLEX countdown card
    var ncx = 640, ncy = 110;
    ctx.fillStyle = '#1e1b4b';
    roundRect(ctx, ncx, ncy, 130, 150, 10);
    ctx.fill();
    ctx.strokeStyle = '#4338ca';
    ctx.lineWidth = 1;
    roundRect(ctx, ncx, ncy, 130, 150, 10);
    ctx.stroke();

    ctx.fillStyle = '#818cf8';
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('NCLEX', ncx + 65, ncy + 28);
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 44px system-ui, sans-serif';
    ctx.fillText(nclexDays.toString(), ncx + 65, ncy + 80);
    ctx.fillStyle = '#818cf8';
    ctx.font = '13px system-ui, sans-serif';
    ctx.fillText('days to go', ncx + 65, ncy + 102);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillText('May 2026', ncx + 65, ncy + 130);
    ctx.textAlign = 'left';

    // Divider
    ctx.fillStyle = '#334155';
    ctx.fillRect(32, 290, W - 64, 1);

    // Status bar chart
    var barY = 310;
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 15px system-ui, sans-serif';
    ctx.fillText('Application Pipeline', 32, barY + 10);

    var barStartX = 32, barMaxW = W - 64, barH = 24;
    var total = PROGRAMS.length;
    var barColors = ['#22c55e', '#3b82f6', '#eab308', '#a78bfa', '#475569', '#ef4444'];
    var barCounts = [statusCounts['Submitted'], statusCounts['Interview'], statusCounts['Offer'], statusCounts['In Progress'], statusCounts['Not Started'], statusCounts['Rejected']];

    var curX = barStartX;
    barCounts.forEach(function(count, i) {{
        if (count === 0) return;
        var w = (count / total) * barMaxW;
        ctx.fillStyle = barColors[i];
        if (i === 0) {{
            roundRectPartial(ctx, curX, barY + 22, w, barH, 6, true, false);
        }} else if (i === barCounts.length - 1 || barCounts.slice(i + 1).every(function(c) {{ return c === 0; }})) {{
            roundRectPartial(ctx, curX, barY + 22, w, barH, 6, false, true);
        }} else {{
            ctx.fillRect(curX, barY + 22, w, barH);
        }}
        ctx.fill();
        curX += w;
    }});

    // Bar legend
    var legY = barY + 58;
    var legX = 32;
    var legItems = ['Submitted', 'Interview', 'Offer', 'In Progress', 'Not Started', 'Rejected'];
    legItems.forEach(function(label, i) {{
        if (barCounts[i] === 0) return;
        ctx.fillStyle = barColors[i];
        ctx.fillRect(legX, legY, 10, 10);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillText(label + ' (' + barCounts[i] + ')', legX + 15, legY + 9);
        legX += ctx.measureText(label + ' (' + barCounts[i] + ')').width + 30;
    }});

    // Upcoming deadline
    if (nextDeadline) {{
        var dlDays = Math.ceil((nextDeadline - today) / 86400000);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 15px system-ui, sans-serif';
        ctx.fillText('Next Deadline', 32, 420);
        ctx.fillStyle = dlDays <= 3 ? '#ef4444' : dlDays <= 7 ? '#f59e0b' : '#94a3b8';
        ctx.font = '14px system-ui, sans-serif';
        ctx.fillText(nextDeadlineHospital + ' — ' + dlDays + ' day' + (dlDays !== 1 ? 's' : '') + ' (' + nextDeadline.toLocaleDateString() + ')', 32, 442);
    }}

    // Total programs tracked
    ctx.fillStyle = '#475569';
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText('Tracking ' + PROGRAMS.length + ' CA new grad RN residency programs', 32, H - 28);

    // Watermark
    ctx.fillStyle = '#334155';
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('CA Nursing Tracker', W - 32, H - 28);
    ctx.textAlign = 'left';

    return canvas;
}}

function roundRect(ctx, x, y, w, h, r) {{
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}}

function roundRectPartial(ctx, x, y, w, h, r, left, right) {{
    ctx.beginPath();
    if (left) {{
        ctx.moveTo(x + r, y);
    }} else {{
        ctx.moveTo(x, y);
    }}
    if (right) {{
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    }} else {{
        ctx.lineTo(x + w, y);
        ctx.lineTo(x + w, y + h);
    }}
    if (left) {{
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
    }} else {{
        ctx.lineTo(x, y + h);
        ctx.lineTo(x, y);
    }}
    ctx.closePath();
}}

function showProgressCard() {{
    var canvas = generateProgressCard();
    var modal = document.getElementById('progress-card-modal');
    var container = document.getElementById('progress-card-container');
    container.innerHTML = '';
    canvas.style.maxWidth = '100%';
    canvas.style.height = 'auto';
    canvas.style.borderRadius = '12px';
    container.appendChild(canvas);
    openModal('progress-card-modal');
}}

function downloadProgressCard() {{
    var canvas = generateProgressCard();
    var link = document.createElement('a');
    link.download = 'rn-progress-' + new Date().toISOString().slice(0, 10) + '.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
    showToast('Progress card downloaded!');
}}

function copyProgressCard() {{
    var canvas = generateProgressCard();
    canvas.toBlob(function(blob) {{
        if (navigator.clipboard && navigator.clipboard.write) {{
            navigator.clipboard.write([
                new ClipboardItem({{ 'image/png': blob }})
            ]).then(function() {{
                showToast('Progress card copied to clipboard!');
            }}).catch(function() {{
                showToast('Copy failed — try downloading instead');
            }});
        }} else {{
            showToast('Clipboard API not supported — try downloading');
        }}
    }}, 'image/png');
}}

function editGoal() {{
    var current = localStorage.getItem('rn_tracker_goal') || '10';
    var newGoal = prompt('Set your application goal (number of programs to apply to):', current);
    if (newGoal && !isNaN(parseInt(newGoal)) && parseInt(newGoal) > 0) {{
        localStorage.setItem('rn_tracker_goal', parseInt(newGoal).toString());
        renderStats();
        showToast('Goal updated to ' + parseInt(newGoal));
    }}
}}

function printView() {{
    window.print();
}}

function showActivityFeed() {{
    var log = getActivityLog();
    var body = document.getElementById('activity-feed-body');
    if (!body) return;
    if (log.length === 0) {{
        body.innerHTML = '<div style="text-align:center;color:#9ca3af;padding:40px">No activity recorded yet. Changes you make will appear here.</div>';
        openModal('activity-modal');
        return;
    }}
    var html = '<div class="activity-feed">';
    var lastDate = '';
    log.forEach(function(entry) {{
        var d = new Date(entry.time);
        var dateStr = d.toLocaleDateString('en-US', {{weekday:'short', month:'short', day:'numeric'}});
        if (dateStr !== lastDate) {{
            html += '<div class="feed-date-header">' + dateStr + '</div>';
            lastDate = dateStr;
        }}
        var timeStr = d.toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit'}});
        var prog = PROGRAMS.find(function(p) {{ return p.id === entry.id; }});
        var progName = prog ? escHtml(prog.hospital) : 'Unknown';
        html += '<div class="feed-entry">';
        html += '<span class="feed-dot"></span>';
        html += '<div class="feed-content">';
        html += '<a href="#" onclick="showDetail(' + entry.id + '); return false;" class="feed-prog">' + progName + '</a>';
        html += '<span class="feed-action">' + escHtml(entry.action) + '</span>';
        html += '</div>';
        html += '<span class="feed-time">' + timeStr + '</span>';
        html += '</div>';
    }});
    html += '</div>';
    body.innerHTML = html;
    openModal('activity-modal');
}}

function hideCtxMenu() {{
    var m = document.querySelector('.ctx-menu');
    if (m) m.style.display = 'none';
}}

function quickSetStatus(id, status) {{
    saveStatus(id, status);
    var row = document.querySelector('tr[data-id="' + id + '"]');
    if (row) {{
        applyRowStatus(row, status);
        row.dataset.status = status;
        var sel = row.querySelector('.status-select');
        if (sel) sel.value = status;
    }}
    renderStatusSummary();
    renderNotifications();
    hideCtxMenu();
    showToast('Status: ' + status);
}}

function announce(message) {{
    var region = document.getElementById('live-region');
    if (region) {{
        region.textContent = '';
        setTimeout(function() {{ region.textContent = message; }}, 50);
    }}
}}

function showToast(message) {{
    var toast = document.querySelector('.toast');
    if (!toast) {{
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }}
    toast.innerHTML = message;
    toast.classList.add('show');
    announce(message.replace(/<[^>]*>/g, ''));
    clearTimeout(toast._timer);
    toast._timer = setTimeout(function() {{ toast.classList.remove('show'); }}, 2500);
}}

var undoTimer = null;
function showUndoToast(message, undoFn) {{
    var toast = document.querySelector('.toast');
    if (!toast) {{
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }}
    toast.innerHTML = message + ' <button class="undo-btn" onclick="event.stopPropagation();">Undo</button>';
    toast.querySelector('.undo-btn').addEventListener('click', function() {{
        undoFn();
        toast.classList.remove('show');
        showToast('Undone');
    }});
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(function() {{ toast.classList.remove('show'); }}, 5000);
}}
    </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    output_path = os.path.join(DOCS_DIR, "index.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated static site: {output_path}")
    print(f"  {total} programs, {open_now} open, {upcoming} upcoming")


if __name__ == "__main__":
    generate()
