import requests
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo
import os
import json
from bs4 import BeautifulSoup


# ============================================================
# SOURCES
# ============================================================

BASE_URL = (
    "https://s3.amazonaws.com/"
    "turnoutquickview.electionsfl.org/data/FL/"
)

BROWARD_URL = (
    "https://my.browardvotes.gov/"
    "TEDElectionLink/TurnOutWidget/dashboard/view/turnout-party"
)

# Separate dashboard specifically for Vote-By-Mail ballots: Issued vs
# Returned, by party. ONLY "Returned" (a ballot that actually came back
# and was counted) represents a real vote -- "Issued" just means a ballot
# was mailed out, which is not a vote and must never be counted as one.
# This is used to correct the VBM figure inside get_broward_data() below,
# since a ballot count conflating Issued with Returned would badly
# inflate Broward's totals (in one snapshot: 114,688 Issued vs. only
# 78,299 Returned -- a ~46,000-vote overcount if Issued were used).
BROWARD_ABSENTEE_URL = (
    "https://my.browardvotes.gov/"
    "TEDElectionLink/lol/dashboard/view/absturnout-party"
)


# ============================================================
# ELECTION CYCLE (date-based)
# ------------------------------------------------------------
# ELECTION_ID is no longer a single hardcoded string -- it's derived
# automatically from today's date against the windows defined below.
# Whenever the resolved id changes from what's stored in the last run's
# data/latest.json (i.e. today crossed one of these date boundaries),
# the script treats it as a new cycle and resets the vote-drop guardrail
# for exactly that one run -- the same mechanism as before, just driven
# by dates instead of a manual string edit.
#
# Each entry is (election_id, start_date_inclusive_or_None, end_date_exclusive).
#   - start=None means "everything before end".
#   - end=None means "everything from start onward, with nothing defined after".
# Keep entries in chronological order and non-overlapping. Add a new
# entry whenever a new election needs to be tracked.
# ============================================================

ELECTION_PERIODS = [

    ("FL-2026-Primary", None,               date(2026, 8, 23)),
    ("FL-2026-General", date(2026, 8, 23),   date(2026, 11, 15)),

    # Nothing is defined on/after November 15, 2026 yet -- add the next
    # election's window here (e.g. a 2026 runoff, or the next cycle)
    # once it's known. Until then, resolve_election_id() falls back to
    # a dated placeholder below rather than crashing.

]


def resolve_election_id(today):

    for election_id, start, end in ELECTION_PERIODS:

        if start is not None and today < start:

            continue

        if end is not None and today >= end:

            continue

        return election_id

    # No configured window covers today -- most likely because a new
    # election period hasn't been added to ELECTION_PERIODS yet. Falls
    # back to a label that's guaranteed to differ from any prior
    # election_id (so it still triggers exactly one guardrail reset,
    # then holds steady run-to-run) instead of erroring out.

    return f"FL-{today.year}-Unassigned-{today.isoformat()}"


# ============================================================
# COUNTY UPDATE SANITY CHECK
# ------------------------------------------------------------
# Two independent guardrails, checked per county on every run:
#
#   DROP:  the county's total went DOWN by more than this many votes.
#          Always suspicious -- vote totals should never meaningfully
#          decrease during a live count.
#
#   SPIKE: the county's total went UP by an implausible amount in a
#          single run. Rejected only when BOTH conditions are true --
#          the raw increase exceeds the abs threshold AND it's more
#          than the pct threshold of the previous total. Requiring both
#          avoids two failure modes: a huge county legitimately posting
#          a large end-of-day batch shouldn't get rejected just because
#          the raw number is big, and a small county's normal increment
#          from a tiny baseline shouldn't get rejected just because the
#          percentage looks huge.
#
#          Florida's largest counties can still legitimately clear the
#          statewide default thresholds with one real canvassing batch
#          (Broward posting +233,000 in one run really happened), so
#          they get their own higher allowance below rather than
#          loosening the check for every county and losing protection
#          against real glitches in smaller ones. Set a county's entry
#          to None to exempt it from the spike check entirely.
#
# Either guardrail firing restores that county's ENTIRE previous
# accepted row -- nothing is capped or partially applied.
# ============================================================

COUNTY_DROP_SANITY_THRESHOLD = 500000

COUNTY_SPIKE_ABS_THRESHOLD = 50000
COUNTY_SPIKE_PCT_THRESHOLD = 0.25

# Code: (abs_threshold, pct_threshold) -- overrides the defaults above
# for specific counties. Add more codes here as needed (see the COUNTIES
# dict below for the full code list).
COUNTY_SPIKE_OVERRIDES = {
    "BRO": (400000, 0.60),   # Broward
    "DAD": (400000, 0.60),   # Miami-Dade
    "PAL": (300000, 0.60),   # Palm Beach
    "HIL": (250000, 0.60),   # Hillsborough
    "ORA": (250000, 0.60),   # Orange
}


# ============================================================
# COUNTIES
# ============================================================

