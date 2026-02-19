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

        status_options = ""
        for s in statuses:
            sel = " selected" if s == status else ""
            status_options += f'<option value="{esc(s)}"{sel}>{esc(s)}</option>'

        apply_cell = ""
        if p.get("application_url"):
            apply_cell = f'<a href="{esc(p["application_url"])}" target="_blank" class="apply-link">Apply &rarr;</a>'

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
<td class="col-hospital frozen-col"><a href="#" class="hospital-link" data-id="{p['id']}">{esc(p['hospital'])}</a></td>
<td class="col-program">{esc(p.get('program_name',''))}</td>
<td class="col-region">{region_dot}{esc(p.get('region',''))}</td>
<td class="col-city" title="{full_city}">{esc(city)}</td>
<td class="col-bsn {bsn_cls}">{esc(bsn)}</td>
<td class="col-date" data-raw="{esc(app_open_raw)}" title="{esc(open_title)}">{app_open_fmt}</td>
<td class="col-date" data-raw="{esc(app_close_raw)}">{app_close_fmt}</td>
<td class="col-date" data-raw="{esc(cohort_raw)}">{cohort_fmt}</td>
<td class="col-rep stars">{stars}</td>
<td class="col-pay" title="{esc(p.get('pay_range', ''))}">{esc(pay)}{pay_bar_html}</td>
<td class="col-len">{p.get('program_length_months','')}mo</td>
<td class="col-specialties" title="{esc(specs)}">{esc(specs)}</td>
<td class="col-status"><select class="status-select" data-id="{p['id']}">{status_options}</select></td>
<td class="col-notes">{notes_cell}</td>
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

    nclex_stat = f"<strong>{nclex_days}d</strong>" if nclex_days is not None else nclex_date
    urgent_class = ' stat-highlight-red' if urgent > 0 else ''
    urgent_text = f" ({urgent} urgent)" if urgent > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Track {total} California new graduate RN residency programs — application dates, deadlines, pay rates, and requirements.">
    <title>CA New Grad RN Tracker</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏥</text></svg>">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
{css}
    </style>
