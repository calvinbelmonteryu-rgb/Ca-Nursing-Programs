# Workflow: Track CA New Grad RN Programs

## Objective
Maintain an up-to-date tracker of new graduate nurse residency programs across California. The tracker helps a May 2026 NCLEX test-taker identify, compare, and apply to programs on time.

## Context
- Target user is taking the NCLEX in **May 2026**
- Programs typically open applications 2-6 months before cohort start
- Many programs require attendance at an info session before applying
- Spring/Summer 2026 cohorts are the primary targets

## Data Fields Per Program

| Field | Description |
|---|---|
| `hospital` | Hospital or health system name |
| `program_name` | Name of the new grad / residency program |
| `region` | Region of California (NorCal, Bay Area, Central Valley, SoCal, etc.) |
| `city` | City |
| `specialty_units` | Available units/specialties (Med-Surg, ICU, ED, L&D, etc.) |
| `program_length_months` | Duration of the residency program |
| `cohort_start` | Expected cohort start date |
| `info_session_dates` | Upcoming info session dates |
| `app_open_date` | Application open date |
| `app_close_date` | Application deadline |
| `requirements` | BSN required?, GPA minimum, certifications, etc. |
| `bsn_required` | Yes / No / Preferred |
| `application_url` | Link to apply or program page |
| `pay_range` | Starting pay range if known |
| `reputation` | Rating 1-5 based on research (Glassdoor, Reddit, word of mouth) |
| `reputation_notes` | Why this rating — specific pros/cons |
| `application_status` | Not Started / In Progress / Submitted / Interview / Offer / Rejected |
| `personal_notes` | Your notes, contacts, follow-ups |
| `last_updated` | When this record was last verified |

## Process

### 1. Research Programs
- Search hospital websites for "new grad nurse residency" or "nurse residency program"
- Check job boards: hospital career pages, Indeed, Handshake
- Check community resources: Reddit r/nursing, allnurses.com, nursing school networks
- Run `tools/program_tracker.py search` to do a web lookup

### 2. Add/Update Program Data
- Run `tools/program_tracker.py add` to add a new program
- Run `tools/program_tracker.py update <id>` to update an existing record
- All data stored in `data/programs.json`

### 3. Review & Prioritize
- Run `tools/program_tracker.py view` to see all programs sorted by deadline
- Run `tools/program_tracker.py upcoming` to see approaching deadlines
- Focus on programs where:
  - Application window overlaps with post-NCLEX timeline (June 2026+)
  - Info sessions haven't passed yet
  - Reputation is 3+ stars

### 4. Export
- Run `tools/export_tracker.py csv` to export to `.tmp/programs.csv`
- Run `tools/export_tracker.py sheets` to push to Google Sheets (requires credentials)

## Key Dates Timeline (May 2026 NCLEX)
- **Now - April 2026**: Research programs, attend info sessions, prep applications
- **May 2026**: Take NCLEX
- **June-July 2026**: Primary application window for summer/fall cohorts
- **Aug-Oct 2026**: Common cohort start dates

## Edge Cases
- Some programs accept applications on a rolling basis (no fixed deadline)
- Some programs require active RN license at time of application (not just NCLEX pass)
- Multi-site health systems may have different programs per campus
- Check if programs accept ADN or require BSN

## Sources to Check Regularly
- Individual hospital career pages
- NurseRecruiter.com
- Indeed / Glassdoor
- Reddit: r/nursing, r/newgrad
- allnurses.com forums
- California BRN website for license processing times