COUNTIES = {

    "Alachua": "ALA",
    "Baker": "BAK",
    "Bay": "BAY",
    "Bradford": "BRA",
    "Brevard": "BRE",
    "Broward": "BRO",
    "Calhoun": "CAL",
    "Charlotte": "CHA",
    "Citrus": "CIT",
    "Clay": "CLA",
    "Collier": "CLL",
    "Columbia": "CLM",
    "DeSoto": "DES",
    "Dixie": "DIX",
    "Duval": "DUV",
    "Escambia": "ESC",
    "Flagler": "FLA",
    "Franklin": "FRA",
    "Gadsden": "GAD",
    "Gilchrist": "GIL",
    "Glades": "GLA",
    "Gulf": "GUL",
    "Hamilton": "HAM",
    "Hardee": "HAR",
    "Hendry": "HEN",
    "Hernando": "HER",
    "Highlands": "HIG",
    "Hillsborough": "HIL",
    "Holmes": "HOL",
    "Indian River": "IND",
    "Jackson": "JAC",
    "Jefferson": "JEF",
    "Lafayette": "LAF",
    "Lake": "LAK",
    "Lee": "LEE",
    "Leon": "LEO",
    "Levy": "LEV",
    "Liberty": "LIB",
    "Madison": "MAD",
    "Manatee": "MAN",
    "Marion": "MRN",
    "Martin": "MRT",
    "Miami-Dade": "DAD",
    "Monroe": "MON",
    "Nassau": "NAS",
    "Okaloosa": "OKA",
    "Okeechobee": "OKE",
    "Orange": "ORA",
    "Osceola": "OSC",
    "Palm Beach": "PAL",
    "Pasco": "PAS",
    "Pinellas": "PIN",
    "Polk": "POL",
    "Putnam": "PUT",
    "Santa Rosa": "SAN",
    "Sarasota": "SAR",
    "Seminole": "SEM",
    "St. Johns": "STJ",
    "St. Lucie": "STL",
    "Sumter": "SUM",
    "Suwannee": "SUW",
    "Taylor": "TAY",
    "Union": "UNI",
    "Volusia": "VOL",
    "Wakulla": "WAK",
    "Walton": "WAL",
    "Washington": "WAS"

}


# ============================================================
# FOLDERS
# ============================================================

DATA_DIR = "data"
ARCHIVE_DIR = "archive"
REPORT_DIR = "reports"


os.makedirs(
    DATA_DIR,
    exist_ok=True
)

os.makedirs(
    ARCHIVE_DIR,
    exist_ok=True
)

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)


# ============================================================
# FILE LOCATIONS
# ============================================================

PREVIOUS_FILE = os.path.join(
    DATA_DIR,
    "previous_turnout.csv"
)

TRACKER_FILE = os.path.join(
    DATA_DIR,
    "county_tracker.csv"
)

HISTORY_FILE = os.path.join(
    DATA_DIR,
    "county_history.csv"
)

LATEST_REPORT_FILE = os.path.join(
    REPORT_DIR,
    "latest_report.txt"
)

LATEST_JSON_FILE = os.path.join(
    DATA_DIR,
    "latest.json"
)


# ============================================================
# RUN TIME — EASTERN TIME
# ============================================================

EASTERN = ZoneInfo(
    "America/New_York"
)

RUN_NOW = datetime.now(
    EASTERN
)


def ordinal_day(day):

    if 10 <= day % 100 <= 20:

        suffix = "th"

    else:

        suffix = {
            1: "st",
            2: "nd",
            3: "rd"
        }.get(
            day % 10,
            "th"
        )

    return f"{day}{suffix}"


RUN_TIME = (

    f"Updated at "
    f"{RUN_NOW.strftime('%B')} "
    f"{ordinal_day(RUN_NOW.day)}, "
    f"{RUN_NOW.strftime('%Y')} "
    f"at "
    f"{RUN_NOW.strftime('%I:%M%p').lstrip('0').lower()}"

)


ELECTION_ID = resolve_election_id(
    RUN_NOW.date()
)


# ============================================================
# DETECT A NEW ELECTION CYCLE
# ------------------------------------------------------------
# Reads whichever election_id the last run stored in latest.json. If it's
# missing, or doesn't match ELECTION_ID above, this run is treated as the
# first run of a brand-new cycle: the old previous_turnout.csv and
# county_tracker.csv are NOT loaded for comparison purposes (even though
# the files themselves still exist on disk), so the vote-drop sanity
# check further down can't reject this run's real, legitimately-lower
# numbers as if they were a scraping glitch.
# ============================================================

previous_election_id = None

