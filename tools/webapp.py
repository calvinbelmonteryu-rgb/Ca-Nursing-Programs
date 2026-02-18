#!/usr/bin/env python3
"""
CA New Grad RN Program Tracker — Web Interface

Usage:
    python3 tools/webapp.py              # Start on port 5000
    python3 tools/webapp.py --port 8080  # Custom port
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import csv
import io
import re
from flask import Flask, render_template, request, jsonify, Response
import data_service

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)


@app.context_processor
def utility_functions():
    def sort_link(field):
        """Build query string for sorting, preserving current filters."""
        args = request.args.copy()
        args["sort"] = field
        return "&".join(f"{k}={v}" for k, v in args.items() if v)
    def base_pay(pay_str):
        """Extract just the base hourly rate from verbose pay strings."""
        if not pay_str:
            return "—"
        # Match patterns like "$89.20/hr", "$48-65/hr", "$50.50/hr"
        m = re.match(r'(\$[\d.,]+-?[\d.,]*/hr)', pay_str)
        if m:
            return m.group(1)
        # Match "$62K/yr" style
        m = re.match(r'(\$[\d.,]+K/yr)', pay_str)
        if m:
            return m.group(1)
        # Match "ADN $50.50/hr" style — just grab first dollar amount
        m = re.search(r'(\$[\d.,]+/hr)', pay_str)
        if m:
            return m.group(1)
        return pay_str
    def short_city(city_str):
        """Abbreviate multi-city strings for the table."""
        if not city_str:
            return ""
        # "Multiple (Sacramento, Oakland, ...)" → "Sac, Oak, etc"
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
            # Extract cities from parentheses
            m = re.search(r'\((.+)\)', city_str)
            if not m:
                return "Multi"
            raw = [c.strip().rstrip('.') for c in m.group(1).split(',') if c.strip() != 'etc']
            short = [abbrevs.get(c, c) for c in raw]
            # Show first 2, add "etc" if more
            if len(short) > 2:
                return ', '.join(short[:2]) + ', etc'
            return ', '.join(short)
        # "Los Angeles (Boyle Heights)" → "LA (Boyle Hts)"
        city_str = city_str.replace("Los Angeles", "LA")
        city_str = city_str.replace("Boyle Heights", "Boyle Hts")
        # "Walnut Creek / Concord" → "W Creek / Concord"
        city_str = city_str.replace("Walnut Creek", "W Creek")
        # "Newport Beach / Irvine" → "Newport / Irvine"
        city_str = city_str.replace("Newport Beach", "Newport")
        # "Mountain View / Los Gatos" → "Mtn View / Los Gatos"
        city_str = city_str.replace("Mountain View", "Mtn View")
        # "West Covina / Covina / Glendora" → "W Covina+"
        if city_str.count("/") >= 2:
            first = city_str.split("/")[0].strip()
            first = first.replace("West ", "W ")
            return first + "+"
        # "San Diego / La Jolla" → "SD / La Jolla"
        city_str = city_str.replace("San Diego", "SD")
        city_str = city_str.replace("San Jose", "SJ")
        city_str = city_str.replace("Santa Monica", "S Monica")
        city_str = city_str.replace("Sacramento", "Sac")
        city_str = city_str.replace("San Francisco", "SF")
        return city_str
    return {"sort_link": sort_link, "base_pay": base_pay, "short_city": short_city}


@app.route("/")
@app.route("/programs")
def programs():
    region = request.args.get("region")
    bsn = request.args.get("bsn")
    status = request.args.get("status")
    search = request.args.get("q")
    sort_by = request.args.get("sort", "id")
    cohort = request.args.get("cohort")

    programs = data_service.get_programs(
        region=region, bsn=bsn, status=status, search=search, sort_by=sort_by, cohort=cohort
    )
    regions = data_service.get_regions()
    cities = data_service.get_cities()
    stats = data_service.get_stats()

    return render_template(
        "programs.html",
        programs=programs,
        regions=regions,
        cities=cities,
        stats=stats,
        filters={"region": region or "", "bsn": bsn or "", "status": status or "", "q": search or "", "sort": sort_by, "cohort": cohort or ""},
        statuses=data_service.VALID_STATUSES,
    )


@app.route("/programs/<int:program_id>")
def program_detail(program_id):
    program = data_service.get_program(program_id)
    if not program:
        return "Program not found", 404
    return render_template("detail.html", program=program, statuses=data_service.VALID_STATUSES)


@app.route("/compare")
def compare():
    ids_param = request.args.get("ids", "")
    program_ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
    programs = [data_service.get_program(pid) for pid in program_ids]
    programs = [p for p in programs if p]
    return render_template("compare.html", programs=programs)


@app.route("/timeline")
def timeline():
    from datetime import date as date_type
    programs = data_service.get_programs(sort_by="deadline")
    metadata = data_service.get_metadata()
    today = date_type.today()

    # Timeline range: Feb 2026 through Dec 2026
    timeline_start = date_type(2026, 2, 1)
    timeline_end = date_type(2026, 12, 31)
    total_days = (timeline_end - timeline_start).days

    # Generate month markers
    months = []
    for m in range(2, 13):
        month_start = date_type(2026, m, 1)
        offset_pct = ((month_start - timeline_start).days / total_days) * 100
        months.append({
            "name": month_start.strftime("%b"),
            "offset": round(offset_pct, 1),
        })

    for p in programs:
        app_open = data_service.parse_date(p.get("app_open_date", ""))
        app_close = data_service.parse_date(p.get("app_close_date", ""))
        cohort_date = data_service.parse_date(p.get("cohort_start", ""))
        p["_is_open"] = app_open and app_open <= today and (not app_close or app_close >= today)
        p["_days_left"] = (app_close - today).days if app_close else None

        # Calculate Gantt bar positions
        if app_open and app_open >= timeline_start:
            p["_bar_start"] = round(((app_open - timeline_start).days / total_days) * 100, 1)
        else:
            p["_bar_start"] = None

        if app_open and app_close:
            bar_start_date = max(app_open, timeline_start)
            bar_end_date = min(app_close, timeline_end)
            p["_bar_start"] = round(((bar_start_date - timeline_start).days / total_days) * 100, 1)
            p["_bar_width"] = round(((bar_end_date - bar_start_date).days / total_days) * 100, 1)
            p["_bar_width"] = max(p["_bar_width"], 0.5)  # minimum visible width
        else:
            p["_bar_width"] = None

        if cohort_date and cohort_date >= timeline_start and cohort_date <= timeline_end:
            p["_cohort_pos"] = round(((cohort_date - timeline_start).days / total_days) * 100, 1)
        else:
            p["_cohort_pos"] = None

    # Today marker
    today_pct = round(((today - timeline_start).days / total_days) * 100, 1) if today >= timeline_start else 0

    nclex_date = data_service.parse_date(metadata.get("nclex_target_date", ""))
    if not nclex_date and len(metadata.get("nclex_target_date", "")) == 7:
        nclex_date = data_service.parse_date(metadata["nclex_target_date"] + "-01")
    metadata["_nclex_days"] = (nclex_date - today).days if nclex_date else None
    nclex_pct = round(((nclex_date - timeline_start).days / total_days) * 100, 1) if nclex_date and nclex_date >= timeline_start else None

    return render_template(
        "timeline.html",
        programs=programs,
        metadata=metadata,
        months=months,
        today_pct=today_pct,
        nclex_pct=nclex_pct,
    )


@app.route("/api/programs/<int:program_id>", methods=["PATCH"])
def api_update_program(program_id):
    updates = request.get_json()
    if not updates:
        return jsonify({"error": "No data provided"}), 400

    program = None
    for field, value in updates.items():
        if field == "application_status" and value not in data_service.VALID_STATUSES:
            return jsonify({"error": f"Invalid status: {value}"}), 400
        program = data_service.update_program(program_id, field, value)

    if not program:
        return jsonify({"error": "Program not found"}), 404

    return jsonify({"success": True, "program": program})


@app.route("/api/export/csv")
def export_csv():
    programs = data_service.get_programs()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Hospital", "Program", "Region", "City", "BSN Required",
        "Reputation", "Length (mo)", "Pay Range", "App Open", "App Close",
        "Cohort Start", "Specialties", "Requirements", "Status", "Notes",
        "Application URL"
    ])
    for p in programs:
        writer.writerow([
            p["id"], p["hospital"], p["program_name"], p["region"], p["city"],
            p["bsn_required"], p["reputation"], p["program_length_months"],
            p.get("pay_range", ""), p.get("app_open_date", ""),
            p.get("app_close_date", ""), p.get("cohort_start", ""),
            ", ".join(p.get("specialty_units", [])), p.get("requirements", ""),
            p.get("application_status", "Not Started"),
            p.get("personal_notes", ""), p.get("application_url", "")
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ca_rn_programs.csv"}
    )


if __name__ == "__main__":
    port = 8080
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    print(f"\n  CA New Grad RN Tracker")
    print(f"  http://localhost:{port}\n")
    app.run(debug=True, port=port)
