#!/usr/bin/env python3
"""Generate a modern static HTML site from programs.json for GitHub Pages deployment."""

import json
import os
import re
from datetime import date, datetime

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "programs.json")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")


def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def base_pay(pay_str):
    if not pay_str:
        return ""
    m = re.search(r'\$[\d.,]+/hr', pay_str)
    if m:
        return m.group(0)
    m = re.search(r'\$[\d.,]+', pay_str)
    if m:
        return m.group(0) + "/hr"
    return pay_str


def pay_number(pay_str):
    """Extract a numeric pay value for sorting."""
    if not pay_str:
        return 0
    m = re.search(r'\$([\d,.]+)', pay_str)
    if m:
        return float(m.group(1).replace(',', ''))
    return 0


def short_city(city_str):
    if not city_str:
        return ""
    if city_str.startswith("Multiple"):
        abbrevs = {
            "Sacramento": "Sac", "Oakland": "Oak", "San Jose": "SJ",
            "Santa Rosa": "S Rosa", "Los Angeles": "LA",
            "Orange County": "OC", "San Diego": "SD",
            "Inland Empire": "IE", "Bay Area": "Bay Area",
        }
        m = re.search(r'\((.+)\)', city_str)
        if not m:
            return "Multiple"
        raw = [c.strip().rstrip('.') for c in m.group(1).split(',') if c.strip() != 'etc']
        short = [abbrevs.get(c, c) for c in raw]
        if len(short) > 2:
            return ', '.join(short[:2]) + '+'
        return ', '.join(short)
    replacements = [
        ("Los Angeles", "LA"), ("San Francisco", "SF"), ("San Diego", "SD"),
        ("San Jose", "SJ"), ("Sacramento", "Sac"), ("Mountain View", "Mtn View"),
        ("Walnut Creek", "W Creek"), ("Newport Beach", "Newport"),
        ("Boyle Heights", "Boyle Hts"), ("Santa Monica", "S Monica"),
    ]
    for old, new in replacements:
        city_str = city_str.replace(old, new)
    if city_str.count("/") >= 2:
        return city_str.split("/")[0].strip() + "+"
    return city_str


def esc(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def cohort_status(cohort_str):
    if not cohort_str:
        return "unknown"
    lower = cohort_str.lower()
    if "paused" in lower:
        return "paused"
    if "rolling" in lower:
        return "rolling"
    if re.match(r'^\d{4}-\d{2}-\d{2}', cohort_str):
        return "released"
    return "not-released"


def format_date_short(date_str):
    """Format 2026-03-15 as Mar 15."""
    d = parse_date(date_str)
    if not d:
        return date_str or "—"
    return d.strftime("%b %d")


def generate():
    with open(DATA_FILE) as f:
        data = json.load(f)

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
    statuses = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]

    # Build program cards data as JSON for JS rendering
    programs_json = []
    for p in programs:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        is_open = bool(app_open and app_open <= today and (not app_close or app_close >= today))
        days_left = (app_close - today).days if app_close and app_close >= today else None

        programs_json.append({
            "id": p["id"],
            "hospital": p["hospital"],
            "program_name": p.get("program_name", ""),
            "region": p.get("region", ""),
            "city": p.get("city", ""),
            "city_short": short_city(p.get("city", "")),
            "specialty_units": p.get("specialty_units", []),
            "program_length_months": p.get("program_length_months", ""),
            "cohort_start": p.get("cohort_start", ""),
            "cohort_status": cohort_status(p.get("cohort_start", "")),
            "app_open_date": p.get("app_open_date", ""),
            "app_close_date": p.get("app_close_date", ""),
            "app_open_fmt": format_date_short(p.get("app_open_date", "")),
            "app_close_fmt": format_date_short(p.get("app_close_date", "")),
            "cohort_start_fmt": format_date_short(p.get("cohort_start", "")) if re.match(r'^\d{4}-', p.get("cohort_start", "")) else p.get("cohort_start", ""),
            "bsn_required": p.get("bsn_required", ""),
            "requirements": p.get("requirements", ""),
            "application_url": p.get("application_url", ""),
            "pay_range": p.get("pay_range", ""),
            "pay_short": base_pay(p.get("pay_range", "")),
            "pay_num": pay_number(p.get("pay_range", "")),
            "reputation": p.get("reputation", 0),
            "reputation_notes": p.get("reputation_notes", ""),
            "application_status": p.get("application_status", "Not Started"),
            "personal_notes": p.get("personal_notes", ""),
            "is_open": is_open,
            "days_left": days_left,
        })

    programs_js = json.dumps(programs_json, ensure_ascii=False)
    regions_js = json.dumps(regions)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CA New Grad RN Tracker</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏥</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
{STATIC_CSS}
    </style>