if os.path.exists(LATEST_JSON_FILE):

    try:

        with open(
            LATEST_JSON_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            previous_election_id = json.load(file).get("election_id")

    except Exception:

        previous_election_id = None


NEW_ELECTION_CYCLE = (
    previous_election_id
    !=
    ELECTION_ID
)


if NEW_ELECTION_CYCLE:

    print(
        "\n================================="
    )

    print(
        "NEW ELECTION CYCLE DETECTED"
    )

    print(
        "================================="
    )

    print(
        f"Previous election_id: {previous_election_id}"
    )

    print(
        f"Current election_id:  {ELECTION_ID}"
    )

    print(
        "Ignoring previous_turnout.csv and county_tracker.csv "
        "from the old cycle for comparison purposes.\n"
        "This run's real numbers will be written through as-is, "
        "even if they're much lower than the last cycle's totals."
    )


# ============================================================
# LOAD MEMORY FILES
# ============================================================

if (

    not NEW_ELECTION_CYCLE

    and

    os.path.exists(PREVIOUS_FILE)

):

    previous = pd.read_csv(
        PREVIOUS_FILE
    )

else:

    previous = None


if (

    not NEW_ELECTION_CYCLE

    and

    os.path.exists(TRACKER_FILE)

):

    tracker = pd.read_csv(
        TRACKER_FILE
    )

else:

    tracker = pd.DataFrame(
        columns=[
            "County",
            "Code",
            "Last Updated"
        ]
    )


# ============================================================
# BROWARD PARSER
# ============================================================

def classify_party_label(label):

    # Matches by what the label actually SAYS, not by position -- the
    # absentee dashboard's row order turned out to be DEM, NPA, Other,
    # REP, not the DEM/REP/NPA/OTHER order assumed elsewhere in this
    # script, so trusting an index here would silently mislabel parties.

    text = label.strip().lower()

    if "democrat" in text:

        return "DEM"

    if "republican" in text:

        return "REP"

    if "no party" in text or text == "npa":

        return "NPA"

    return "OTHER"


def _parse_broward_absentee_from_json(soup):

    # PRIMARY method: the "Vote By Mail Ballots by Party" chart on this
    # page is driven by a clean JSON blob -- <script type="application/
    # json" class="ted-ec-initial"> inside the chart widget's div (that
    # div is identified by its data-ec-poll attribute containing
    # "tile=party-bar&dashboard=absturnout-party"). It carries a
    # "Returned" series (vote counts, indexed 0..3) and an "extra.labels"
    # dict mapping those same indices to party names -- no nested-div
    # navigation required, and much less likely to break if the page's
    # HTML structure changes around it.

    chart_div = soup.find(
        "div",

        attrs={
            "data-ec-poll": lambda v: (
                v
                and "tile=party-bar" in v
                and "dashboard=absturnout-party" in v
            )
        }

    )

    if chart_div is None:

        return None


    script_tag = chart_div.find(
        "script",
        {"class": "ted-ec-initial"}
    )

    if script_tag is None or not script_tag.string:

        return None


    chart_json = json.loads(
        script_tag.string
    )

    series_list = (

        chart_json
        .get("option", {})
        .get("series", [])

    )

    returned_series = next(
        (s for s in series_list if s.get("name") == "Returned"),
        None
    )

    if returned_series is None:

        return None


    labels = (

        chart_json
        .get("extra", {})
        .get("labels")

    )

    if not labels:

        y_data = (

            chart_json
            .get("option", {})
            .get("yAxis", {})
            .get("data", [])

        )

        labels = {

            str(i): name

            for i, name in enumerate(y_data)

        }


    returned = {

        "DEM": 0,
        "REP": 0,
        "NPA": 0,
        "OTHER": 0

    }


    for index, votes in enumerate(returned_series["data"]):

        label = labels.get(
            str(index),
            ""
        )

        code = classify_party_label(
            label
        )

        returned[code] += int(
            votes
        )

        print(
            f"  {label} ({code}): "
            f"Returned = {int(votes):,}"
        )


    return returned


def _parse_broward_absentee_from_grid(soup):

    # FALLBACK method: the same numbers also appear in an on-page data
    # grid, each cell nested several divs deep under ids Party0/
    # Returned0, Party1/Returned1, etc. Used only if the JSON chart data
    # above isn't found (e.g. the page changes to no longer render a
    # chart). Row count and order aren't assumed here either -- this
    # walks Party0, Party1, ... until a row is missing, and identifies
    # each row's party by reading its actual label text, not its index.

    returned = {

        "DEM": 0,
        "REP": 0,
        "NPA": 0,
        "OTHER": 0

    }


    row_index = 0

    while True:

        party_element = soup.find(
            id=f"Party{row_index}"
        )

        if party_element is None:

            break


        returned_element = soup.find(
            id=f"Returned{row_index}"
        )

        if returned_element is None:

            raise ValueError(
                f"Could not find Returned{row_index} "
                "on Broward absentee page."
            )


        party_label = party_element.get_text(
            strip=True
        )

        code = classify_party_label(
            party_label
        )


        returned_text = (
            returned_element
            .get_text(strip=True)
            .replace(",", "")
        )

        returned_votes = (
            int(float(returned_text))

            if returned_text

            else 0

        )


        returned[code] += returned_votes


        print(
            f"  {party_label} ({code}): "
            f"Returned = {returned_votes:,}"
        )


        row_index += 1


    return returned


def get_broward_absentee_returned():

    # Scrapes Broward's Vote-By-Mail (absentee) dashboard, which
    # explicitly separates ballots merely ISSUED (mailed out) from
    # ballots actually RETURNED (came back and were counted). ONLY the
    # Returned figure is a real vote -- Issued is not, and pulling it by
    # mistake badly inflates totals (Broward's snapshot: 114,688 Issued
    # vs. only 78,299 Returned).
    #
    # Tries the chart's JSON data feed first (cleaner, less fragile);
    # falls back to the on-page data grid if that isn't found.

    print(
        "\nUsing Broward County VBM (absentee) source:"
    )

    print(
        BROWARD_ABSENTEE_URL
    )


    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36",

        "Accept":
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"

    }


    response = requests.get(
        BROWARD_ABSENTEE_URL,
        headers=headers,
        timeout=30
    )


    response.raise_for_status()


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    result = _parse_broward_absentee_from_json(
        soup
    )

    if result is not None:

        print(
            "  (source: chart JSON)"
        )

        return result


    print(
        "  Chart JSON not found -- falling back to the data grid."
    )

    return _parse_broward_absentee_from_grid(
        soup
    )


