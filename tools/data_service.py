#!/usr/bin/env python3
"""
Shared data layer for CA New Grad RN Program Tracker.
Used by both the CLI (program_tracker.py) and the web app (webapp.py).
"""

import json
import os
from datetime import datetime, date

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "programs.json")

VALID_STATUSES = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    data["metadata"]["last_updated"] = date.today().isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def get_metadata():
    data = load_data()
    return data["metadata"]


def get_program(program_id):
    data = load_data()
    return next((p for p in data["programs"] if p["id"] == program_id), None)


def get_programs(region=None, bsn=None, status=None, search=None, sort_by="id", cohort=None):
    data = load_data()
    programs = data["programs"]

    if region:
        programs = [p for p in programs if region.lower() in p["region"].lower()]

    if bsn:
        if bsn.lower() == "no":
            programs = [p for p in programs if p["bsn_required"] != "Yes"]
        elif bsn.lower() == "yes":
            programs = [p for p in programs if p["bsn_required"] == "Yes"]

    if status:
        programs = [p for p in programs if p.get("application_status", "Not Started") == status]

    if cohort:
        filtered = []
        for p in programs:
            cohort_str = p.get("cohort_start", "")
            if not cohort_str:
                continue
            cohort_date = parse_date(cohort_str)
            if cohort == "jul-sep-2026":
                if cohort_date and cohort_date.year == 2026 and 7 <= cohort_date.month <= 9:
                    filtered.append(p)
                elif any(m in cohort_str.lower() for m in ["jul", "aug", "sep", "summer 2026", "july", "august", "september"]):
                    filtered.append(p)
            elif cohort == "q4-2026":
                if cohort_date and cohort_date.year == 2026 and 10 <= cohort_date.month <= 12:
                    filtered.append(p)
                elif any(m in cohort_str.lower() for m in ["oct", "nov", "dec", "fall 2026"]):
                    filtered.append(p)
        programs = filtered

    if search:
        keyword = search.lower()
        filtered = []
        for p in programs:
            searchable = " ".join([
                str(p.get("hospital", "")),
                str(p.get("program_name", "")),
                str(p.get("region", "")),
                str(p.get("city", "")),
                " ".join(p.get("specialty_units", [])),
                str(p.get("requirements", "")),
                str(p.get("reputation_notes", "")),
                str(p.get("personal_notes", "")),
                str(p.get("pay_range", "")),
            ]).lower()
            if keyword in searchable:
                filtered.append(p)
        programs = filtered

    if sort_by == "deadline":
        programs.sort(key=lambda p: parse_date(p.get("app_close_date", "")) or date(9999, 12, 31))
    elif sort_by == "reputation":
        programs.sort(key=lambda p: p.get("reputation", 0), reverse=True)
    elif sort_by == "pay":
        programs.sort(key=lambda p: p.get("pay_range", ""), reverse=True)
    elif sort_by == "hospital":
        programs.sort(key=lambda p: p.get("hospital", "").lower())

    return programs


def get_regions():
    data = load_data()
    regions = sorted(set(p["region"] for p in data["programs"]))
    return regions


def get_cities():
    data = load_data()
    cities = sorted(set(p["city"] for p in data["programs"]))
    return cities


def update_program(program_id, field, value):
    data = load_data()
    program = next((p for p in data["programs"] if p["id"] == program_id), None)
    if not program:
        return None

    if field not in program:
        return None

    if isinstance(program[field], list):
        if isinstance(value, str):
            program[field] = [v.strip() for v in value.split(",")]
        else:
            program[field] = value
    elif isinstance(program[field], int):
        program[field] = int(value)
    else:
        program[field] = value

    program["last_updated"] = date.today().isoformat()
    save_data(data)
    return program