</head>
<body>
    <!-- Top Bar -->
    <header class="topbar">
        <div class="topbar-inner">
            <div class="topbar-brand">
                <span class="brand-icon">🏥</span>
                <span class="brand-text">CA New Grad RN Tracker</span>
            </div>
            <div class="topbar-stats">
                <div class="stat-pill"><span class="stat-num">{total}</span> Programs</div>
                <div class="stat-pill stat-green"><span class="stat-num">{open_now}</span> Open Now</div>
                <div class="stat-pill {'stat-red' if urgent else 'stat-yellow'}"><span class="stat-num">{upcoming}</span> Upcoming{f' ({urgent} urgent)' if urgent else ''}</div>
                <div class="stat-pill stat-blue">NCLEX: <span class="stat-num">{nclex_days}d</span></div>
            </div>
            <div class="topbar-actions">
                <button onclick="setView('cards')" class="view-btn active" id="btn-cards" title="Card View">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
                </button>
                <button onclick="setView('table')" class="view-btn" id="btn-table" title="Table View">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="14" height="3" rx="1"/><rect x="1" y="6" width="14" height="3" rx="1"/><rect x="1" y="11" width="14" height="3" rx="1"/></svg>
                </button>
                <button onclick="exportCSV()" class="btn-export" title="Export CSV">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 12l-4-4h2.5V2h3v6H12L8 12zM2 14h12v1H2z"/></svg>
                    CSV
                </button>
            </div>
        </div>
    </header>

    <!-- Filters -->
    <div class="filter-bar">
        <div class="filter-inner">
            <div class="search-box">
                <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="#94a3b8"><path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/></svg>
                <input type="text" id="search" placeholder="Search hospitals, programs, notes..." autocomplete="off">
            </div>
            <div class="filter-chips">
                <select id="filter-region"><option value="">All Regions</option></select>
                <select id="filter-status"><option value="">All Statuses</option></select>
                <select id="filter-cohort"><option value="">All Cohorts</option><option value="released">Released</option><option value="not-released">Not Released</option><option value="rolling">Rolling</option><option value="paused">Paused</option></select>
                <select id="filter-bsn"><option value="">BSN Req</option><option value="No">ADN OK</option><option value="Yes">BSN Required</option><option value="Preferred">BSN Preferred</option></select>
            </div>
            <div class="sort-group">
                <label>Sort:</label>
                <select id="sort-by">
                    <option value="deadline">Deadline</option>
                    <option value="reputation">Reputation</option>
                    <option value="pay">Pay</option>
                    <option value="name">Name</option>
                    <option value="cohort">Cohort Start</option>
                </select>
            </div>
            <span class="result-count" id="result-count">{total} programs</span>
        </div>
    </div>

    <!-- Main Content -->
    <main id="main-content">
        <div id="cards-view" class="cards-grid"></div>
        <div id="table-view" class="table-view" style="display:none">
            <div class="table-wrapper">
                <table id="program-table">
                    <thead>
                        <tr>
                            <th>Hospital</th>
                            <th>Region</th>
                            <th>City</th>
                            <th>App Open</th>
                            <th>App Close</th>
                            <th>Cohort</th>
                            <th>Rep</th>
                            <th>Pay</th>
                            <th>BSN</th>
                            <th>Length</th>
                            <th>Status</th>
                            <th>Apply</th>
                        </tr>
                    </thead>
                    <tbody id="table-body"></tbody>
                </table>
            </div>
        </div>
    </main>

    <!-- Detail Modal -->
    <div id="modal-overlay" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <div id="modal-content"></div>
        </div>
    </div>

    <!-- Toast -->
    <div id="toast" class="toast"></div>

    <footer>
        <span>CA New Grad RN Program Tracker</span>
        <span class="footer-sep">&bull;</span>
        <span>NCLEX Target: May 2026</span>
        <span class="footer-sep">&bull;</span>
        <span>Updated {today.strftime('%b %d, %Y')}</span>
    </footer>

    <script>