def get_broward_data():

    print(
        "\nUsing Broward County source:"
    )

    print(
        BROWARD_URL
    )


    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36",

        "Accept":
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"

    }


    response = requests.get(
        BROWARD_URL,
        headers=headers,
        timeout=30
    )


    response.raise_for_status()


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    # Corrected Vote-By-Mail figures -- Returned only, never Issued. Used
    # below in place of whatever this page's own "VoteByMail" field
    # reports, since that field's Issued-vs-Returned meaning on THIS
    # specific page has not been independently verified.
    absentee_returned = get_broward_absentee_returned()


    # --------------------------------------------------------
    # Party mapping
    # --------------------------------------------------------

    party_mapping = {

        0: "DEM",
        1: "REP",
        2: "NPA",
        3: "OTHER"

    }


    totals = {

        "DEM": 0,
        "REP": 0,
        "IND": 0,
        "NPA": 0,
        "OTHER": 0

    }


    detailed = {}


    # --------------------------------------------------------
    # Extract each party
    # --------------------------------------------------------

    for party_number, party_code in party_mapping.items():

        party_element = soup.find(
            id=f"Party{party_number}"
        )


        if party_element is None:

            raise ValueError(
                f"Could not find Party{party_number} "
                "on Broward page."
            )


        party_name = (
            party_element.get_text(
                strip=True
            )
        )


        def get_value(field):

            element = soup.find(
                id=f"{field}{party_number}"
            )


            if element is None:

                raise ValueError(
                    f"Could not find "
                    f"{field}{party_number} "
                    "on Broward page."
                )


            text = element.get_text(
                strip=True
            )


            text = (
                text
                .replace(",", "")
                .replace("%", "")
                .strip()
            )


            if not text:

                return 0


            if field == "Turnout":

                return float(text)


            return int(
                float(text)
            )


        # ----------------------------------------------------
        # Voting methods
        # ----------------------------------------------------

        eligible = get_value(
            "EligibleCount"
        )

        # Corrected: Returned-only VBM count from the dedicated absentee
        # dashboard (see get_broward_absentee_returned above), NOT this
        # page's own "VoteByMail" field -- that field's Issued-vs-Returned
        # meaning here hasn't been independently confirmed, and using
        # Issued by mistake would count un-cast mailed ballots as votes.
        vbm = absentee_returned.get(
            party_code,
            0
        )

        early = get_value(
            "EarlyVote"
        )

        election_day = get_value(
            "ElectionDay"
        )

        # Total is derived from the corrected VBM + EV + ED, rather than
        # trusted from this page's own "Total" field, since that field
        # would inherit the same Issued-vs-Returned ambiguity as VBM.
        total = (
            vbm
            +
            early
            +
            election_day
        )

        turnout = get_value(
            "Turnout"
        )


        # ----------------------------------------------------
        # Store total
        # ----------------------------------------------------

        totals[party_code] = total


        # ----------------------------------------------------
        # Store detailed data
        # ----------------------------------------------------

        detailed[
            f"{party_code} VBM"
        ] = vbm


        detailed[
            f"{party_code} EV"
        ] = early


        detailed[
            f"{party_code} ED"
        ] = election_day


        # ----------------------------------------------------
        # Console output
        # ----------------------------------------------------

        print(
            f"  {party_name}:"
        )

        print(
            f"    VBM (Returned, corrected): {vbm:,}"
        )

        print(
            f"    Early Vote: {early:,}"
        )

        print(
            f"    Election Day: {election_day:,}"
        )

        print(
            f"    Total (recomputed): {total:,}"
        )

        print(
            f"    Eligible: {eligible:,}"
        )

        print(
            f"    Turnout: {turnout:.2f}%"
        )


    # --------------------------------------------------------
    # Sanity check
    # --------------------------------------------------------

    for party_code in [

        "DEM",
        "REP",
        "NPA",
        "OTHER"

    ]:

        calculated = (

            detailed[
                f"{party_code} VBM"
            ]

            +

            detailed[
                f"{party_code} EV"
            ]

            +

            detailed[
                f"{party_code} ED"
            ]

        )


        if calculated != totals[party_code]:

            print(
                f"WARNING: {party_code} "
                "does not match!"
            )

            print(
                f"  VBM + EV + ED = "
                f"{calculated:,}"
            )

            print(
                f"  Reported total = "
                f"{totals[party_code]:,}"
            )


    return {

        **totals,

        **detailed

    }


# ============================================================
# DOWNLOAD DATA
# ============================================================

rows = []


for county_name, county_code in COUNTIES.items():

    print(
        "\nLoading:",
        county_name
    )


    # ========================================================
    # BROWARD
    # ========================================================

    if county_name == "Broward":

        try:

            broward = get_broward_data()


            rows.append({

                "Timestamp":
                    RUN_TIME,

                "County":
                    county_name,

                "Code":
                    county_code,

                "DEM":
                    broward["DEM"],

                "REP":
                    broward["REP"],

                "IND":
                    broward["IND"],

                "NPA":
                    broward["NPA"],

                "OTHER":
                    broward["OTHER"],

                "DEM VBM":
                    broward["DEM VBM"],

                "DEM EV":
                    broward["DEM EV"],

                "DEM ED":
                    broward["DEM ED"],

                "REP VBM":
                    broward["REP VBM"],

                "REP EV":
                    broward["REP EV"],

                "REP ED":
                    broward["REP ED"],

                "NPA VBM":
                    broward["NPA VBM"],

                "NPA EV":
                    broward["NPA EV"],

                "NPA ED":
                    broward["NPA ED"],

                "OTHER VBM":
                    broward["OTHER VBM"],

                "OTHER EV":
                    broward["OTHER EV"],

                "OTHER ED":
                    broward["OTHER ED"]

            })


            print(
                "Broward successfully loaded."
            )


        except Exception as e:

            print(
                "\nBROWARD FAILED:"
            )

            print(
                str(e)
            )


        continue


    # ========================================================
    # ALL OTHER COUNTIES
    # ========================================================

    totals = {

        "DEM": 0,
        "REP": 0,
        "IND": 0,
        "NPA": 0,
        "OTHER": 0

    }


    index_url = (
        f"{BASE_URL}"
        f"{county_code}/index.json"
    )


    try:

        index_response = requests.get(
            index_url,
            timeout=15
        )

        index_response.raise_for_status()

        index = index_response.json()


    except Exception as e:

        print(
            "Failed:",
            county_name,
            e
        )

        continue


    for location in index:

        data_url = (

            f"{BASE_URL}"
            f"{county_code}/"
            f"{location}/data.json"

        )


        try:

            data_response = requests.get(
                data_url,
                timeout=15
            )

            data_response.raise_for_status()

            data = data_response.json()


            parties = (

                data
                .get(
                    "Turnout",
                    {}
                )
                .get(
                    "PartyType",
                    {}
                )

            )


            for party, value in parties.items():

                if not isinstance(
                    value,
                    dict
                ):

                    continue


                mail = value.get(
                    "Mail",
                    0
                )

                early = value.get(
                    "EarlyVoting",
                    0
                )

                election_day = (

                    value.get(
                        "ElectionDay",
                        0
                    )

                    or

                    value.get(
                        "ElectionDayVoting",
                        0
                    )

                    or

                    value.get(
                        "ElectionDayVote",
                        0
                    )

                )


                ballots = (

                    mail
                    +
                    early
                    +
                    election_day

                )


                if party in totals:

                    totals[party] += ballots

                else:

                    totals["OTHER"] += ballots


        except Exception:

            continue


    rows.append({

        "Timestamp":
            RUN_TIME,

        "County":
            county_name,

        "Code":
            county_code,

        **totals

    })


