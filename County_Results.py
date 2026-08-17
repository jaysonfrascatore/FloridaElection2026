import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import re
from html import unescape


# ============================================================
# DATA SOURCES
# ============================================================

BASE_URL = (
    "https://s3.amazonaws.com/"
    "turnoutquickview.electionsfl.org/data/FL/"
)


# Broward uses the ElectionLink turnout-party API
BROWARD_URL = (
    "https://my.browardvotes.gov/"
    "api/v1/widgets/chart"
    "?tile=ptq06000000000000000000000000006"
    "&dashboard=turnout-party"
)


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
# FILES
# ============================================================

DATA_DIR = "data"
ARCHIVE_DIR = "archive"
REPORT_DIR = "reports"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


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


# ============================================================
# RUN TIME
# ============================================================

RUN_TIME = datetime.now(
    ZoneInfo("America/New_York")
).strftime(
    "%Y-%m-%d %H:%M:%S"
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
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):

    """
    Remove HTML tags and return clean text.
    """

    if value is None:
        return ""

    value = unescape(
        str(value)
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def number_from_text(value):

    """
    Convert something like:

        44,784
        41,057
        0

    into an integer.
    """

    if value is None:
        return 0

    value = clean_text(
        value
    )

    value = value.replace(
        ",",
        ""
    )

    match = re.search(
        r"-?\d+",
        value
    )

    if not match:
        return 0

    return int(
        match.group()
    )


def extract_td_texts(row_html):

    """
    Extract the text contained in every <td>
    within a table row.
    """

    cells = re.findall(
        r"<td\b[^>]*>(.*?)</td>",
        row_html,
        flags=re.IGNORECASE | re.DOTALL
    )

    return [
        clean_text(cell)
        for cell in cells
    ]


def get_numeric_ballot_value(value):

    """
    Safely convert a JSON ballot value to an integer.
    """

    if value is None:
        return 0

    if isinstance(value, (int, float)):

        return int(value)

    return number_from_text(
        value
    )


def get_ballot_value(ballot_data, field_names):

    """
    Return the first matching ballot field.

    This allows the script to support the normal
    TurnoutQuickView ElectionDay field while also
    tolerating alternate Election Day naming if
    a county source uses it.
    """

    for field in field_names:

        if field in ballot_data:

            return (
                get_numeric_ballot_value(
                    ballot_data[field]
                ),
                True
            )

    return 0, False


# ============================================================
# BROWARD PARSER
# ============================================================

def get_broward_data():

    """
    Pull Broward County's Voter Turnout By Party
    table from the Broward ElectionLink API.

    Broward's table contains:

        Party
        Eligible Voters
        Vote By Mail
        Early Vote
        Election Day
        Total
        Turnout

    The CSV continues to contain only:

        DEM
        REP
        IND
        NPA
        OTHER

    Internally, VBM / EV / Election Day are parsed
    so we know whether Election Day has been ingested.
    """

    print(
        "  Broward source:",
        "ElectionLink turnout-party API"
    )

    headers = {

        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        ),

        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/json"
        )

    }


    response = requests.get(
        BROWARD_URL,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()


    content = response.text


    totals = {

        "DEM": 0,
        "REP": 0,
        "IND": 0,
        "NPA": 0,
        "OTHER": 0

    }


    # --------------------------------------------------------
    # Election Day detection
    # --------------------------------------------------------

    election_day_found = False


    # --------------------------------------------------------
    # Find table rows
    # --------------------------------------------------------

    rows_html = re.findall(
        r"<tr\b[^>]*>(.*?)</tr>",
        content,
        flags=re.IGNORECASE | re.DOTALL
    )


    found_parties = []


    for row_html in rows_html:

        cells = extract_td_texts(
            row_html
        )


        if len(cells) < 6:

            continue


        party_name = cells[0]


        # Expected:
        #
        # 0 = Party
        # 1 = Eligible Voters
        # 2 = Vote By Mail
        # 3 = Early Vote
        # 4 = Election Day
        # 5 = Total
        # 6 = Turnout


        vbm = number_from_text(
            cells[2]
        )


        ev = number_from_text(
            cells[3]
        )


        election_day = number_from_text(
            cells[4]
        )


        total = number_from_text(
            cells[5]
        )


        # If the Election Day column exists in the
        # Broward table, we consider ED ingested.
        if len(cells) >= 5:

            election_day_found = True


        # ----------------------------------------------------
        # Democratic Party
        # ----------------------------------------------------

        if party_name == (
            "Florida Democratic Party"
        ):

            totals["DEM"] = (
                vbm
                +
                ev
                +
                election_day
            )

            found_parties.append(
                "DEM"
            )


        # ----------------------------------------------------
        # Republican Party
        # ----------------------------------------------------

        elif party_name == (
            "Republican Party Of Florida"
        ):

            totals["REP"] = (
                vbm
                +
                ev
                +
                election_day
            )

            found_parties.append(
                "REP"
            )


        # ----------------------------------------------------
        # No Party Affiliation
        # ----------------------------------------------------

        elif party_name == (
            "No Party Affiliation"
        ):

            totals["NPA"] = (
                vbm
                +
                ev
                +
                election_day
            )

            found_parties.append(
                "NPA"
            )


        # ----------------------------------------------------
        # Other
        # ----------------------------------------------------

        elif party_name == "Other":

            totals["OTHER"] = (
                vbm
                +
                ev
                +
                election_day
            )

            found_parties.append(
                "OTHER"
            )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    expected = {

        "DEM",
        "REP",
        "NPA",
        "OTHER"

    }


    found = set(
        found_parties
    )


    if not expected.issubset(found):

        raise ValueError(
            "Broward party table could not be "
            f"fully parsed. Found: {sorted(found)}"
        )


    # IND does not have its own category in
    # Broward's party turnout table.

    totals["IND"] = 0


    print(
        "  Broward totals:",
        totals
    )


    return totals, election_day_found


# ============================================================
# DOWNLOAD DATA
# ============================================================

rows = []


# Global Election Day detection.
#
# This starts False and becomes True as soon as
# ANY source provides Election Day data.

election_day_ingested = False


for county_name, county_code in COUNTIES.items():

    print(
        "Loading:",
        county_name
    )


    totals = {

        "DEM": 0,
        "REP": 0,
        "IND": 0,
        "NPA": 0,
        "OTHER": 0

    }


    # ========================================================
    # BROWARD SPECIAL SOURCE
    # ========================================================

    if county_code == "BRO":

        try:

            (
                totals,
                broward_ed_found
            ) = get_broward_data()


            if broward_ed_found:

                election_day_ingested = True


        except Exception as e:

            print(
                "Failed:",
                county_name
            )

            print(
                "  Error:",
                str(e)
            )

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


        continue


    # ========================================================
    # ALL OTHER COUNTIES
    # ========================================================

    index_url = (
        f"{BASE_URL}"
        f"{county_code}/index.json"
    )


    try:

        response = requests.get(
            index_url,
            timeout=10
        )

        response.raise_for_status()

        index = response.json()


    except Exception as e:

        print(
            "Failed:",
            county_name
        )

        print(
            "  Error:",
            str(e)
        )

        continue


    for location in index:

        data_url = (

            f"{BASE_URL}"
            f"{county_code}/"
            f"{location}/data.json"

        )


        try:

            response = requests.get(
                data_url,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()


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


                # ------------------------------------------------
                # VOTE BY MAIL
                # ------------------------------------------------

                mail, mail_found = get_ballot_value(
                    value,
                    [
                        "Mail"
                    ]
                )


                # ------------------------------------------------
                # EARLY VOTING
                # ------------------------------------------------

                early_voting, ev_found = get_ballot_value(
                    value,
                    [
                        "EarlyVoting"
                    ]
                )


                # ------------------------------------------------
                # ELECTION DAY
                # ------------------------------------------------

                election_day, ed_found = get_ballot_value(
                    value,
                    [
                        "ElectionDay",
                        "ElectionDayVoting",
                        "ElectionDayVote"
                    ]
                )


                # ------------------------------------------------
                # GLOBAL ELECTION DAY DETECTION
                # ------------------------------------------------

                if ed_found:

                    election_day_ingested = True


                # ------------------------------------------------
                # TOTAL PARTY BALLOTS
                #
                # This is intentionally:
                #
                # VBM + EV + Election Day
                #
                # No separate VBM / EV / ED columns are
                # written to the CSV.
                # ------------------------------------------------

                ballots = (

                    mail
                    +
                    early_voting
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
# ELECTION DAY STATUS
# ============================================================

print(
    "\n================================="
)

print(
    "BALLOT TYPE STATUS"
)

print(
    "================================="
)


if election_day_ingested:

    print(
        "Election Day data detected and ingested."
    )

else:

    print(
        "Election Day not yet ingested"
    )


# ============================================================
# BUILD DATAFRAME
# ============================================================

df = pd.DataFrame(
    rows
)


# ============================================================
# VALIDATION
# ============================================================

if df.empty:

    print(
        "\nERROR: No county data was collected."
    )

    raise SystemExit(1)


print(
    "\nCounties successfully loaded:",
    len(df),
    "/",
    len(COUNTIES)
)


# ============================================================
# BROWARD VERIFICATION
# ============================================================

if "BRO" in df["Code"].values:

    broward_check = df[
        df["Code"] == "BRO"
    ].iloc[0]


    print(
        "\nBroward verification:"
    )


    print(
        "  DEM:",
        f"{int(broward_check['DEM']):,}"
    )


    print(
        "  REP:",
        f"{int(broward_check['REP']):,}"
    )


    print(
        "  NPA:",
        f"{int(broward_check['NPA']):,}"
    )


    print(
        "  OTHER:",
        f"{int(broward_check['OTHER']):,}"
    )


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


# Avoid division by zero.

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


    if margin < .03:

        return "Toss Up"


    elif margin < .08:

        return "Lean"


    elif margin < .15:

        return "Likely"


    else:

        return "Safe"


df["Rating"] = (

    df["Signed Margin"]
    .apply(
        rating
    )

)


# ============================================================
# CHANGE DETECTION
# ============================================================

updates = []

rating_changes = []

rating_history = []

unchanged = 0


# Default columns.

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
# COMPARE AGAINST PREVIOUS RUN
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


    print(
        "\nComparison columns:"
    )


    print(
        comparison.columns.tolist()
    )


    for _, row in comparison.iterrows():

        changes = {}

        total_change = 0


        # ----------------------------------------------------
        # MARGIN DIFF COMPARISON
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
        # RATING / FORECAST CHANGES
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
        # VOTE CHANGES
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
        # TOTAL VOTE MOVEMENT
        # ----------------------------------------------------

        df.loc[

            df["Code"] == row["Code"],

            "Total New"

        ] = total_change


        # ----------------------------------------------------
        # STORE UPDATES
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


    changed = any(

        x["Code"] == county_code

        for x in updates

    )


    old = tracker[

        tracker["Code"]
        ==
        county_code

    ]


    if changed or old.empty:

        last_updated = RUN_TIME


    else:

        last_updated = (

            old.iloc[0]
            ["Last Updated"]

        )


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
            item.get(
                "DEM",
                0
            ),

        "REP New":
            item.get(
                "REP",
                0
            ),

        "IND New":
            item.get(
                "IND",
                0
            ),

        "NPA New":
            item.get(
                "NPA",
                0
            ),

        "OTHER New":
            item.get(
                "OTHER",
                0
            ),

        "Total New":
            item["Total New"]

    })


if history_rows:

    history = pd.DataFrame(
        history_rows
    )


    if os.path.exists(
        HISTORY_FILE
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
# SAVE FILES
# ============================================================

df.to_csv(

    PREVIOUS_FILE,

    index=False

)


tracker.to_csv(

    TRACKER_FILE,

    index=False

)


archive_file = os.path.join(

    ARCHIVE_DIR,

    "florida_turnout_"

    +

    datetime.now(
        ZoneInfo(
            "America/New_York"
        )
    ).strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    +

    ".csv"

)


df.to_csv(

    archive_file,

    index=False

)


# ============================================================
# MANIFEST
# ============================================================

manifest = {

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

    os.path.join(
        DATA_DIR,
        "latest.json"
    ),

    "w"

) as f:

    json.dump(

        manifest,

        f,

        indent=2

    )


# ============================================================
# STATEWIDE SUMMARY
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

    old_dem = previous[
        "DEM"
    ].sum()


    old_rep = previous[
        "REP"
    ].sum()


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


    else:

        statewide_change = 0


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
    RUN_TIME
)


print(
    "\nElection Day Status:"
)


if election_day_ingested:

    print(
        "Election Day data detected and ingested."
    )

else:

    print(
        "Election Day not yet ingested"
    )


print(
    "\nUpdated Counties:",
    len(updates)
)


print(
    "Unchanged Counties:",
    unchanged
)


# ============================================================
# RATING / FORECAST CHANGES
# ============================================================

print(
    "\nRATING / FORECAST CHANGES:"
)


if len(rating_changes) == 0:

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

if len(updates) == 0:

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


print(
    "\n================================="
)

print(
    "COMPLETE"
)

print(
    "Saved:",
    archive_file
)

print(
    "================================="
)


# ============================================================
# TWEET GENERATOR
# ============================================================

tweet_time = datetime.now(

    ZoneInfo(
        "America/New_York"
    )

).strftime(
    "%I %p"
).lstrip(
    "0"
)


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


print(
    "\n================================="
)

print(
    "TWEET DRAFT"
)

print(
    "================================="
)


# ============================================================
# TWEET BALLOT-TYPE LABEL
# ============================================================

if election_day_ingested:

    tweet_ballot_label = (
        "Florida EV, VBM & Election Day Update"
    )

    tweet_hashtags = (
        "#Florida #EarlyVoting #VoteByMail #ElectionDay"
    )

else:

    tweet_ballot_label = (
        "Florida EV & VBM Update"
    )

    tweet_hashtags = (
        "#Florida #EarlyVoting #VoteByMail"
    )


tweet = f"""
🗳️{tweet_time} {tweet_ballot_label}

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


tweet += f"""

{tweet_hashtags}
"""


print(
    tweet
)


# ============================================================
# SAVE REPORT TXT FILE
# ============================================================

report_time = datetime.now(

    ZoneInfo(
        "America/New_York"
    )

).strftime(
    "%Y-%m-%d_%H-%M-%S"
)


report = f"""
=================================
FLORIDA TURNOUT UPDATE
=================================

Run Time:
{RUN_TIME}


Election Day Status:
"""


if election_day_ingested:

    report += (
        "Election Day data detected and ingested.\n"
    )

else:

    report += (
        "Election Day not yet ingested\n"
    )


report += f"""

Updated Counties:
{len(updates)}

Unchanged Counties:
{unchanged}


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

    report += (
        "No rating changes detected.\n"
    )


report += """

TWEET DRAFT
=================================

"""


report += tweet


# ============================================================
# SAVE LATEST REPORT
# ============================================================

with open(

    os.path.join(
        REPORT_DIR,
        "latest_report.txt"
    ),

    "w",

    encoding="utf-8"

) as file:

    file.write(
        report
    )


# ============================================================
# SAVE TIMESTAMP REPORT
# ============================================================

with open(

    os.path.join(
        REPORT_DIR,
        f"florida_report_{report_time}.txt"
    ),

    "w",

    encoding="utf-8"

) as file:

    file.write(
        report
    )


print(
    "Saved report:",
    f"florida_report_{report_time}.txt"
)