const PROGRAMS = {programs_js};
const REGIONS = {regions_js};
const STATUSES = ["Not Started","In Progress","Submitted","Interview","Offer","Rejected"];
const TODAY = new Date('{today.isoformat()}');

let currentView = 'cards';
let filteredPrograms = [...PROGRAMS];

// Init
document.addEventListener('DOMContentLoaded', function() {{
    // Populate region filter
    const regionSel = document.getElementById('filter-region');
    REGIONS.forEach(r => {{
        const opt = document.createElement('option');
        opt.value = r; opt.textContent = r;
        regionSel.appendChild(opt);
    }});
    // Populate status filter
    const statusSel = document.getElementById('filter-status');
    STATUSES.forEach(s => {{
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s;
        statusSel.appendChild(opt);
    }});

    // Event listeners
    document.getElementById('search').addEventListener('input', debounce(render, 200));
    document.querySelectorAll('.filter-bar select').forEach(s => s.addEventListener('change', render));
    document.getElementById('sort-by').addEventListener('change', render);

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {{
        if (e.key === '/' && !isEditing(e.target)) {{
            e.preventDefault();
            document.getElementById('search').focus();
        }}
        if (e.key === 'Escape') {{
            closeModal();
            document.activeElement.blur();
        }}
    }});

    render();
}});

function debounce(fn, ms) {{
    let t; return function() {{ clearTimeout(t); t = setTimeout(fn, ms); }};
}}
function isEditing(el) {{
    return ['INPUT','TEXTAREA','SELECT'].includes(el.tagName) || el.isContentEditable;
}}

function setView(v) {{
    currentView = v;
    document.getElementById('cards-view').style.display = v === 'cards' ? '' : 'none';
    document.getElementById('table-view').style.display = v === 'table' ? '' : 'none';
    document.getElementById('btn-cards').classList.toggle('active', v === 'cards');
    document.getElementById('btn-table').classList.toggle('active', v === 'table');
    render();
}}

function render() {{
    const q = document.getElementById('search').value.toLowerCase().trim();
    const region = document.getElementById('filter-region').value;
    const status = document.getElementById('filter-status').value;
    const cohort = document.getElementById('filter-cohort').value;
    const bsn = document.getElementById('filter-bsn').value;
    const sortBy = document.getElementById('sort-by').value;

    filteredPrograms = PROGRAMS.filter(p => {{
        if (q) {{
            const text = (p.hospital + ' ' + p.program_name + ' ' + p.city + ' ' + p.region + ' ' + p.personal_notes + ' ' + p.specialty_units.join(' ')).toLowerCase();
            if (!text.includes(q)) return false;
        }}
        if (region && p.region !== region) return false;
        if (status && p.application_status !== status) return false;
        if (cohort && p.cohort_status !== cohort) return false;
        if (bsn && p.bsn_required !== bsn) return false;
        return true;
    }});

    // Sort
    filteredPrograms.sort((a, b) => {{
        if (sortBy === 'deadline') {{
            // Open now first, then by close date, then by open date, then no-date last
            if (a.is_open !== b.is_open) return a.is_open ? -1 : 1;
            const aClose = a.app_close_date || 'z';
            const bClose = b.app_close_date || 'z';
            if (aClose !== bClose) return aClose < bClose ? -1 : 1;
            const aOpen = a.app_open_date || 'z';
            const bOpen = b.app_open_date || 'z';
            return aOpen < bOpen ? -1 : aOpen > bOpen ? 1 : 0;
        }}
        if (sortBy === 'reputation') return b.reputation - a.reputation;
        if (sortBy === 'pay') return b.pay_num - a.pay_num;
        if (sortBy === 'name') return a.hospital.localeCompare(b.hospital);
        if (sortBy === 'cohort') {{
            const aDate = a.cohort_start.match(/^\\d/) ? a.cohort_start : 'z';
            const bDate = b.cohort_start.match(/^\\d/) ? b.cohort_start : 'z';
            return aDate < bDate ? -1 : aDate > bDate ? 1 : 0;
        }}
        return 0;
    }});

    document.getElementById('result-count').textContent = filteredPrograms.length + ' of ' + PROGRAMS.length + ' programs';

    if (currentView === 'cards') renderCards();
    else renderTable();
}}