# ============================================================
# CREATE DATAFRAME
# ============================================================

df = pd.DataFrame(
    rows
)


if df.empty:

    raise SystemExit(
        "ERROR: No county data was collected."
    )


# ============================================================
# ENSURE DETAILED COLUMNS EXIST
# ============================================================

for col in [

    "DEM VBM",
    "DEM EV",
    "DEM ED",

    "REP VBM",
    "REP EV",
    "REP ED",

    "NPA VBM",
    "NPA EV",
    "NPA ED",

    "OTHER VBM",
    "OTHER EV",
    "OTHER ED"

]:

    if col not in df.columns:

        df[col] = 0


df = df.fillna(0)


# ============================================================
# COUNTY UPDATE SANITY CHECK
# ------------------------------------------------------------
# Skipped entirely when NEW_ELECTION_CYCLE is True (previous is None in
# that case), so a legitimate reset to near-0 turnout at the start of a
# new cycle is never mistaken for a scraping error. Checks BOTH a big
# drop and an implausible spike (see the threshold comments above).
# ============================================================

rejected_counties = []


if previous is not None:

    for index, row in df.iterrows():

        county_code = row["Code"]


        previous_rows = previous[
            previous["Code"] == county_code
        ]


        if previous_rows.empty:

            continue


        previous_row = previous_rows.iloc[0]


        previous_total = (

            previous_row["DEM"]
            +
            previous_row["REP"]
            +
            previous_row["IND"]
            +
            previous_row["NPA"]
            +
            previous_row["OTHER"]

        )


        scraped_total = (

            row["DEM"]
            +
            row["REP"]
            +
            row["IND"]
            +
            row["NPA"]
            +
            row["OTHER"]

        )


        votes_removed = (
            previous_total
            -
            scraped_total
        )

        votes_added = (
            scraped_total
            -
            previous_total
        )


        # ----------------------------------------------------
        # Reject this county if either guardrail trips
        # ----------------------------------------------------

        reject_reason = None

        spike_override = COUNTY_SPIKE_OVERRIDES.get(county_code)

        if spike_override is None and county_code in COUNTY_SPIKE_OVERRIDES:

            # Explicitly set to None in the overrides dict -- this
            # county is fully exempt from the spike check.
            spike_abs_threshold = None
            spike_pct_threshold = None

        elif spike_override is not None:

            spike_abs_threshold, spike_pct_threshold = spike_override

        else:

            spike_abs_threshold = COUNTY_SPIKE_ABS_THRESHOLD
            spike_pct_threshold = COUNTY_SPIKE_PCT_THRESHOLD


        if votes_removed > COUNTY_DROP_SANITY_THRESHOLD:

            reject_reason = "drop"


        elif (

            spike_abs_threshold is not None

            and

            votes_added
            >
            spike_abs_threshold

            and

            (
                previous_total == 0

                or

                (
                    votes_added
                    /
                    previous_total
                )
                >
                spike_pct_threshold
            )

        ):

            reject_reason = "spike"


        if reject_reason:

            county_name = row["County"]


            print(
                "\n⚠️ REJECTED COUNTY UPDATE "
                f"({reject_reason.upper()}):"
            )

            print(
                f"  County: {county_name}"
            )

            print(
                f"  Previous accepted total: "
                f"{previous_total:,.0f}"
            )

            print(
                f"  Newly scraped total: "
                f"{scraped_total:,.0f}"
            )

            if reject_reason == "drop":

                print(
                    f"  Votes removed: "
                    f"{votes_removed:,.0f}"
                )

                print(
                    f"  Drop threshold: "
                    f"{COUNTY_DROP_SANITY_THRESHOLD:,}"
                )

            else:

                pct_display = (

                    (votes_added / previous_total)

                    if previous_total

                    else float("inf")

                )

                print(
                    f"  Votes added: "
                    f"{votes_added:,.0f}"
                )

                print(
                    f"  Spike thresholds: "
                    f"{spike_abs_threshold:,} votes "
                    f"AND {spike_pct_threshold:.0%} "
                    f"(actual: {pct_display:.0%})"
                    + (
                        f"  [override for {county_code}]"
                        if county_code in COUNTY_SPIKE_OVERRIDES
                        else ""
                    )
                )

            print(
                "  Keeping previous accepted data."
            )


            rejected_counties.append({

                "County":
                    county_name,

                "Code":
                    county_code,

                "Reason":
                    reject_reason,

                "Previous Total":
                    previous_total,

                "Scraped Total":
                    scraped_total,

                "Votes Removed":
                    votes_removed,

                "Votes Added":
                    votes_added

            })


            # Restore the ENTIRE previous accepted row.
            # No vote totals are capped or modified.

            for column in previous.columns:

                if column in df.columns:

                    df.loc[
                        index,
                        column
                    ] = previous_row[column]


# ============================================================
# CALCULATIONS
# ============================================================

df["TOTAL"] = (

    df["DEM"]
    +
    df["REP"]
    +
    df["IND"]
    +
    df["NPA"]
    +
    df["OTHER"]

)


major_total = (

    df["DEM"]
    +
    df["REP"]

)


df["DEM %"] = (

    df["DEM"]
    .div(
        major_total.replace(
            0,
            pd.NA
        )
    )
    .fillna(0)

)


df["REP %"] = (

    df["REP"]
    .div(
        major_total.replace(
            0,
            pd.NA
        )
    )
    .fillna(0)

)


df["D Raw Margin"] = (

    df["DEM"]
    -
    df["REP"]

)


df["R Raw Margin"] = (

    df["REP"]
    -
    df["DEM"]

)


df["Diff"] = (

    abs(
        df["DEM %"]
        -
        df["REP %"]
    )

)


df["Signed Margin"] = (

    df["DEM %"]
    -
    df["REP %"]

)


df["Leader"] = df["Signed Margin"].apply(

    lambda x:
        "D"
        if x > 0
        else "R"

)


