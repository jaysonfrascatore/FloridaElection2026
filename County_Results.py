import requests
import pandas as pd
from datetime import datetime
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


# ============================================================
# COUNTY UPDATE SANITY CHECK
# ============================================================

COUNTY_DROP_SANITY_THRESHOLD = 5000


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


# ============================================================
# LOAD MEMORY FILES
# ============================================================

if os.path.exists(PREVIOUS_FILE):

    previous = pd.read_csv(
        PREVIOUS_FILE
    )

else:

    previous = None


if os.path.exists(TRACKER_FILE):

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

        vbm = get_value(
            "VoteByMail"
        )

        early = get_value(
            "EarlyVote"
        )

        election_day = get_value(
            "ElectionDay"
        )

        total = get_value(
            "Total"
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
            f"    VBM: {vbm:,}"
        )

        print(
            f"    Early Vote: {early:,}"
        )

        print(
            f"    Election Day: {election_day:,}"
        )

        print(
            f"    Total: {total:,}"
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


        # ----------------------------------------------------
        # Reject ONLY this county if >5,000 votes are removed
        # ----------------------------------------------------

        if (
            votes_removed
            >
            COUNTY_DROP_SANITY_THRESHOLD
        ):

            county_name = row["County"]


            print(
                "\n⚠️ REJECTED COUNTY UPDATE:"
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

            print(
                f"  Votes removed: "
                f"{votes_removed:,.0f}"
            )

            print(
                f"  Threshold: "
                f"{COUNTY_DROP_SANITY_THRESHOLD:,}"
            )

            print(
                "  Keeping previous accepted data."
            )


            rejected_counties.append({

                "County":
                    county_name,

                "Code":
                    county_code,

                "Previous Total":
                    previous_total,

                "Scraped Total":
                    scraped_total,

                "Votes Removed":
                    votes_removed

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
        "\nFirst run detected."
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


    if os.path.exists(HISTORY_FILE):

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
            f"\n{rejected['County']}"
        )

        print(
            " Previous Accepted:",
            f"{rejected['Previous Total']:,.0f}"
        )

        print(
            " Scraped:",
            f"{rejected['Scraped Total']:,.0f}"
        )

        print(
            " Votes Removed:",
            f"{rejected['Votes Removed']:,.0f}"
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

{rejected['County']}

Previous Accepted:
{rejected['Previous Total']:,.0f}

Scraped:
{rejected['Scraped Total']:,.0f}

Votes Removed:
{rejected['Votes Removed']:,.0f}

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
