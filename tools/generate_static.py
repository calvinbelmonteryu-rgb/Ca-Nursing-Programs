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

    nclex_date = metadata.get("nclex_target_date", "")
    nclex_parsed = parse_date(nclex_date)
    if not nclex_parsed and len(nclex_date) == 7:
        nclex_parsed = parse_date(nclex_date + "-01")
    nclex_days = (nclex_parsed - today).days if nclex_parsed else None

    regions = sorted(set(p["region"] for p in programs))
    cities = sorted(set(p["city"] for p in programs))
    statuses = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]

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

        row = f"""<tr data-id="{p['id']}" data-region="{esc(p.get('region',''))}" data-city="{esc(p.get('city',''))}" data-status="{esc(status)}">
<td class="col-check"><input type="checkbox" class="compare-check" value="{p['id']}"></td>
<td class="col-hospital frozen-col"><a href="#{p['id']}">{esc(p['hospital'])}</a></td>
<td class="col-program">{esc(p.get('program_name',''))}</td>
<td class="col-region">{esc(p.get('region',''))}</td>
<td class="col-city" title="{full_city}">{esc(city)}</td>
<td class="col-date">{esc(p.get('app_open_date',''))}</td>
<td class="col-date">{esc(p.get('app_close_date',''))}</td>
<td class="col-date">{esc(p.get('cohort_start',''))}</td>
<td class="col-rep stars">{stars}</td>
<td class="col-pay">{esc(pay)}</td>
<td class="col-len">{p.get('program_length_months','')}mo</td>
<td class="col-specialties">{esc(specs)}</td>
<td class="col-status"><select class="status-select" data-id="{p['id']}">{status_options}</select></td>
<td class="col-notes">{esc(p.get('personal_notes',''))}</td>
<td class="col-apply">{apply_cell}</td>
</tr>"""
        rows_html.append(row)

    region_options = ''.join(f'<option value="{esc(r)}">{esc(r)}</option>' for r in regions)
    city_options = ''.join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in cities)
    status_options_filter = ''.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in statuses)

    nclex_stat = f"<strong>{nclex_days}d</strong>" if nclex_days is not None else nclex_date
    urgent_class = ' stat-highlight-red' if urgent > 0 else ''
    urgent_text = f" ({urgent} urgent)" if urgent > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
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
        </ul>
    </nav>

    <main class="container-fluid sheet-page">
        <div class="stats-bar">
            <span><strong>{total}</strong> programs</span>
            <span class="stats-sep">|</span>
            <span class="stat-highlight-green"><strong>{open_now}</strong> open now</span>
            <span class="stats-sep">|</span>
            <span class="{urgent_class}"><strong>{upcoming}</strong> upcoming{urgent_text}</span>
            <span class="stats-sep">|</span>
            <span>NCLEX: {nclex_stat}</span>
        </div>

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
                <span class="filter-spacer"></span>
                <button type="button" id="compare-btn" disabled onclick="goCompare()">Compare</button>
                <button type="button" onclick="exportCSV()" title="Export CSV">Export</button>
            </div>
        </div>

        <div class="sheet-wrapper">
            <table class="sheet">
                <thead>
                    <tr>
                        <th class="col-check"><input type="checkbox" id="select-all"></th>
                        <th class="col-hospital frozen-col">Hospital</th>
                        <th class="col-program">Program</th>
                        <th class="col-region">Region</th>
                        <th class="col-city">City</th>
                        <th class="col-date">App Open</th>
                        <th class="col-date">App Close</th>
                        <th class="col-date">Cohort</th>
                        <th class="col-rep">Rep</th>
                        <th class="col-pay">Pay</th>
                        <th class="col-len">Len</th>
                        <th class="col-specialties">Specialties</th>
                        <th class="col-status">Status</th>
                        <th class="col-notes">Notes</th>
                        <th class="col-apply">Apply</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
    </main>

    <footer class="container">
        <small>CA New Grad RN Program Tracker &bull; NCLEX Target: May 2026</small>
    </footer>

    <script>
// ===== Static site JS (no backend) =====

const statusClasses = {{
    'Not Started': '',
    'In Progress': 'row-in-progress',
    'Submitted': 'row-submitted',
    'Interview': 'row-interview',
    'Offer': 'row-offer',
    'Rejected': 'row-rejected'
}};

function applyRowStatus(row, status) {{
    Object.values(statusClasses).forEach(function(cls) {{
        if (cls) row.classList.remove(cls);
    }});
    if (statusClasses[status]) row.classList.add(statusClasses[status]);
}}