def rating(margin):

    margin = abs(
        margin
    )


    if margin < 0.03:

        return "Toss Up"


    elif margin < 0.08:

        return "Lean"


    elif margin < 0.15:

        return "Likely"


    else:

        return "Safe"


df["Rating"] = (

    df["Signed Margin"]
    .apply(rating)

)


# ============================================================
# STATEWIDE TOTALS
# ============================================================

state_dem = df["DEM"].sum()

state_rep = df["REP"].sum()

state_other = (

    df["IND"].sum()
    +
    df["NPA"].sum()
    +
    df["OTHER"].sum()

)


state_total = (

    state_dem
    +
    state_rep
    +
    state_other

)


statewide_totals = {

    "DEM":
        int(state_dem),

    "REP":
        int(state_rep),

    "OTHER":
        int(state_other),

    "TOTAL":
        int(state_total)

}


# ============================================================
# CHANGE DETECTION
# ============================================================

updates = []

rating_changes = []

unchanged = 0


for col in [

    "DEM New",
    "REP New",
    "IND New",
    "NPA New",
    "OTHER New",
    "Total New"

]:

    df[col] = 0


df["Margin Move"] = 0.0


for col in [

    "Rating Change",
    "Rating Move",
    "Margin Diff"

]:

    df[col] = ""


df["Rating Change"] = "No"


# ============================================================
# COMPARE TO PREVIOUS RUN
# ============================================================

if previous is not None:

    comparison = df.merge(

        previous,

        on="Code",

        suffixes=(
            "_NEW",
            "_OLD"
        )

    )


    for _, row in comparison.iterrows():

        changes = {}

        total_change = 0


        # ----------------------------------------------------
        # Margin change
        # ----------------------------------------------------

        margin_diff = (

            row["Signed Margin_NEW"]
            -
            row["Signed Margin_OLD"]

        )


        if margin_diff > 0:

            margin_diff_text = (

                f"+{margin_diff:.2%} "
                "toward Democrats"

            )


        elif margin_diff < 0:

            margin_diff_text = (

                f"{margin_diff:.2%} "
                "toward Republicans"

            )


        else:

            margin_diff_text = (
                "No change"
            )


        df.loc[
            df["Code"] == row["Code"],
            "Margin Diff"
        ] = margin_diff_text


        # ----------------------------------------------------
        # Rating change
        # ----------------------------------------------------

        if (

            row["Rating_NEW"]
            !=
            row["Rating_OLD"]

            or

            row["Leader_NEW"]
            !=
            row["Leader_OLD"]

        ):

            margin_change = (

                row["Signed Margin_NEW"]
                -
                row["Signed Margin_OLD"]

            )


            rating_changes.append({

                "County":
                    row["County"],

                "Code":
                    row["Code"],

                "Old":
                    (
                        f"{row['Rating_OLD']} "
                        f"{row['Leader_OLD']}"
                    ),

                "New":
                    (
                        f"{row['Rating_NEW']} "
                        f"{row['Leader_NEW']}"
                    ),

                "Margin Change":
                    margin_change

            })


            df.loc[
                df["Code"] == row["Code"],
                "Rating Change"
            ] = "Yes"


            df.loc[
                df["Code"] == row["Code"],
                "Rating Move"
            ] = (

                f"{row['Rating_OLD']} "
                f"{row['Leader_OLD']}"
                " → "
                f"{row['Rating_NEW']} "
                f"{row['Leader_NEW']}"

            )


            df.loc[
                df["Code"] == row["Code"],
                "Margin Move"
            ] = margin_change


        # ----------------------------------------------------
        # Vote changes
        # ----------------------------------------------------

        for party in [

            "DEM",
            "REP",
            "IND",
            "NPA",
            "OTHER"

        ]:

            change = (

                row[f"{party}_NEW"]
                -
                row[f"{party}_OLD"]

            )


            if change != 0:

                changes[party] = change

                total_change += change


                df.loc[
                    df["Code"] == row["Code"],
                    f"{party} New"
                ] = change


        # ----------------------------------------------------
        # Total movement
        # ----------------------------------------------------

        df.loc[
            df["Code"] == row["Code"],
            "Total New"
        ] = total_change


        # ----------------------------------------------------
        # Store update
        # ----------------------------------------------------

        if changes:

            updates.append({

                "County":
                    row["County"],

                "Code":
                    row["Code"],

                **changes,

                "Total New":
                    total_change

            })

        else:

            unchanged += 1


else:

    print(
        "\nFirst run detected"
        + (
            " for this election cycle."
            if NEW_ELECTION_CYCLE
            else "."
        )
    )

    print(
        "Creating baseline file..."
    )


# ============================================================
# LAST UPDATED TRACKER
# ============================================================

tracker_updates = []


for _, row in df.iterrows():

    county_code = row["Code"]


    rejected = any(

        item["Code"] == county_code

        for item in rejected_counties

    )


    previous_tracker_rows = tracker[
        tracker["Code"] == county_code
    ]


    if (
        rejected
        and
        not previous_tracker_rows.empty
    ):

        last_updated = (
            previous_tracker_rows.iloc[0]["Last Updated"]
        )

    else:

        last_updated = RUN_TIME


    tracker_updates.append({

        "County":
            row["County"],

        "Code":
            county_code,

        "Last Updated":
            last_updated

    })


tracker = pd.DataFrame(
    tracker_updates
)


df = df.merge(
    tracker,
    on="Code",
    how="left"
)


# ============================================================
# COUNTY HISTORY
# ============================================================

history_rows = []


for item in updates:

    history_rows.append({

        "Timestamp":
            RUN_TIME,

        "County":
            item["County"],

        "Code":
            item["Code"],

        "DEM New":
            item.get("DEM", 0),

        "REP New":
            item.get("REP", 0),

        "IND New":
            item.get("IND", 0),

        "NPA New":
            item.get("NPA", 0),

        "OTHER New":
            item.get("OTHER", 0),

        "Total New":
            item["Total New"]

    })