function urgencyBadge(p) {{
    if (p.is_open) return '<span class="badge badge-open">OPEN NOW</span>';
    if (p.days_left !== null && p.days_left <= 7) return '<span class="badge badge-urgent">' + p.days_left + 'd left</span>';
    if (p.days_left !== null && p.days_left <= 14) return '<span class="badge badge-warning">' + p.days_left + 'd left</span>';
    if (p.days_left !== null && p.days_left <= 30) return '<span class="badge badge-soon">' + p.days_left + 'd left</span>';
    if (p.cohort_status === 'paused') return '<span class="badge badge-paused">PAUSED</span>';
    if (p.cohort_status === 'rolling') return '<span class="badge badge-rolling">ROLLING</span>';
    return '';
}}

function stars(n) {{
    return '<span class="stars">' + '★'.repeat(n) + '<span class="star-empty">' + '★'.repeat(5-n) + '</span></span>';
}}

function bsnBadge(bsn) {{
    if (bsn === 'Yes') return '<span class="bsn-tag bsn-yes">BSN</span>';
    if (bsn === 'Preferred') return '<span class="bsn-tag bsn-pref">BSN Pref</span>';
    if (bsn === 'No') return '<span class="bsn-tag bsn-no">ADN OK</span>';
    return '';
}}

function statusClass(s) {{
    return 'status-' + s.toLowerCase().replace(/\\s+/g, '-');
}}

function renderCards() {{
    const container = document.getElementById('cards-view');
    if (filteredPrograms.length === 0) {{
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><h3>No programs match your filters</h3><p>Try adjusting your search or filters</p></div>';
        return;
    }}
    container.innerHTML = filteredPrograms.map(p => {{
        const specList = p.specialty_units.slice(0, 4).join(', ') + (p.specialty_units.length > 4 ? ' +' + (p.specialty_units.length - 4) : '');
        const cardClass = p.is_open ? 'card card-open' : (p.days_left !== null && p.days_left <= 7 ? 'card card-urgent' : 'card');

        return `<div class="${{cardClass}}" onclick="openDetail(${{p.id}})">
            <div class="card-top">
                <div class="card-header">
                    <h3 class="card-hospital">${{esc(p.hospital)}}</h3>
                    ${{urgencyBadge(p)}}
                </div>
                <div class="card-meta">
                    <span class="meta-region">${{esc(p.region)}}</span>
                    <span class="meta-sep">&bull;</span>
                    <span>${{esc(p.city_short)}}</span>
                </div>
            </div>
            <div class="card-body">
                <div class="card-dates">
                    <div class="date-item">
                        <span class="date-label">App Window</span>
                        <span class="date-value">${{p.app_open_date ? esc(p.app_open_fmt) + ' → ' + esc(p.app_close_fmt) : '<span class=\\"tbd\\">TBD</span>'}}</span>
                    </div>
                    <div class="date-item">
                        <span class="date-label">Cohort Start</span>
                        <span class="date-value">${{esc(p.cohort_start_fmt) || '<span class=\\"tbd\\">TBD</span>'}}</span>
                    </div>
                </div>
                <div class="card-stats">
                    <div class="card-stat">
                        ${{stars(p.reputation)}}
                    </div>
                    <div class="card-stat">
                        <span class="pay-amount">${{esc(p.pay_short) || '—'}}</span>
                    </div>
                    <div class="card-stat">
                        ${{bsnBadge(p.bsn_required)}}
                    </div>
                    <div class="card-stat">
                        <span class="length-badge">${{p.program_length_months}}mo</span>
                    </div>
                </div>
                <div class="card-specs">${{esc(specList)}}</div>
            </div>
            <div class="card-footer">
                ${{p.application_url ? '<a href="' + esc(p.application_url) + '" target="_blank" class="btn-apply" onclick="event.stopPropagation()">Apply →</a>' : '<span class="btn-apply btn-disabled">No Link</span>'}}
            </div>
        </div>`;
    }}).join('');
}}

