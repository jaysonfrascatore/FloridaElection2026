import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from bs4 import BeautifulSoup


# ============================================================
# SOURCES
# ============================================================

BASE_URL = (
    "https://s3.amazonaws.com/"
    "turnoutquickview.electionsfl.org/data/FL/"
)

# Broward uses the working ElectionLink turnout-party page
BROWARD_URL = (
    "https://my.browardvotes.gov/"
    "TEDElectionLink/TurnOutWidget/dashboard/view/turnout-party"
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

PREVIOUS_FILE = "previous_turnout.csv"
TRACKER_FILE = "county_tracker.csv"
HISTORY_FILE = "county_history.csv"


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
            "Chrome/151.0 Safari/537.36"

    }


    response = requests.get(
        BROWARD_URL,
        headers=headers,
        timeout=20
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
                f"Could not find Party{party_number}"
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
                    f"{field}{party_number}"
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


            if field == "Turnout":

                return float(text)


            return int(text)


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
        # Store combined total
        # ----------------------------------------------------

        totals[party_code] = total


        # ----------------------------------------------------
        # Store detailed voting method data
        # ----------------------------------------------------

        detailed[f"{party_code} VBM"] = vbm

        detailed[f"{party_code} EV"] = early

        detailed[f"{party_code} ED"] = election_day


        # ----------------------------------------------------
        # Display what was found
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

            detailed[f"{party_code} VBM"]

            +

            detailed[f"{party_code} EV"]

            +

            detailed[f"{party_code} ED"]

        )


        if calculated != totals[party_code]:

            print(
                f"WARNING: {party_code} "
                f"does not match!"
            )

            print(
                f"  VBM + EV + ED = {calculated:,}"
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
    # BROWARD SPECIAL SOURCE
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
                "BROWARD FAILED:"
            )

            print(
                e
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
            timeout=10
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
                timeout=10
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


                # ------------------------------------------------
                # Current live turnout
                #
                # VBM + Early Voting
                #
                # This matches your working local version.
                # ------------------------------------------------

                ballots = (

                    value.get(
                        "Mail",
                        0
                    )

                    +

                    value.get(
                        "EarlyVoting",
                        0
                    )

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


# ============================================================
# VALIDATION
# ============================================================

if df.empty:

    print(
        "\nERROR: No county data was collected."
    )

    raise SystemExit(1)


print(
    "\n================================="
)

print(
    "COUNTY COLLECTION COMPLETE"
)

print(
    "================================="
)

print(
    "Counties loaded:",
    len(df),
    "/",
    len(COUNTIES)
)


if "BRO" not in df["Code"].values:

    print(
        "\nWARNING: BROWARD IS MISSING!"
    )

    raise SystemExit(
        "Broward failed to load."
    )


# ============================================================
# BROWARD VERIFICATION
# ============================================================

broward_check = df[
    df["Code"] == "BRO"
].iloc[0]


print(
    "\nBROWARD VERIFICATION"
)

print(
    "DEM:",
    f"{int(broward_check['DEM']):,}"
)

print(
    "REP:",
    f"{int(broward_check['REP']):,}"
)

print(
    "NPA:",
    f"{int(broward_check['NPA']):,}"
)

print(
    "OTHER:",
    f"{int(broward_check['OTHER']):,}"
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
    /
    major_total.replace(
        0,
        pd.NA
    )

).fillna(0)


df["REP %"] = (

    df["REP"]
    /
    major_total.replace(
        0,
        pd.NA
    )

).fillna(0)


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
                f"toward Democrats"

            )


        elif margin_diff < 0:

            margin_diff_text = (

                f"{margin_diff:.2%} "
                f"toward Republicans"

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


    changed = any(

        x["Code"]
        ==
        county_code

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
# ARCHIVE
# ============================================================

archive_file = (

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
                f"toward Democrats"

            )


        elif statewide_change < 0:

            statewide_margin_change = (

                f"{statewide_change:.2%} "
                f"toward Republicans"

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
    RUN_TIME
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
# RATING CHANGES
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


# ============================================================
# COMPLETE
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
    "Broward:",
    "LOADED"
)

print(
    "Counties:",
    f"{len(df)}/{len(COUNTIES)}"
)

print(
    "Saved:",
    PREVIOUS_FILE
)

print(
    "Archive:",
    archive_file
)

print(
    "================================="
)


# ============================================================
# TWEET GENERATOR
# ============================================================

tweet_time = datetime.now(
    ZoneInfo("America/New_York")
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
    tweet
)