document.addEventListener('DOMContentLoaded', function() {{
    // Apply initial row colors
    document.querySelectorAll('.status-select').forEach(function(sel) {{
        var row = sel.closest('tr');
        if (row) applyRowStatus(row, sel.value);
    }});

    // Status dropdowns (local only, no backend)
    document.querySelectorAll('.status-select').forEach(function(sel) {{
        sel.addEventListener('change', function() {{
            var row = this.closest('tr');
            if (row) {{
                applyRowStatus(row, this.value);
                row.dataset.status = this.value;
                showToast('Status updated (local only)');
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

    // Search
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    if (searchInput) {{
        searchInput.addEventListener('input', debounce(filterTable, 150));
    }}

    // Filter dropdowns
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function(sel) {{
        sel.addEventListener('change', filterTable);
    }});

    // Keyboard: / to search, Esc to blur
    document.addEventListener('keydown', function(e) {{
        if (e.key === '/' && !isEditing(e.target)) {{
            var si = document.querySelector('.sheet-filters input[type="search"]');
            if (si) {{ e.preventDefault(); si.focus(); si.select(); }}
        }}
        if (e.key === 'Escape') document.activeElement.blur();
    }});

    highlightDeadlines();
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
    var statusSelect = document.querySelector('.sheet-filters select[data-instant="status"]');
    var cohortStatusSelect = document.querySelector('.sheet-filters select[data-instant="cohort-status"]');

    var query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var region = regionSelect ? regionSelect.value : '';
    var city = citySelect ? citySelect.value : '';
    var status = statusSelect ? statusSelect.value : '';
    var cohortStatus = cohortStatusSelect ? cohortStatusSelect.value : '';

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
        if (show && status) {{
            var statusSel = row.querySelector('.status-select');
            if (statusSel && statusSel.value !== status) show = false;
        }}
        if (show && cohortStatus) {{
            var dateCells = row.querySelectorAll('.col-date');
            var cohortCell = dateCells.length >= 3 ? dateCells[2] : null;
            var cohortText = cohortCell ? cohortCell.textContent.trim().toLowerCase() : '';
            var isDate = /^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(cohortText);
            if (cohortStatus === 'released' && !isDate) show = false;
            if (cohortStatus === 'not-released' && (isDate || cohortText.indexOf('rolling') !== -1 || cohortText.indexOf('paused') !== -1)) show = false;
            if (cohortStatus === 'rolling' && cohortText.indexOf('rolling') === -1) show = false;
            if (cohortStatus === 'paused' && cohortText.indexOf('paused') === -1) show = false;
        }}
        row.style.display = show ? '' : 'none';
        if (show) visibleCount++;
    }});

    var countEl = document.querySelector('.sheet-count');
    if (countEl) countEl.textContent = visibleCount + ' of ' + rows.length + ' rows';
}}

function highlightDeadlines() {{
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    document.querySelectorAll('.sheet tbody tr').forEach(function(row) {{
        var dateCells = row.querySelectorAll('.col-date');
        if (dateCells.length >= 2) {{
            var closeCell = dateCells[1];
            var dateStr = closeCell.textContent.trim();
            if (dateStr) {{
                var closeDate = parseDate(dateStr);
                if (closeDate) {{
                    var daysLeft = Math.ceil((closeDate - today) / (1000 * 60 * 60 * 24));
                    if (daysLeft < 0) {{
                        closeCell.innerHTML = dateStr + ' <span class="deadline-past">closed</span>';
                    }} else if (daysLeft <= 7) {{
                        closeCell.innerHTML = dateStr + ' <span class="deadline-urgent">' + daysLeft + 'd</span>';
                        row.classList.add('urgent-row');
                    }} else if (daysLeft <= 14) {{
                        closeCell.innerHTML = dateStr + ' <span class="deadline-warning">' + daysLeft + 'd</span>';
                        row.classList.add('warning-row');
                    }} else if (daysLeft <= 30) {{
                        closeCell.innerHTML = dateStr + ' <span class="deadline-soon">' + daysLeft + 'd</span>';
                    }}
                }}
            }}

            var openCell = dateCells[0];
            var openStr = openCell.textContent.trim();
            if (openStr && dateStr) {{
                var openDate = parseDate(openStr);
                var closeDate2 = parseDate(dateStr);
                if (openDate && closeDate2 && openDate <= today && closeDate2 >= today) {{
                    openCell.innerHTML = openStr + ' <span class="badge-open">OPEN</span>';
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

function updateCompareBtn() {{
    var btn = document.getElementById('compare-btn');
    if (!btn) return;
    var checked = document.querySelectorAll('.compare-check:checked');
    btn.disabled = checked.length < 2;
    btn.textContent = checked.length >= 2 ? 'Compare ' + checked.length : 'Compare';
}}

function goCompare() {{
    showToast('Compare view not available in static version');
}}

function exportCSV() {{
    // Build CSV from table data
    var rows = document.querySelectorAll('.sheet tbody tr');
    var csv = 'Hospital,Program,Region,City,App Open,App Close,Cohort,Rep,Pay,Length,Specialties,Status,Notes\\n';
    rows.forEach(function(row) {{
        var cells = row.querySelectorAll('td');
        if (cells.length >= 14) {{
            var vals = [
                cells[1].textContent.trim(),
                cells[2].textContent.trim(),
                cells[3].textContent.trim(),
                row.dataset.city || cells[4].textContent.trim(),
                cells[5].textContent.trim(),
                cells[6].textContent.trim(),
                cells[7].textContent.trim(),
                cells[8].textContent.trim(),
                cells[9].textContent.trim(),
                cells[10].textContent.trim(),
                cells[11].textContent.trim(),
                cells[12].querySelector('select') ? cells[12].querySelector('select').value : '',
                cells[13].textContent.trim()
            ];
            csv += vals.map(function(v) {{ return '"' + v.replace(/"/g, '""') + '"'; }}).join(',') + '\\n';
        }}
    }});
    var blob = new Blob([csv], {{type: 'text/csv'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'ca_rn_programs.csv';
    a.click();
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