function renderTable() {{
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = filteredPrograms.map(p => {{
        const rowClass = p.is_open ? 'row-open' : (p.days_left !== null && p.days_left <= 7 ? 'row-urgent' : '');
        return `<tr class="${{rowClass}}" onclick="openDetail(${{p.id}})">
            <td class="td-hospital">${{esc(p.hospital)}}</td>
            <td>${{esc(p.region)}}</td>
            <td>${{esc(p.city_short)}}</td>
            <td class="td-date">${{esc(p.app_open_fmt)}}</td>
            <td class="td-date">${{esc(p.app_close_fmt)}} ${{urgencyBadge(p)}}</td>
            <td class="td-date">${{esc(p.cohort_start_fmt)}}</td>
            <td>${{stars(p.reputation)}}</td>
            <td class="td-pay">${{esc(p.pay_short)}}</td>
            <td>${{bsnBadge(p.bsn_required)}}</td>
            <td>${{p.program_length_months}}mo</td>
            <td><span class="status-chip ${{statusClass(p.application_status)}}">${{esc(p.application_status)}}</span></td>
            <td>${{p.application_url ? '<a href="' + esc(p.application_url) + '" target="_blank" class="link-apply" onclick="event.stopPropagation()">Apply →</a>' : '—'}}</td>
        </tr>`;
    }}).join('');
}}

function esc(s) {{
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}}

function openDetail(id) {{
    const p = PROGRAMS.find(x => x.id === id);
    if (!p) return;
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');

    const specTags = p.specialty_units.map(s => '<span class="spec-tag">' + esc(s) + '</span>').join('');
    const notesHtml = esc(p.personal_notes).replace(/\\n/g, '<br>');
    const reqHtml = esc(p.requirements).replace(/\\n/g, '<br>');

    content.innerHTML = `
        <div class="detail-top">
            <div>
                <h2 class="detail-hospital">${{esc(p.hospital)}}</h2>
                <p class="detail-program">${{esc(p.program_name)}}</p>
                <div class="detail-location">
                    <span class="meta-region">${{esc(p.region)}}</span>
                    <span class="meta-sep">&bull;</span>
                    <span>${{esc(p.city)}}</span>
                </div>
            </div>
            <div class="detail-right">
                ${{urgencyBadge(p)}}
                ${{stars(p.reputation)}}
            </div>
        </div>

        <div class="detail-grid">
            <div class="detail-card-section">
                <h4>Application Timeline</h4>
                <div class="detail-row"><span class="detail-label">App Opens</span><span class="detail-val">${{p.app_open_date ? esc(p.app_open_fmt) + ' (' + esc(p.app_open_date) + ')' : 'TBD'}}</span></div>
                <div class="detail-row"><span class="detail-label">App Closes</span><span class="detail-val">${{p.app_close_date ? esc(p.app_close_fmt) + ' (' + esc(p.app_close_date) + ')' : 'TBD'}}</span></div>
                <div class="detail-row"><span class="detail-label">Cohort Start</span><span class="detail-val">${{esc(p.cohort_start) || 'TBD'}}</span></div>
                <div class="detail-row"><span class="detail-label">Length</span><span class="detail-val">${{p.program_length_months}} months</span></div>
            </div>
            <div class="detail-card-section">
                <h4>Details</h4>
                <div class="detail-row"><span class="detail-label">Pay</span><span class="detail-val pay-highlight">${{esc(p.pay_range) || '—'}}</span></div>
                <div class="detail-row"><span class="detail-label">BSN</span><span class="detail-val">${{bsnBadge(p.bsn_required)}} ${{esc(p.bsn_required)}}</span></div>
                <div class="detail-row"><span class="detail-label">Reputation</span><span class="detail-val">${{stars(p.reputation)}} ${{p.reputation_notes ? '<span class="rep-note">' + esc(p.reputation_notes) + '</span>' : ''}}</span></div>
            </div>
        </div>

        <div class="detail-section">
            <h4>Specialties</h4>
            <div class="spec-tags">${{specTags}}</div>
        </div>

        <div class="detail-section">
            <h4>Requirements</h4>
            <p class="detail-text">${{reqHtml || '—'}}</p>
        </div>

        <div class="detail-section">
            <h4>Notes</h4>
            <p class="detail-text">${{notesHtml || '—'}}</p>
        </div>

        <div class="detail-actions">
            ${{p.application_url ? '<a href="' + esc(p.application_url) + '" target="_blank" class="btn-apply-large">Apply Now →</a>' : ''}}
        </div>
    `;
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
}}