def get_stats():
    data = load_data()
    programs = data["programs"]
    total = len(programs)
    today = date.today()

    if total == 0:
        return {"total": 0}

    regions = {}
    for p in programs:
        r = p["region"]
        regions[r] = regions.get(r, 0) + 1

    statuses = {}
    for p in programs:
        s = p.get("application_status", "Not Started")
        statuses[s] = statuses.get(s, 0) + 1

    bsn_yes = sum(1 for p in programs if p["bsn_required"] == "Yes")
    bsn_pref = sum(1 for p in programs if p["bsn_required"] == "Preferred")
    bsn_no = sum(1 for p in programs if p["bsn_required"] == "No")

    avg_reputation = sum(p.get("reputation", 0) for p in programs) / total
    top_tier = sum(1 for p in programs if p.get("reputation", 0) >= 4)

    upcoming_count = 0
    urgent_count = 0
    open_now = 0
    for p in programs:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        if app_close and app_close >= today:
            upcoming_count += 1
            if (app_close - today).days <= 14:
                urgent_count += 1
        if app_open and app_open <= today and (not app_close or app_close >= today):
            open_now += 1

    nclex_date = data["metadata"].get("nclex_target_date", "")
    nclex_days_left = None
    if nclex_date:
        nclex_parsed = parse_date(nclex_date)
        if not nclex_parsed and len(nclex_date) == 7:
            # Handle "YYYY-MM" format — assume 1st of month
            nclex_parsed = parse_date(nclex_date + "-01")
        if nclex_parsed:
            nclex_days_left = (nclex_parsed - today).days

    return {
        "total": total,
        "regions": dict(sorted(regions.items(), key=lambda x: x[1], reverse=True)),
        "statuses": statuses,
        "bsn": {"yes": bsn_yes, "preferred": bsn_pref, "no": bsn_no},
        "avg_reputation": round(avg_reputation, 1),
        "top_tier": top_tier,
        "upcoming": upcoming_count,
        "urgent": urgent_count,
        "open_now": open_now,
        "nclex_date": nclex_date,
        "nclex_days_left": nclex_days_left,
        "today": today.isoformat(),
    }


def get_upcoming():
    data = load_data()
    today = date.today()
    upcoming = []

    for p in data["programs"]:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        is_open = app_open and app_open <= today and (not app_close or app_close >= today)

        if app_close and app_close >= today:
            days_left = (app_close - today).days
            upcoming.append({
                "id": p["id"],
                "hospital": p["hospital"],
                "app_close": p["app_close_date"],
                "days_left": days_left,
                "status": p.get("application_status", "Not Started"),
                "is_open": is_open,
                "application_url": p.get("application_url", ""),
            })

    upcoming.sort(key=lambda x: x["days_left"])
    return upcoming


def get_action_items():
    """Generate priority action items based on current program data."""
    data = load_data()
    today = date.today()
    actions = []

    for p in data["programs"]:
        status = p.get("application_status", "Not Started")
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        is_open = app_open and app_open <= today and (not app_close or app_close >= today)

        # Apps open NOW that haven't been started
        if is_open and status == "Not Started":
            days_left = (app_close - today).days if app_close else None
            close_str = p.get('app_close_date', '')
            if days_left is not None:
                detail = f"App closes {close_str} ({days_left}d left)"
            elif close_str:
                detail = f"App closes {close_str}"
            else:
                detail = "Application is open — no close date listed"
            actions.append({
                "priority": "critical" if days_left and days_left <= 5 else "high",
                "action": f"Apply to {p['hospital']}",
                "detail": detail,
                "program_id": p["id"],
                "url": p.get("application_url", ""),
                "sort_key": days_left if days_left is not None else 50,
            })

        # Apps opening within 14 days — prepare
        if app_open and not is_open and 0 < (app_open - today).days <= 14 and status == "Not Started":
            days_until = (app_open - today).days
            actions.append({
                "priority": "medium",
                "action": f"Prepare for {p['hospital']}",
                "detail": f"App opens in {days_until}d ({p.get('app_open_date', '')})",
                "program_id": p["id"],
                "url": "",
                "sort_key": 100 + days_until,
            })

        # Submitted but no follow-up in 30+ days
        if status == "Submitted" and p.get("last_updated"):
            last = parse_date(p["last_updated"])
            if last and (today - last).days > 30:
                actions.append({
                    "priority": "low",
                    "action": f"Follow up with {p['hospital']}",
                    "detail": f"Submitted {(today - last).days}d ago, no update",
                    "program_id": p["id"],
                    "url": "",
                    "sort_key": 500,
                })

    actions.sort(key=lambda a: a["sort_key"])
    return actions