if history_rows:

    history = pd.DataFrame(
        history_rows
    )


    if (

        not NEW_ELECTION_CYCLE

        and

        os.path.exists(HISTORY_FILE)

    ):

        old_history = pd.read_csv(
            HISTORY_FILE
        )


        history = pd.concat(
            [
                old_history,
                history
            ],
            ignore_index=True
        )


    history.to_csv(
        HISTORY_FILE,
        index=False
    )


# ============================================================
# SAVE CURRENT DATA
# ============================================================

df.to_csv(
    PREVIOUS_FILE,
    index=False
)


tracker.to_csv(
    TRACKER_FILE,
    index=False
)


# ============================================================
# SAVE ARCHIVE
# ============================================================

archive_timestamp = RUN_NOW.strftime(
    "%Y-%m-%d_%H-%M-%S"
)


archive_file = os.path.join(

    ARCHIVE_DIR,

    f"florida_turnout_{archive_timestamp}.csv"

)


df.to_csv(
    archive_file,
    index=False
)


# ============================================================
# UPDATE LATEST JSON
# ============================================================

latest_json = {

    "election_id":
        ELECTION_ID,

    "run_time":
        RUN_TIME,

    "previous_file":
        PREVIOUS_FILE.replace(
            os.sep,
            "/"
        ),

    "archive_file":
        archive_file.replace(
            os.sep,
            "/"
        )

}


