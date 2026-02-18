#!/usr/bin/env python3
"""
CA New Grad RN Program Tracker - Core Tool

Usage:
    python tools/program_tracker.py view                    # View all programs (table)
    python tools/program_tracker.py view --sort deadline    # Sort by app close date
    python tools/program_tracker.py view --sort reputation  # Sort by reputation (best first)
    python tools/program_tracker.py view --region "Bay Area" # Filter by region
    python tools/program_tracker.py view --bsn no           # Show ADN-friendly programs
    python tools/program_tracker.py compact                 # Compact one-line-per-program view
    python tools/program_tracker.py compact --sort reputation
    python tools/program_tracker.py upcoming                # Upcoming deadlines & info sessions
    python tools/program_tracker.py detail <id>             # Full details for one program
    python tools/program_tracker.py compare <id> <id> ...   # Side-by-side comparison
    python tools/program_tracker.py search <keyword>        # Search programs by keyword
    python tools/program_tracker.py add                     # Add a new program (interactive)
    python tools/program_tracker.py update <id> <field> <value>  # Update a field
    python tools/program_tracker.py status <id> <status>    # Update application status
    python tools/program_tracker.py stats                   # Summary statistics
    python tools/program_tracker.py timeline                # Visual timeline of key dates
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from data_service import load_data, save_data, parse_date


def truncate(text, length=30):
    text = str(text)
    return text[:length-2] + ".." if len(text) > length else text


def reputation_stars(rating):
    return "★" * rating + "☆" * (5 - rating)


def view_programs(data, sort_by="id", region=None, bsn_filter=None):
    programs = data["programs"]

    if region:
        programs = [p for p in programs if region.lower() in p["region"].lower()]

    if bsn_filter:
        if bsn_filter.lower() == "no":
            programs = [p for p in programs if p["bsn_required"] != "Yes"]
        elif bsn_filter.lower() == "yes":
            programs = [p for p in programs if p["bsn_required"] == "Yes"]

    if sort_by == "deadline":
        def deadline_key(p):
            d = parse_date(p.get("app_close_date", ""))
            return d if d else date(9999, 12, 31)
        programs.sort(key=deadline_key)
    elif sort_by == "reputation":
        programs.sort(key=lambda p: p.get("reputation", 0), reverse=True)
    elif sort_by == "pay":
        programs.sort(key=lambda p: p.get("pay_range", ""), reverse=True)

    # Print header
    print(f"\n{'ID':>3}  {'Hospital':<28} {'Region':<14} {'BSN':<5} {'Rep':>5}  {'Program Len':>6}  {'App Close':<12} {'Status':<12}")
    print("-" * 110)

    for p in programs:
        print(
            f"{p['id']:>3}  "
            f"{truncate(p['hospital'], 28):<28} "
            f"{truncate(p['region'], 14):<14} "
            f"{p['bsn_required']:<5} "
            f"{reputation_stars(p.get('reputation', 0)):>5}  "
            f"{str(p.get('program_length_months', '?')) + 'mo':>6}  "
            f"{p.get('app_close_date', 'TBD'):<12} "
            f"{p.get('application_status', 'Not Started'):<12}"
        )

    print(f"\nTotal: {len(programs)} programs")


def view_detail(data, program_id):
    program = next((p for p in data["programs"] if p["id"] == program_id), None)
    if not program:
        print(f"No program found with ID {program_id}")
        return

    print(f"\n{'=' * 60}")
    print(f"  {program['hospital']}")
    print(f"  {program['program_name']}")
    print(f"{'=' * 60}")
    print(f"  Region:           {program['region']}")
    print(f"  City:             {program['city']}")
    print(f"  BSN Required:     {program['bsn_required']}")
    print(f"  Program Length:   {program['program_length_months']} months")
    print(f"  Reputation:       {reputation_stars(program.get('reputation', 0))} ({program.get('reputation', 0)}/5)")
    print(f"  Pay Range:        {program.get('pay_range', 'Unknown')}")
    print()
    print(f"  Specialties:      {', '.join(program.get('specialty_units', []))}")
    print(f"  Requirements:     {program.get('requirements', 'N/A')}")
    print()
    print(f"  Cohort Start:     {program.get('cohort_start', 'TBD')}")
    print(f"  Info Sessions:    {', '.join(program.get('info_session_dates', [])) or 'TBD'}")
    print(f"  App Open:         {program.get('app_open_date', 'TBD')}")
    print(f"  App Close:        {program.get('app_close_date', 'TBD')}")
    print(f"  Application URL:  {program.get('application_url', 'N/A')}")
    print()
    print(f"  Status:           {program.get('application_status', 'Not Started')}")
    print(f"  Reputation Notes: {program.get('reputation_notes', '')}")
    print(f"  Personal Notes:   {program.get('personal_notes', '') or '(none)'}")
    print(f"  Last Updated:     {program.get('last_updated', 'Unknown')}")
    print(f"{'=' * 60}")


def upcoming_deadlines(data):
    today = date.today()
    print(f"\n--- Upcoming Deadlines (as of {today.isoformat()}) ---\n")

    # Info sessions
    sessions = []
    for p in data["programs"]:
        for s in p.get("info_session_dates", []):
            d = parse_date(s)
            if d and d >= today:
                sessions.append((d, p["hospital"], p["id"]))
    sessions.sort()

    if sessions:
        print("INFO SESSIONS:")
        for d, hospital, pid in sessions:
            days_away = (d - today).days
            print(f"  {d.isoformat():<12} ({days_away:>3}d away)  {hospital} [ID:{pid}]")
    else:
        print("INFO SESSIONS: None scheduled yet — dates need to be researched")

    # Application deadlines
    deadlines = []
    for p in data["programs"]:
        close = parse_date(p.get("app_close_date", ""))
        if close and close >= today:
            deadlines.append((close, p["hospital"], p["id"], p.get("application_status", "Not Started")))
    deadlines.sort()

    print()
    if deadlines:
        print("APPLICATION DEADLINES:")
        for d, hospital, pid, status in deadlines:
            days_away = (d - today).days
            urgency = " ⚠️ URGENT" if days_away <= 7 else ""
            print(f"  {d.isoformat():<12} ({days_away:>3}d away)  {hospital} [ID:{pid}] — {status}{urgency}")
    else:
        print("APPLICATION DEADLINES: None set yet — dates need to be researched")

    print()


def update_field(data, program_id, field, value):
    program = next((p for p in data["programs"] if p["id"] == program_id), None)
    if not program:
        print(f"No program found with ID {program_id}")
        return

    if field not in program:
        print(f"Unknown field: {field}")
        print(f"Valid fields: {', '.join(program.keys())}")
        return

    # Handle list fields
    if isinstance(program[field], list):
        if value.startswith("+"):
            program[field].append(value[1:])
            print(f"Added '{value[1:]}' to {field}")
        elif value.startswith("-"):
            try:
                program[field].remove(value[1:])
                print(f"Removed '{value[1:]}' from {field}")
            except ValueError:
                print(f"'{value[1:]}' not found in {field}")
                return
        else:
            program[field] = [v.strip() for v in value.split(",")]
            print(f"Set {field} to: {program[field]}")
    elif isinstance(program[field], int):
        try:
            program[field] = int(value)
        except ValueError:
            print(f"Field '{field}' requires an integer value")
            return
        print(f"Updated {field} to: {value}")
    else:
        program[field] = value
        print(f"Updated {field} to: {value}")

    program["last_updated"] = date.today().isoformat()
    save_data(data)
    print("Data saved.")


def update_status(data, program_id, status):
    valid_statuses = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]
    if status not in valid_statuses:
        print(f"Invalid status: {status}")
        print(f"Valid statuses: {', '.join(valid_statuses)}")
        return
    update_field(data, program_id, "application_status", status)


def add_program(data):
    next_id = max(p["id"] for p in data["programs"]) + 1 if data["programs"] else 1

    print("\n--- Add New Program ---")
    hospital = input("Hospital name: ").strip()
    program_name = input("Program name: ").strip() or "New Graduate RN Residency"
    region = input("Region (NorCal/Bay Area/Central Valley/SoCal): ").strip()
    city = input("City: ").strip()
    bsn = input("BSN required? (Yes/No/Preferred): ").strip() or "Preferred"
    url = input("Application URL: ").strip()

    new_program = {
        "id": next_id,
        "hospital": hospital,
        "program_name": program_name,
        "region": region,
        "city": city,
        "specialty_units": [],
        "program_length_months": 12,
        "cohort_start": "",
        "info_session_dates": [],
        "app_open_date": "",
        "app_close_date": "",
        "requirements": "",
        "bsn_required": bsn,
        "application_url": url,
        "pay_range": "",
        "reputation": 0,
        "reputation_notes": "",
        "application_status": "Not Started",
        "personal_notes": "",
        "last_updated": date.today().isoformat()
    }

    data["programs"].append(new_program)
    save_data(data)
    print("Data saved.")
    print(f"\nAdded program ID {next_id}: {hospital} — {program_name}")


def compact_view(data, sort_by="id", region=None, bsn_filter=None):
    """One-line-per-program compact view with key info at a glance."""
    programs = data["programs"]

    if region:
        programs = [p for p in programs if region.lower() in p["region"].lower()]
    if bsn_filter:
        if bsn_filter.lower() == "no":
            programs = [p for p in programs if p["bsn_required"] != "Yes"]
        elif bsn_filter.lower() == "yes":
            programs = [p for p in programs if p["bsn_required"] == "Yes"]

    if sort_by == "deadline":
        programs.sort(key=lambda p: parse_date(p.get("app_close_date", "")) or date(9999, 12, 31))
    elif sort_by == "reputation":
        programs.sort(key=lambda p: p.get("reputation", 0), reverse=True)
    elif sort_by == "pay":
        programs.sort(key=lambda p: p.get("pay_range", ""), reverse=True)

    status_icons = {
        "Not Started": "  ",
        "In Progress": ">>",
        "Submitted": "TX",
        "Interview": "!!",
        "Offer": "**",
        "Rejected": "XX",
    }

    print(f"\n{'':>2} {'ID':>3} {'Hospital':<24} {'Region':<10} {'BSN':<4} {'Rep':<5} {'Len':>4} {'Deadline':<10} {'Status':<12}")
    print("-" * 85)

    for p in programs:
        icon = status_icons.get(p.get("application_status", "Not Started"), "  ")
        deadline = p.get("app_close_date", "") or "--"
        rep = "★" * p.get("reputation", 0)
        print(
            f"{icon} "
            f"{p['id']:>3} "
            f"{truncate(p['hospital'], 24):<24} "
            f"{truncate(p['region'], 10):<10} "
            f"{p['bsn_required'][:3]:<4} "
            f"{rep:<5} "
            f"{str(p.get('program_length_months', '?')) + 'm':>4} "
            f"{deadline:<10} "
            f"{p.get('application_status', 'Not Started'):<12}"
        )

    print(f"\nTotal: {len(programs)} programs")
    print("Legend: >> In Progress | TX Submitted | !! Interview | ** Offer | XX Rejected")


def compare_programs(data, program_ids):
    """Side-by-side comparison of selected programs."""
    programs = [p for p in data["programs"] if p["id"] in program_ids]
    if len(programs) < 2:
        print("Need at least 2 valid program IDs to compare.")
        return

    col_width = max(28, 60 // len(programs))
    label_width = 18

    # Header
    print(f"\n{'':>{label_width}}", end="")
    for p in programs:
        print(f"  {truncate(p['hospital'], col_width):<{col_width}}", end="")
    print()
    print("-" * (label_width + (col_width + 2) * len(programs)))

    fields = [
        ("Region", "region"),
        ("City", "city"),
        ("BSN Required", "bsn_required"),
        ("Program Length", lambda p: f"{p.get('program_length_months', '?')} months"),
        ("Reputation", lambda p: f"{reputation_stars(p.get('reputation', 0))} ({p.get('reputation', 0)}/5)"),
        ("Pay Range", "pay_range"),
        ("App Open", lambda p: p.get("app_open_date") or "TBD"),
        ("App Close", lambda p: p.get("app_close_date") or "TBD"),
        ("Cohort Start", lambda p: p.get("cohort_start") or "TBD"),
        ("Status", lambda p: p.get("application_status", "Not Started")),
        ("Specialties", lambda p: truncate(", ".join(p.get("specialty_units", [])), col_width)),
    ]

    for label, getter in fields:
        print(f"{label + ':':<{label_width}}", end="")
        for p in programs:
            if callable(getter):
                val = getter(p)
            else:
                val = str(p.get(getter, ""))
            print(f"  {truncate(val, col_width):<{col_width}}", end="")
        print()

    print()


def search_programs(data, keyword):
    """Search programs by keyword across all text fields."""
    keyword_lower = keyword.lower()
    matches = []

    for p in data["programs"]:
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

        if keyword_lower in searchable:
            matches.append(p)

    if not matches:
        print(f"No programs found matching '{keyword}'")
        return

    print(f"\n--- Search Results for '{keyword}' ({len(matches)} matches) ---\n")
    for p in matches:
        print(
            f"  [{p['id']:>2}] {p['hospital']:<30} "
            f"{p['region']:<14} "
            f"{reputation_stars(p.get('reputation', 0))} "
            f"BSN: {p['bsn_required']}"
        )
    print()


def show_timeline(data):
    """Visual timeline of application windows and key dates."""
    today = date.today()
    programs_with_dates = []

    for p in data["programs"]:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        cohort = parse_date(p.get("cohort_start", ""))
        if app_open or app_close or cohort:
            programs_with_dates.append((p, app_open, app_close, cohort))

    if not programs_with_dates:
        print("\n--- Timeline ---")
        print("No dates available yet. Use 'update <id> app_open_date <date>' to add dates.")
        print(f"Today: {today.isoformat()}")
        print(f"NCLEX target: {data['metadata'].get('nclex_target_date', 'TBD')}")
        return

    # Sort by earliest date available
    programs_with_dates.sort(key=lambda x: x[1] or x[2] or x[3] or date(9999, 12, 31))

    print(f"\n--- Application Timeline (today: {today.isoformat()}) ---\n")

    for p, app_open, app_close, cohort in programs_with_dates:
        name = truncate(p["hospital"], 26)
        status = p.get("application_status", "Not Started")

        print(f"  [{p['id']:>2}] {name:<26} {status}")

        if app_open:
            marker = " <-- NOW OPEN" if app_open <= today and (not app_close or app_close >= today) else ""
            print(f"       App Open:   {app_open.isoformat()}{marker}")
        if app_close:
            if app_close < today:
                marker = " (CLOSED)"
            elif (app_close - today).days <= 14:
                marker = f" ({(app_close - today).days}d left!)"
            else:
                marker = f" ({(app_close - today).days}d away)"
            print(f"       App Close:  {app_close.isoformat()}{marker}")
        if cohort:
            print(f"       Cohort:     {cohort.isoformat()}")
        print()

    # Key milestones
    nclex = data["metadata"].get("nclex_target_date", "")
    if nclex:
        print(f"  KEY DATES:")
        print(f"    NCLEX Target:  {nclex}")
        print(f"    Today:         {today.isoformat()}")
        print()


def show_stats(data):
    programs = data["programs"]
    total = len(programs)
    today = date.today()

    if total == 0:
        print("No programs tracked yet.")
        return

    # Region breakdown
    regions = {}
    for p in programs:
        r = p["region"]
        regions[r] = regions.get(r, 0) + 1

    # Status breakdown
    statuses = {}
    for p in programs:
        s = p.get("application_status", "Not Started")
        statuses[s] = statuses.get(s, 0) + 1

    # BSN stats
    bsn_yes = sum(1 for p in programs if p["bsn_required"] == "Yes")
    bsn_pref = sum(1 for p in programs if p["bsn_required"] == "Preferred")
    bsn_no = sum(1 for p in programs if p["bsn_required"] == "No")

    # Reputation stats
    avg_reputation = sum(p.get("reputation", 0) for p in programs) / total
    top_tier = sum(1 for p in programs if p.get("reputation", 0) >= 4)

    # Date completeness
    dates_close = sum(1 for p in programs if p.get("app_close_date"))
    dates_open = sum(1 for p in programs if p.get("app_open_date"))
    dates_cohort = sum(1 for p in programs if p.get("cohort_start"))

    # Program length breakdown
    lengths = {}
    for p in programs:
        l = p.get("program_length_months", 0)
        lengths[l] = lengths.get(l, 0) + 1

    # Upcoming deadlines
    upcoming_count = 0
    urgent_count = 0
    for p in programs:
        close = parse_date(p.get("app_close_date", ""))
        if close and close >= today:
            upcoming_count += 1
            if (close - today).days <= 14:
                urgent_count += 1

    # Currently open apps
    open_now = 0
    for p in programs:
        app_open = parse_date(p.get("app_open_date", ""))
        app_close = parse_date(p.get("app_close_date", ""))
        if app_open and app_open <= today and (not app_close or app_close >= today):
            open_now += 1

    nclex_date = data["metadata"].get("nclex_target_date", "")

    print(f"\n{'=' * 50}")
    print(f"  CA NEW GRAD RN TRACKER — DASHBOARD")
    print(f"  Today: {today.isoformat()}   NCLEX Target: {nclex_date}")
    print(f"{'=' * 50}")

    print(f"\n  OVERVIEW")
    print(f"  Total Programs:       {total}")
    print(f"  Avg Reputation:       {avg_reputation:.1f}/5  ({top_tier} programs rated 4+)")
    print(f"  Apps Open Now:        {open_now}")
    print(f"  Upcoming Deadlines:   {upcoming_count}" + (f"  ({urgent_count} URGENT)" if urgent_count else ""))

    print(f"\n  BSN REQUIREMENTS")
    bar_yes = "█" * bsn_yes
    bar_pref = "▓" * bsn_pref
    bar_no = "░" * bsn_no
    print(f"  Required:  {bsn_yes:>2}  {bar_yes}")
    print(f"  Preferred: {bsn_pref:>2}  {bar_pref}")
    print(f"  Not Req:   {bsn_no:>2}  {bar_no}")

    print(f"\n  BY REGION")
    for r, count in sorted(regions.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * count
        print(f"  {r:<28} {count:>2}  {bar}")

    print(f"\n  APPLICATION STATUS")
    status_order = ["Not Started", "In Progress", "Submitted", "Interview", "Offer", "Rejected"]
    for s in status_order:
        count = statuses.get(s, 0)
        if count > 0:
            bar = "█" * count
            print(f"  {s:<20} {count:>2}  {bar}")

    print(f"\n  PROGRAM LENGTH")
    for l, count in sorted(lengths.items()):
        bar = "█" * count
        print(f"  {l:>2} months:  {count:>2}  {bar}")

    print(f"\n  DATA COMPLETENESS")
    print(f"  App close dates:    {dates_close:>2}/{total}  {'█' * dates_close}{'░' * (total - dates_close)}")
    print(f"  App open dates:     {dates_open:>2}/{total}  {'█' * dates_open}{'░' * (total - dates_open)}")
    print(f"  Cohort start dates: {dates_cohort:>2}/{total}  {'█' * dates_cohort}{'░' * (total - dates_cohort)}")

    print(f"\n{'=' * 50}\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    data = load_data()
    command = sys.argv[1]

    # Parse common flags
    def parse_filters():
        sort_by, region, bsn_filter = "id", None, None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--sort" and i + 1 < len(sys.argv):
                sort_by = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--region" and i + 1 < len(sys.argv):
                region = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--bsn" and i + 1 < len(sys.argv):
                bsn_filter = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        return sort_by, region, bsn_filter

    if command == "view":
        sort_by, region, bsn_filter = parse_filters()
        view_programs(data, sort_by, region, bsn_filter)

    elif command == "compact":
        sort_by, region, bsn_filter = parse_filters()
        compact_view(data, sort_by, region, bsn_filter)

    elif command == "detail":
        if len(sys.argv) < 3:
            print("Usage: program_tracker.py detail <id>")
            return
        view_detail(data, int(sys.argv[2]))

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: program_tracker.py compare <id> <id> [<id> ...]")
            return
        ids = [int(x) for x in sys.argv[2:]]
        compare_programs(data, ids)

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: program_tracker.py search <keyword>")
            return
        search_programs(data, " ".join(sys.argv[2:]))

    elif command == "upcoming":
        upcoming_deadlines(data)

    elif command == "timeline":
        show_timeline(data)

    elif command == "add":
        add_program(data)

    elif command == "update":
        if len(sys.argv) < 5:
            print("Usage: program_tracker.py update <id> <field> <value>")
            return
        update_field(data, int(sys.argv[2]), sys.argv[3], " ".join(sys.argv[4:]))

    elif command == "status":
        if len(sys.argv) < 4:
            print("Usage: program_tracker.py status <id> <status>")
            print("Statuses: Not Started, In Progress, Submitted, Interview, Offer, Rejected")
            return
        update_status(data, int(sys.argv[2]), " ".join(sys.argv[3:]))

    elif command == "stats":
        show_stats(data)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