</head>
<body>
    <a href="#main-table" class="skip-link">Skip to programs table</a>
    <nav class="container-fluid" role="navigation" aria-label="Main navigation">
        <ul>
            <li><strong>CA New Grad RN Tracker</strong></li>
        </ul>
        <ul>
            <li><a href="#" class="active" id="nav-table" onclick="showView('table'); return false;">Table</a></li>
            <li><a href="#" id="nav-pipeline" onclick="showView('pipeline'); return false;">Pipeline</a></li>
            <li><a href="#" id="nav-calendar" onclick="showView('calendar'); return false;">Calendar</a></li>
            <li><a href="#" id="nav-stats" onclick="showView('stats'); return false;">Stats</a></li>
            <li class="nclex-nav" title="Days until NCLEX ({nclex_date})"><span class="nclex-badge">{nclex_days if nclex_days is not None else '?'}d</span> NCLEX</li>
            <li><a href="#" onclick="toggleTheme(); return false;" id="theme-toggle" title="Toggle dark mode">Dark</a></li>
            <li><a href="#" onclick="toggleShortcutHelp(); return false;" title="Keyboard shortcuts (?)" class="nav-help">?</a></li>
        </ul>
    </nav>

    <div class="urgency-banner" id="urgency-banner" style="display:none"></div>

    <main class="container-fluid sheet-page" role="main" id="main-table">
        <div class="sheet-toolbar">
            <div class="sheet-filters">
                <input type="search" name="q" placeholder="Search... ( / )" value="">
                <select data-instant="region">
                    <option value="">All Regions</option>
                    {region_options}
                </select>
                <select data-instant="city">
                    <option value="">All Cities</option>
                    {city_options}
                </select>
                <select data-instant="bsn">
                    <option value="">All BSN</option>
                    {bsn_options}
                </select>
                <select data-instant="status">
                    <option value="">All Statuses</option>
                    {status_options_filter}
                </select>
                <select data-instant="cohort-status">
                    <option value="">All Cohorts</option>
                    <option value="released">Released</option>
                    <option value="not-released">Not Released</option>
                    <option value="rolling">Rolling</option>
                    <option value="paused">Paused</option>
                </select>
                <span class="sheet-count">{total} rows</span>
                <button type="button" class="clear-filter" id="clear-all-btn" onclick="clearAllFilters()" style="display:none">Clear All</button>
                <span class="filter-spacer"></span>
                <select id="sort-preset" onchange="applySortPreset(this.value)" style="height:28px;font-size:0.75rem;padding:4px 8px;margin:0;border:1px solid #d1d5db;border-radius:3px">
                    <option value="">Sort by...</option>
                    <option value="deadline">Nearest Deadline</option>
                    <option value="pay-high">Highest Pay</option>
                    <option value="rep-high">Best Reputation</option>
                    <option value="opening">Opening Soon</option>
                    <option value="cohort">Cohort Start</option>
                    <option value="hospital">Hospital A-Z</option>
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
            <button class="chip chip-amber" onclick="filterUpcoming(this)">Upcoming <span class="chip-count">{upcoming}</span></button>
            <button class="chip" onclick="filterBsn('No', this)">ADN OK</button>
            <button class="chip" onclick="filterBsn('Preferred', this)">BSN Preferred</button>
            <span class="chip-sep"></span>
            <button class="chip chip-purple" onclick="filterCohort('jul-sep', this)">Jul-Sep <span class="chip-count">{cohort_jul_sep}</span></button>
            <button class="chip chip-purple" onclick="filterCohort('oct-dec', this)">Oct-Dec <span class="chip-count">{cohort_oct_dec}</span></button>
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

    <!-- Pipeline View -->
    <div id="pipeline-view" class="container-fluid" style="display:none">
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
        </div>
        <div class="cal-grid" id="cal-grid"></div>
        <div class="cal-legend">
            <span><span class="cal-legend-dot cal-dot-open"></span> App window open</span>
            <span><span class="cal-legend-dot cal-dot-close"></span> App deadline</span>
            <span><span class="cal-legend-dot cal-dot-cohort"></span> Cohort start</span>
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

    <footer class="container">
        <small>{total} programs across {len(regions)} regions &bull; Updated {today.strftime("%b %d, %Y")}</small>
        <small class="shortcuts-hint"><kbd>/</kbd> Search &bull; <kbd>j</kbd><kbd>k</kbd> Navigate &bull; <kbd>Enter</kbd> Details &bull; <kbd>&larr;</kbd><kbd>&rarr;</kbd> Prev/Next &bull; <kbd>d</kbd> Dark mode &bull; <kbd>Esc</kbd> Close</small>
    </footer>

    <button class="back-to-top" id="back-to-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="Back to top">&uarr;</button>

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
    }} catch(e) {{}}
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
    }} else {{
        favs.push(id);
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
}}

