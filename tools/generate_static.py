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
    <nav class="container-fluid">
        <ul>
            <li><strong>CA New Grad RN Tracker</strong></li>
        </ul>
        <ul>
            <li><a href="#" class="active">Programs</a></li>
            <li><a href="#" onclick="toggleTheme(); return false;" id="theme-toggle" title="Toggle dark mode">Dark</a></li>
        </ul>
    </nav>

    <main class="container-fluid sheet-page">
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
                <div class="col-toggle-wrap">
                    <button type="button" onclick="toggleColMenu()" title="Show/hide columns">Columns</button>
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
                <button type="button" id="compare-btn" disabled onclick="goCompare()">Compare</button>
                <button type="button" onclick="toggleDensity()" title="Toggle compact/comfortable view" id="density-btn">Compact</button>
                <button type="button" onclick="exportCSV()" title="Export CSV">Export</button>
            </div>
        </div>

        <div class="quick-chips">
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
                        <th class="col-hospital frozen-col sortable" data-col="1" data-sort="text" data-label="Hospital">Hospital <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-program sortable" data-col="2" data-sort="text" data-label="Program">Program <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-region sortable" data-col="3" data-sort="text" data-label="Region">Region <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-city sortable" data-col="4" data-sort="text" data-label="City">City <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-bsn sortable" data-col="5" data-sort="text" data-label="BSN">BSN <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="6" data-sort="date" data-label="App Open">App Open <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="7" data-sort="date" data-label="App Close">App Close <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-date sortable" data-col="8" data-sort="date" data-label="Cohort">Cohort <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-rep sortable" data-col="9" data-sort="stars" data-label="Reputation">Rep <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-pay sortable" data-col="10" data-sort="pay" data-label="Pay">Pay <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-len sortable" data-col="11" data-sort="num" data-label="Length">Len <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-specialties sortable" data-col="12" data-sort="text" data-label="Specialties">Specialties <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-status sortable" data-col="13" data-sort="status" data-label="Status">Status <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-notes sortable" data-col="14" data-sort="text" data-label="Notes">Notes <span class="sort-arrow">&udarr;</span></th>
                        <th class="col-apply">Apply</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        <div class="no-results" id="no-results">No programs match your filters. <a href="#" onclick="clearAllFilters(); return false;">Clear filters</a></div>
    </main>

    <!-- Detail Modal -->
    <div id="detail-modal" class="modal-overlay" style="display:none" role="dialog" aria-modal="true" aria-label="Program Details">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>
            <div id="modal-body"></div>
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
        <small class="shortcuts-hint"><kbd>/</kbd> Search &bull; <kbd>j</kbd><kbd>k</kbd> Navigate &bull; <kbd>Enter</kbd> Details &bull; <kbd>Esc</kbd> Close</small>
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

    // Default sort by App Close (soonest first) unless URL has params
    if (!params.toString()) {{
        var closeHeader = document.querySelector('[data-label="App Close"]');
        if (closeHeader) sortTable(closeHeader);
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
    restripe();
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

        if (window._specialFilter === 'open') {{
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

function toggleColMenu() {{
    var menu = document.getElementById('col-menu');
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}}

// Close column menu when clicking outside
document.addEventListener('click', function(e) {{
    var wrap = document.querySelector('.col-toggle-wrap');
    var menu = document.getElementById('col-menu');
    if (wrap && menu && !wrap.contains(e.target)) {{
        menu.style.display = 'none';
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
    html += '<div class="detail-meta"><span class="stars">' + stars + '</span>';
    html += ' <span class="' + bsnCls + '">' + escHtml(p.bsn_required || 'N/A') + ' BSN</span>';
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
    html += '<div class="checklist-progress">' + done + ' of ' + checklistItems.length + ' complete</div>';
    html += '</div>';

    if (p.application_url) {{
        html += '<div class="detail-actions"><a href="' + escHtml(p.application_url) + '" target="_blank" class="apply-btn-modal">Apply Now &rarr;</a></div>';
    }}

    document.getElementById('modal-body').innerHTML = html;
    openModal('detail-modal');

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
                var progDiv = checklist.parentElement.querySelector('.checklist-progress');
                if (progDiv) progDiv.textContent = checkedCount + ' of ' + allCbs.length + ' complete';
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
}}

function closeModalEl(el) {{
    el.classList.remove('modal-visible');
    document.body.style.overflow = '';
    setTimeout(function() {{ el.style.display = 'none'; }}, 200);
}}

function closeModal() {{
    closeModalEl(document.getElementById('detail-modal'));
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