function closeModal(e) {{
    if (e && e.target !== document.getElementById('modal-overlay')) return;
    document.getElementById('modal-overlay').classList.remove('open');
    document.body.style.overflow = '';
}}

function exportCSV() {{
    let csv = 'Hospital,Program,Region,City,App Open,App Close,Cohort Start,Reputation,Pay,BSN,Length,Status,URL,Notes\\n';
    PROGRAMS.forEach(p => {{
        const vals = [p.hospital, p.program_name, p.region, p.city, p.app_open_date, p.app_close_date, p.cohort_start, p.reputation, p.pay_range, p.bsn_required, p.program_length_months + 'mo', p.application_status, p.application_url, p.personal_notes];
        csv += vals.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',') + '\\n';
    }});
    const blob = new Blob([csv], {{type: 'text/csv'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'ca_rn_programs.csv';
    a.click();
    showToast('CSV exported');
}}

function showToast(msg) {{
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
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


# ===== EMBEDDED CSS =====
STATIC_CSS = """
/* ===== RESET & BASE ===== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg: #0f172a;
    --bg-card: #1e293b;
    --bg-card-hover: #263548;
    --bg-surface: #1a2332;
    --border: #334155;
    --border-light: #1e293b;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --text-dim: #64748b;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --green: #22c55e;
    --red: #ef4444;
    --yellow: #f59e0b;
    --purple: #8b5cf6;
    --orange: #f97316;
    --radius: 12px;
    --radius-sm: 8px;
}

body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    min-height: 100vh;
}

/* ===== TOP BAR ===== */
.topbar {
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
}

.topbar-inner {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
}

.topbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-right: auto;
}

.brand-icon { font-size: 1.4rem; }
.brand-text { font-weight: 700; font-size: 1.05rem; letter-spacing: -0.02em; }

.topbar-stats {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.stat-pill {
    background: rgba(255,255,255,0.06);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    color: var(--text-muted);
    white-space: nowrap;
}

.stat-pill .stat-num { font-weight: 700; color: var(--text); }
.stat-green .stat-num { color: var(--green); }
.stat-red .stat-num { color: var(--red); }
.stat-yellow .stat-num { color: var(--yellow); }
.stat-blue .stat-num { color: var(--accent); }

.topbar-actions {
    display: flex;
    gap: 6px;
    align-items: center;
}

.view-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s;
}

.view-btn:hover { background: rgba(255,255,255,0.06); color: var(--text); }
.view-btn.active { background: var(--accent); border-color: var(--accent); color: white; }

.btn-export {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    gap: 5px;
    transition: all 0.15s;
}

.btn-export:hover { background: rgba(255,255,255,0.06); color: var(--text); }

/* ===== FILTER BAR ===== */
.filter-bar {
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    padding: 10px 0;
    position: sticky;
    top: 53px;
    z-index: 99;
}

.filter-inner {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.search-box {
    position: relative;
    flex: 1;
    min-width: 200px;
    max-width: 320px;
}

.search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
}

.search-box input {
    width: 100%;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 7px 12px 7px 34px;
    color: var(--text);
    font-size: 0.82rem;
    outline: none;
    transition: border-color 0.15s;
}

.search-box input:focus { border-color: var(--accent); }
.search-box input::placeholder { color: var(--text-dim); }

.filter-chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}

.filter-chips select, .sort-group select {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
    color: var(--text);
    font-size: 0.78rem;
    cursor: pointer;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    padding-right: 26px;
}

.filter-chips select:focus, .sort-group select:focus { border-color: var(--accent); }

.sort-group {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
}

.sort-group label { font-size: 0.78rem; color: var(--text-dim); }

.result-count {
    font-size: 0.75rem;
    color: var(--text-dim);
    white-space: nowrap;
}

/* ===== CARDS GRID ===== */
main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
}

.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
}

.card:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}

.card-open {
    border-color: var(--green);
    box-shadow: 0 0 0 1px var(--green), 0 0 20px rgba(34,197,94,0.1);
}

.card-urgent {
    border-color: var(--red);
    box-shadow: 0 0 0 1px var(--red), 0 0 20px rgba(239,68,68,0.1);
}

.card-top { padding: 16px 16px 0; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.card-hospital { font-size: 0.95rem; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; }
.card-meta { display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 0.78rem; color: var(--text-muted); }
.meta-region { background: rgba(59,130,246,0.15); color: var(--accent); padding: 1px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 600; }
.meta-sep { color: var(--text-dim); }

.card-body { padding: 12px 16px; flex: 1; }

.card-dates {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
}

.date-item { display: flex; flex-direction: column; gap: 2px; }
.date-label { font-size: 0.68rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.date-value { font-size: 0.82rem; font-weight: 500; }
.tbd { color: var(--text-dim); font-style: italic; }

.card-stats {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}

.card-stat { display: flex; align-items: center; }

.stars { color: var(--yellow); font-size: 0.8rem; letter-spacing: 1px; }
.star-empty { color: var(--text-dim); opacity: 0.3; }

.pay-amount { font-size: 0.82rem; font-weight: 700; color: var(--green); }
.length-badge { font-size: 0.72rem; color: var(--text-muted); background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px; }

.card-specs { font-size: 0.72rem; color: var(--text-dim); line-height: 1.4; }

.card-footer {
    padding: 0 16px 16px;
    margin-top: auto;
}

.btn-apply {
    display: block;
    text-align: center;
    background: var(--accent);
    color: white;
    text-decoration: none;
    padding: 8px 16px;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    font-weight: 600;
    transition: background 0.15s;
}

.btn-apply:hover { background: var(--accent-hover); }
.btn-disabled { background: var(--border); color: var(--text-dim); cursor: default; }

/* ===== BADGES ===== */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.68rem;
    font-weight: 700;
    white-space: nowrap;
    letter-spacing: 0.02em;
}

.badge-open { background: rgba(34,197,94,0.2); color: var(--green); }
.badge-urgent { background: rgba(239,68,68,0.2); color: var(--red); animation: pulse 2s infinite; }
.badge-warning { background: rgba(249,115,22,0.2); color: var(--orange); }
.badge-soon { background: rgba(59,130,246,0.2); color: var(--accent); }
.badge-paused { background: rgba(100,116,139,0.2); color: var(--text-dim); }
.badge-rolling { background: rgba(139,92,246,0.2); color: var(--purple); }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

.bsn-tag {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 10px;
    font-size: 0.68rem;
    font-weight: 600;
}

.bsn-yes { background: rgba(239,68,68,0.15); color: #fca5a5; }
.bsn-pref { background: rgba(249,115,22,0.15); color: #fdba74; }
.bsn-no { background: rgba(34,197,94,0.15); color: #86efac; }

.status-chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.72rem;
    font-weight: 600;
}

.status-not-started { background: rgba(100,116,139,0.2); color: var(--text-dim); }
.status-in-progress { background: rgba(249,115,22,0.2); color: var(--orange); }
.status-submitted { background: rgba(59,130,246,0.2); color: var(--accent); }
.status-interview { background: rgba(139,92,246,0.2); color: var(--purple); }
.status-offer { background: rgba(34,197,94,0.2); color: var(--green); }
.status-rejected { background: rgba(239,68,68,0.2); color: var(--red); }

/* ===== TABLE VIEW ===== */
.table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

#program-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}

#program-table th {
    background: var(--bg-surface);
    padding: 10px 12px;
    text-align: left;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
}

#program-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-light);
    vertical-align: middle;
}

#program-table tbody tr {
    cursor: pointer;
    transition: background 0.1s;
}

#program-table tbody tr:hover { background: rgba(59,130,246,0.08); }
.row-open { background: rgba(34,197,94,0.06) !important; }
.row-urgent { background: rgba(239,68,68,0.06) !important; }

.td-hospital { font-weight: 600; min-width: 180px; }
.td-date { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.76rem; white-space: nowrap; }
.td-pay { font-weight: 600; color: var(--green); white-space: nowrap; }

.link-apply {
    color: var(--accent);
    text-decoration: none;
    font-weight: 600;
    font-size: 0.78rem;
}
.link-apply:hover { text-decoration: underline; }

/* ===== MODAL ===== */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    backdrop-filter: blur(4px);
    z-index: 200;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 40px 20px;
    overflow-y: auto;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
}

.modal-overlay.open { opacity: 1; pointer-events: all; }

.modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    max-width: 720px;
    width: 100%;
    padding: 28px;
    position: relative;
    transform: translateY(20px);
    transition: transform 0.2s;
}

.modal-overlay.open .modal { transform: translateY(0); }

.modal-close {
    position: absolute;
    top: 16px;
    right: 16px;
    background: rgba(255,255,255,0.06);
    border: none;
    color: var(--text-muted);
    font-size: 1.5rem;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
}

.modal-close:hover { background: rgba(255,255,255,0.12); color: var(--text); }

.detail-top { margin-bottom: 24px; display: flex; justify-content: space-between; gap: 16px; }
.detail-hospital { font-size: 1.3rem; font-weight: 800; letter-spacing: -0.02em; }
.detail-program { color: var(--text-muted); font-size: 0.88rem; margin-top: 2px; }
.detail-location { display: flex; align-items: center; gap: 6px; margin-top: 6px; font-size: 0.82rem; color: var(--text-muted); }
.detail-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }

.detail-card-section {
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px;
}

.detail-card-section h4 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    margin-bottom: 12px;
}

.detail-row { display: flex; justify-content: space-between; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); gap: 12px; }
.detail-row:last-child { border-bottom: none; }
.detail-label { font-size: 0.78rem; color: var(--text-dim); flex-shrink: 0; }
.detail-val { font-size: 0.82rem; text-align: right; }

.pay-highlight { color: var(--green); font-weight: 600; }
.rep-note { display: block; font-size: 0.75rem; color: var(--text-dim); margin-top: 4px; text-align: right; line-height: 1.4; }

.detail-section { margin-bottom: 20px; }
.detail-section h4 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); margin-bottom: 8px; }

.spec-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.spec-tag { background: rgba(59,130,246,0.12); color: var(--accent); padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 500; }

.detail-text { font-size: 0.82rem; color: var(--text-muted); line-height: 1.6; }

.detail-actions { padding-top: 16px; border-top: 1px solid var(--border); }
.btn-apply-large {
    display: inline-block;
    background: var(--accent);
    color: white;
    text-decoration: none;
    padding: 12px 28px;
    border-radius: var(--radius-sm);
    font-size: 0.92rem;
    font-weight: 700;
    transition: background 0.15s;
}
.btn-apply-large:hover { background: var(--accent-hover); }

/* ===== EMPTY STATE ===== */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-dim); }
.empty-icon { font-size: 3rem; margin-bottom: 16px; }
.empty-state h3 { color: var(--text-muted); margin-bottom: 6px; }

/* ===== TOAST ===== */
.toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 20px;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
    z-index: 300;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s;
    pointer-events: none;
}

.toast.show { opacity: 1; transform: translateY(0); }

/* ===== FOOTER ===== */
footer {
    text-align: center;
    padding: 28px 20px;
    color: var(--text-dim);
    font-size: 0.75rem;
    border-top: 1px solid var(--border);
    margin-top: 40px;
    display: flex;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
}

.footer-sep { color: var(--text-dim); }

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
    .topbar-inner { gap: 10px; }
    .topbar-stats { display: none; }
    .cards-grid { grid-template-columns: 1fr; }
    .filter-inner { gap: 8px; }
    .search-box { max-width: none; }
    .detail-grid { grid-template-columns: 1fr; }
    .modal { padding: 20px; }
    .detail-top { flex-direction: column; }
    .detail-right { flex-direction: row; align-items: center; }
}

@media (max-width: 480px) {
    .filter-chips { display: none; }
    .sort-group { display: none; }
    main { padding: 12px; }
    .cards-grid { gap: 10px; }
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

/* ===== SELECT OPTION STYLING ===== */
select option { background: var(--bg-card); color: var(--text); }
"""


if __name__ == "__main__":
    generate()