function filterByStatus(status) {{
    resetFilters();
    var statusSel = document.querySelector('[data-instant="status"]');
    if (statusSel) statusSel.value = status;
    filterTable();
    updateUrlParams();
    showToast('Showing ' + status);
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
                applyRowStatus(row, this.value);
                row.dataset.status = this.value;
                saveStatus(this.dataset.id, this.value);
                renderStatusSummary();
                showToast('Status saved');
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

    document.querySelectorAll('.compare-check').forEach(function(cb) {{
        cb.addEventListener('change', updateCompareBtn);
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

    // Search
    if (searchInput) {{
        searchInput.addEventListener('input', debounce(function() {{ filterTable(); updateUrlParams(); }}, 150));
    }}

    // Filter dropdowns
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function(sel) {{
        sel.addEventListener('change', function() {{ filterTable(); updateUrlParams(); }});
    }});

    // Keyboard: / to search, j/k to navigate rows, Enter to open detail
    var selectedRowIdx = -1;
    document.addEventListener('keydown', function(e) {{
        if (e.key === '/' && !isEditing(e.target)) {{
            var si = document.querySelector('.sheet-filters input[type="search"]');
            if (si) {{ e.preventDefault(); si.focus(); si.select(); }}
        }}
        if (e.key === 'Escape') document.activeElement.blur();

        if (!isEditing(e.target)) {{
            // Keyboard shortcuts
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
    renderFavButtons();
    updateFavCount();
    renderStatusSummary();
    renderRecentViewed();
    renderUrgencyBanner();

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

    // Back to top button visibility
    var topBtn = document.getElementById('back-to-top');
    if (topBtn) {{
        window.addEventListener('scroll', function() {{
            if (window.scrollY > 300) {{
                topBtn.classList.add('visible');
            }} else {{
                topBtn.classList.remove('visible');
            }}
        }});
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

        if (window._specialFilter === 'favorites') {{
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
                }}
            }}
        }}
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
        theme: localStorage.getItem('rn_tracker_theme') || 'light',
        density: localStorage.getItem('rn_tracker_density') || 'normal',
        cols: JSON.parse(localStorage.getItem('rn_tracker_cols') || '{{}}'),
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
            if (data.cols) localStorage.setItem('rn_tracker_cols', JSON.stringify(data.cols));
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
    if (html.dataset.theme === 'dark') {{
        html.dataset.theme = 'light';
        btn.textContent = 'Dark';
        localStorage.setItem('rn_tracker_theme', 'light');
    }} else {{
        html.dataset.theme = 'dark';
        btn.textContent = 'Light';
        localStorage.setItem('rn_tracker_theme', 'dark');
    }}
}}

// Restore theme preference
(function() {{
    try {{
        var theme = localStorage.getItem('rn_tracker_theme');
        if (theme === 'dark') {{
            document.documentElement.dataset.theme = 'dark';
            var btn = document.getElementById('theme-toggle');
            if (btn) btn.textContent = 'Light';
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
    }}
    sel.value = '';
    showDetail(id); // re-render
    showToast('Tag added');
}}

function removeTag(id, tag) {{
    var tags = loadTags(id);
    tags = tags.filter(function(t) {{ return t !== tag; }});
    saveTags(id, tags);
    showDetail(id); // re-render
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

    html += '<div class="detail-meta"><span class="stars">' + stars + '</span>';
    html += ' <span class="' + bsnCls + '">' + escHtml(p.bsn_required || 'N/A') + ' BSN</span>';
    html += ' <select class="modal-status-select ' + statusSelCls + '" id="modal-status" data-id="' + p.id + '">' + statusOpts + '</select>';
    if (p.last_updated) {{
        html += ' <span class="detail-updated">Updated: ' + escHtml(p.last_updated) + '</span>';
    }}
    html += '</div>';
    html += '</div>';

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
    html += '</dl></div>';

    html += '<div class="detail-section"><h3>Details</h3><dl>';
    html += '<dt>Region</dt><dd>' + escHtml(p.region) + '</dd>';
    html += '<dt>City</dt><dd>' + escHtml(p.city) + '</dd>';
    html += '<dt>Pay</dt><dd>' + escHtml(p.pay_range || 'N/A') + '</dd>';
    html += '<dt>Length</dt><dd>' + (p.program_length_months || 'N/A') + ' months</dd>';
    html += '</dl></div>';

    html += '</div>';

    html += '<div class="detail-section"><h3>Specialties</h3><p>' + escHtml(specs) + '</p></div>';
    html += '<div class="detail-section"><h3>Requirements</h3><p>' + escHtml(p.requirements || 'N/A').replace(/\\n/g, '<br>') + '</p></div>';

    if (repNotes) {{
        html += '<div class="detail-section"><h3>Reputation Notes</h3><p class="detail-rep-notes">' + repNotes + '</p></div>';
    }}

    // Editable notes — load saved notes from localStorage
    var savedNotes = loadSavedNotes();
    var currentNotes = savedNotes[p.id] !== undefined ? savedNotes[p.id] : (p.personal_notes || '');
    html += '<div class="detail-section"><h3>Your Notes</h3>';
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
            showToast('Status updated');
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
    var navTable = document.getElementById('nav-table');
    var navPipeline = document.getElementById('nav-pipeline');

    var calendarView = document.getElementById('calendar-view');
    var statsView = document.getElementById('stats-view');
    var navCalendar = document.getElementById('nav-calendar');
    var navStats = document.getElementById('nav-stats');

    // Hide all
    [tableView, pipelineView, calendarView, statsView].forEach(function(v) {{ v.style.display = 'none'; }});
    [navTable, navPipeline, navCalendar, navStats].forEach(function(n) {{ n.classList.remove('active'); }});

    if (view === 'pipeline') {{
        pipelineView.style.display = 'block';
        navPipeline.classList.add('active');
        renderPipeline();
    }} else if (view === 'calendar') {{
        calendarView.style.display = 'block';
        navCalendar.classList.add('active');
        renderCalendar();
    }} else if (view === 'stats') {{
        statsView.style.display = 'block';
        navStats.classList.add('active');
        renderStats();
    }} else {{
        tableView.style.display = '';
        navTable.classList.add('active');
    }}
}}

function renderPipeline() {{
    var savedStatuses = loadSavedStatuses();
    var columns = ['Not Started', 'In Progress', 'Submitted', 'Interview', 'Offer', 'Rejected'];
    var grouped = {{}};
    columns.forEach(function(c) {{ grouped[c] = []; }});

    PROGRAMS.forEach(function(p) {{
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
        html += '<div class="pipeline-col-body">';
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
            html += '<div class="pipeline-card' + (isFav ? ' pipeline-fav' : '') + '" onclick="showDetail(' + p.id + ')">';
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
            html += '<div class="pipeline-empty">No programs</div>';
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

    var html = '<div class="stats-header">';
    html += '<h2>Program Analytics</h2>';
    html += '<div class="stats-summary-cards">';
    html += '<div class="stats-num-card"><span class="stats-big-num">' + total + '</span><span>Total Programs</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num stat-green">' + openNow + '</span><span>Open Now</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num" style="color:#f59e0b">' + upcoming30 + '</span><span>Closing in 30d</span></div>';
    html += '<div class="stats-num-card"><span class="stats-big-num" style="color:#8b5cf6">' + favs.length + '</span><span>Favorites</span></div>';
    html += '</div></div>';

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

    html += '</div>';

    document.getElementById('stats-dashboard').innerHTML = html;
}}

// Calendar view
var calMonth = new Date().getMonth();
var calYear = new Date().getFullYear();

function calPrev() {{ calMonth--; if (calMonth < 0) {{ calMonth = 11; calYear--; }} renderCalendar(); }}
function calNext() {{ calMonth++; if (calMonth > 11) {{ calMonth = 0; calYear++; }} renderCalendar(); }}
function calToday() {{ var now = new Date(); calMonth = now.getMonth(); calYear = now.getFullYear(); renderCalendar(); }}

function renderCalendar() {{
    var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    var title = document.getElementById('cal-month-title');
    if (title) title.textContent = months[calMonth] + ' ' + calYear;

    var firstDay = new Date(calYear, calMonth, 1).getDay();
    var daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    var today = new Date(); today.setHours(0,0,0,0);

    // Collect events for this month
    var events = {{}};
    PROGRAMS.forEach(function(p) {{
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

function showToast(message) {{
    var toast = document.querySelector('.toast');
    if (!toast) {{
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }}
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(function() {{ toast.classList.remove('show'); }}, 2500);
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