with open(
    LATEST_JSON_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        latest_json,
        file,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# STATEWIDE SUMMARY
# ============================================================

state_margin = (

    state_dem
    -
    state_rep

)


if state_margin > 0:

    statewide_leader = (

        f"🔵 Democrats lead by "
        f"{state_margin:,.0f} votes statewide."

    )


elif state_margin < 0:

    statewide_leader = (

        f"🔴 Republicans lead by "
        f"{abs(state_margin):,.0f} votes statewide."

    )


else:

    statewide_leader = (
        "The statewide vote is tied."
    )


# ============================================================
# STATEWIDE MARGIN CHANGE
# ============================================================

if previous is not None:

    old_dem = previous["DEM"].sum()

    old_rep = previous["REP"].sum()


    old_total = (
        old_dem
        +
        old_rep
    )


    new_total = (
        state_dem
        +
        state_rep
    )


    if old_total > 0 and new_total > 0:

        old_share = (
            old_dem
            /
            old_total
        )


        new_share = (
            state_dem
            /
            new_total
        )


        statewide_change = (
            new_share
            -
            old_share
        )


        if statewide_change > 0:

            statewide_margin_change = (

                f"+{statewide_change:.2%} "
                "toward Democrats"

            )


        elif statewide_change < 0:

            statewide_margin_change = (

                f"{statewide_change:.2%} "
                "toward Republicans"

            )


        else:

            statewide_margin_change = (
                "No change"
            )


    else:

        statewide_margin_change = (
            "No change"
        )


else:

    statewide_margin_change = (
        "First update"
    )


# ============================================================
# TOP 3 COUNTY UPDATES
# ============================================================

top_three = sorted(

    updates,

    key=lambda x:
        x["Total New"],

    reverse=True

)[:3]


# ============================================================
# CONSOLE REPORT
# ============================================================

print(
    "\n================================="
)

print(
    "FLORIDA TURNOUT UPDATE"
)

print(
    "================================="
)


print(
    "\nElection ID:",
    ELECTION_ID
)


print(
    "\nRun Time:"
)

print(
    RUN_TIME,
    "Eastern Time"
)


print(
    "\nCounties successfully loaded:",
    len(df),
    "/",
    len(COUNTIES)
)


if "BRO" in df["Code"].values:

    broward_row = df[
        df["Code"] == "BRO"
    ].iloc[0]


    print(
        "\nBROWARD VERIFICATION:"
    )

    print(
        "  DEM:",
        f"{broward_row['DEM']:,.0f}"
    )

    print(
        "  REP:",
        f"{broward_row['REP']:,.0f}"
    )

    print(
        "  NPA:",
        f"{broward_row['NPA']:,.0f}"
    )

    print(
        "  OTHER:",
        f"{broward_row['OTHER']:,.0f}"
    )


else:

    print(
        "\nWARNING: Broward is missing from the dataset."
    )


print(
    "\nUpdated Counties:",
    len(updates)
)

print(
    "Unchanged Counties:",
    unchanged
)

print(
    "Rejected County Updates:",
    len(rejected_counties)
)


# ============================================================
# STATEWIDE TOTALS
# ============================================================

print(
    "\nSTATEWIDE TOTALS:"
)

print(
    "  DEM:",
    f"{statewide_totals['DEM']:,}"
)

print(
    "  REP:",
    f"{statewide_totals['REP']:,}"
)

print(
    "  OTHER:",
    f"{statewide_totals['OTHER']:,}"
)

print(
    "  TOTAL:",
    f"{statewide_totals['TOTAL']:,}"
)


# ============================================================
# REJECTED COUNTY UPDATES
# ============================================================

if rejected_counties:

    print(
        "\n================================="
    )

    print(
        "REJECTED COUNTY UPDATES"
    )

    print(
        "================================="
    )


    for rejected in rejected_counties:

        print(
            f"\n{rejected['County']} "
            f"({rejected['Reason'].upper()})"
        )

        print(
            " Previous Accepted:",
            f"{rejected['Previous Total']:,.0f}"
        )

        print(
            " Scraped:",
            f"{rejected['Scraped Total']:,.0f}"
        )

        if rejected["Reason"] == "drop":

            print(
                " Votes Removed:",
                f"{rejected['Votes Removed']:,.0f}"
            )

        else:

            print(
                " Votes Added:",
                f"{rejected['Votes Added']:,.0f}"
            )

        print(
            " Action: Previous data retained"
        )


# ============================================================
# RATING CHANGES
# ============================================================

print(
    "\nRATING / FORECAST CHANGES:"
)


if not rating_changes:

    print(
        "No rating changes detected."
    )


else:

    for change in rating_changes:

        print(
            "\n",
            change["County"]
        )

        print(
            " ",
            change["Old"],
            "→",
            change["New"]
        )

        print(
            " Margin Move:",
            f"{change['Margin Change']:+.3f}"
        )


# ============================================================
# COUNTY UPDATES
# ============================================================

if not updates:

    print(
        "\nNo county changes detected."
    )


else:

    print(
        "\nCOUNTY UPDATES:"
    )


    for county in updates:

        print(
            "\n",
            county["County"]
        )


        for key, value in county.items():

            if key not in [
                "County",
                "Code",
                "Total New"
            ]:

                print(
                    " ",
                    key,
                    f"{value:+}"
                )


        print(
            " Total New:",
            f"{county['Total New']:+}"
        )


# ============================================================
# TOTAL NEW VOTES
# ============================================================

print(
    "\n================================="
)

print(
    "TOTAL NEW VOTES"
)

print(
    "================================="
)


for party in [

    "DEM",
    "REP",
    "IND",
    "NPA",
    "OTHER"

]:

    total = sum(

        x.get(
            party,
            0
        )

        for x in updates

    )


    print(
        party + ":",
        f"{total:+}"
    )


grand_total = sum(

    x["Total New"]

    for x in updates

)


print(
    "TOTAL:",
    f"{grand_total:+}"
)


# ============================================================
# TWEET GENERATOR
# ============================================================

tweet_time = RUN_NOW.strftime(
    "%I %p"
).lstrip("0")


new_dem = sum(

    x.get(
        "DEM",
        0
    )

    for x in updates

)


new_rep = sum(

    x.get(
        "REP",
        0
    )

    for x in updates

)


new_other = sum(

    x.get(
        "IND",
        0
    )

    +

    x.get(
        "NPA",
        0
    )

    +

    x.get(
        "OTHER",
        0
    )

    for x in updates

)


tweet = f"""
🗳️{tweet_time} Florida EV & VBM Update

New votes have been cast in {len(updates)} counties over the last hour, with the largest update coming from {top_three[0]['County'] if top_three else 'No county'} County.

🔵 DEM: {new_dem:+,}
🔴 REP: {new_rep:+,}
🟣 OTHER: {new_other:+,}
🟢 TOTAL: {grand_total:+,}

{statewide_leader}

🔴 Margin Change: {statewide_margin_change}

Largest County Updates
"""


medals = [
    "🥇",
    "🥈",
    "🥉"
]


for medal, county in zip(
    medals,
    top_three
):

    county_other = (

        county.get(
            "IND",
            0
        )

        +

        county.get(
            "NPA",
            0
        )

        +

        county.get(
            "OTHER",
            0
        )

    )


    tweet += f"""

{medal}{county['County']} County

🔵 DEM: {county.get('DEM', 0):+,}
🔴 REP: {county.get('REP', 0):+,}
🟣 OTHER: {county_other:+,}
🟢 TOTAL: {county['Total New']:+,}

"""


tweet += """

#Florida #EarlyVoting #VoteByMail
"""


print(
    "\n================================="
)

print(
    "TWEET DRAFT"
)

print(
    "================================="
)

print(
    tweet
)


# ============================================================
# SAVE LATEST REPORT
# ============================================================

report = f"""
=================================
FLORIDA TURNOUT UPDATE
=================================

Election ID:
{ELECTION_ID}

Run Time:
{RUN_TIME} Eastern Time

Counties Loaded:
{len(df)} / {len(COUNTIES)}

Updated Counties:
{len(updates)}

Unchanged Counties:
{unchanged}

Rejected County Updates:
{len(rejected_counties)}

STATEWIDE TOTALS
=================================

DEM:
{statewide_totals['DEM']:,}

REP:
{statewide_totals['REP']:,}

OTHER:
{statewide_totals['OTHER']:,}

TOTAL:
{statewide_totals['TOTAL']:,}

STATEWIDE SUMMARY
=================================

{statewide_leader}

Margin Change:
{statewide_margin_change}

TOTAL NEW VOTES
=================================

🔵 DEM: {new_dem:+,}
🔴 REP: {new_rep:+,}
🟣 OTHER: {new_other:+,}
🟢 TOTAL: {grand_total:+,}

REJECTED COUNTY UPDATES
=================================
"""


if rejected_counties:

    for rejected in rejected_counties:

        report += f"""

{rejected['County']} ({rejected['Reason'].upper()})

Previous Accepted:
{rejected['Previous Total']:,.0f}

Scraped:
{rejected['Scraped Total']:,.0f}

Action:
Previous county data retained.

"""


else:

    report += """

No county updates were rejected.

"""


report += """

RATING / FORECAST CHANGES
=================================
"""


if rating_changes:

    for change in rating_changes:

        report += f"""

{change['County']}

{change['Old']} → {change['New']}

Margin Move:
{change['Margin Change']:+.3f}

"""


else:

    report += """

No rating changes detected.

"""


report += """

TWEET DRAFT
=================================

"""


report += tweet


with open(
    LATEST_REPORT_FILE,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        report
    )


# ============================================================
# SAVE TIMESTAMPED REPORT
# ============================================================

report_time = RUN_NOW.strftime(
    "%Y-%m-%d_%H-%M-%S"
)


timestamped_report = os.path.join(

    REPORT_DIR,

    f"florida_report_{report_time}.txt"

)


with open(
    timestamped_report,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        report
    )


# ============================================================
# FINAL OUTPUT
# ============================================================

print(
    "\n================================="
)

print(
    "COMPLETE"
)

print(
    "================================="
)

print(
    "Current data:",
    PREVIOUS_FILE
)

print(
    "Latest JSON:",
    LATEST_JSON_FILE
)

print(
    "Tracker:",
    TRACKER_FILE
)

print(
    "History:",
    HISTORY_FILE
)

print(
    "Archive:",
    archive_file
)

print(
    "Latest report:",
    LATEST_REPORT_FILE
)

print(
    "================================="
)
