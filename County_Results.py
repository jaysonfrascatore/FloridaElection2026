import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os


BASE_URL = "https://s3.amazonaws.com/turnoutquickview.electionsfl.org/data/FL/"


COUNTIES = {

    "Alachua":"ALA",
    "Baker":"BAK",
    "Bay":"BAY",
    "Bradford":"BRA",
    "Brevard":"BRE",
    "Broward":"BRO",
    "Calhoun":"CAL",
    "Charlotte":"CHA",
    "Citrus":"CIT",
    "Clay":"CLA",
    "Collier":"CLL",
    "Columbia":"CLM",
    "DeSoto":"DES",
    "Dixie":"DIX",
    "Duval":"DUV",
    "Escambia":"ESC",
    "Flagler":"FLA",
    "Franklin":"FRA",
    "Gadsden":"GAD",
    "Gilchrist":"GIL",
    "Glades":"GLA",
    "Gulf":"GUL",
    "Hamilton":"HAM",
    "Hardee":"HAR",
    "Hendry":"HEN",
    "Hernando":"HER",
    "Highlands":"HIG",
    "Hillsborough":"HIL",
    "Holmes":"HOL",
    "Indian River":"IND",
    "Jackson":"JAC",
    "Jefferson":"JEF",
    "Lafayette":"LAF",
    "Lake":"LAK",
    "Lee":"LEE",
    "Leon":"LEO",
    "Levy":"LEV",
    "Liberty":"LIB",
    "Madison":"MAD",
    "Manatee":"MAN",
    "Marion":"MRN",
    "Martin":"MRT",
    "Miami-Dade":"DAD",
    "Monroe":"MON",
    "Nassau":"NAS",
    "Okaloosa":"OKA",
    "Okeechobee":"OKE",
    "Orange":"ORA",
    "Osceola":"OSC",
    "Palm Beach":"PAL",
    "Pasco":"PAS",
    "Pinellas":"PIN",
    "Polk":"POL",
    "Putnam":"PUT",
    "Santa Rosa":"SAN",
    "Sarasota":"SAR",
    "Seminole":"SEM",
    "St. Johns":"STJ",
    "St. Lucie":"STL",
    "Sumter":"SUM",
    "Suwannee":"SUW",
    "Taylor":"TAY",
    "Union":"UNI",
    "Volusia":"VOL",
    "Wakulla":"WAK",
    "Walton":"WAL",
    "Washington":"WAS"

}


# ==========================
# FILES
# ==========================
# DATA_DIR holds the fixed-name files the *website* reads (data/previous_turnout.csv
# is the "current" snapshot — it gets overwritten every run and that's the file
# index.html's CSV_PATH points at). ARCHIVE_DIR holds a dated copy of every run
# for history's sake and never gets overwritten, so it'll keep growing over time.

DATA_DIR = "data"
ARCHIVE_DIR = "archive"
REPORT_DIR = "reports"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

PREVIOUS_FILE = os.path.join(DATA_DIR, "previous_turnout.csv")
TRACKER_FILE = os.path.join(DATA_DIR, "county_tracker.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "county_history.csv")


RUN_TIME = datetime.now(ZoneInfo("America/New_York")).strftime(
    "%Y-%m-%d %H:%M:%S"
)



# ==========================
# LOAD MEMORY FILES
# ==========================

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



# ==========================
# DOWNLOAD DATA
# ==========================

rows = []



for county_name, county_code in COUNTIES.items():

    print(
        "Loading:",
        county_name
    )


    totals = {

        "DEM":0,
        "REP":0,
        "IND":0,
        "NPA":0,
        "OTHER":0

    }



    index_url = (
        f"{BASE_URL}"
        f"{county_code}/index.json"
    )



    try:

        index = requests.get(
            index_url,
            timeout=10
        ).json()


    except Exception:

        print(
            "Failed:",
            county_name
        )

        continue



    for location in index:


        data_url = (

            f"{BASE_URL}"
            f"{county_code}/"
            f"{location}/data.json"

        )


        try:

            data = requests.get(
                data_url,
                timeout=10
            ).json()



            parties = (

                data
                .get("Turnout", {})
                .get("PartyType", {})

            )



            for party, value in parties.items():


                ballots = value.get(
                    "Mail",
                    0
                )



                if party in totals:

                    totals[party] += ballots

                else:

                    totals["OTHER"] += ballots



        except Exception:

            continue



    rows.append({

        "Timestamp": RUN_TIME,
        "County": county_name,
        "Code": county_code,
        **totals

    })



df = pd.DataFrame(rows)
# ==========================
# CALCULATIONS
# ==========================

df["TOTAL"] = (
    df["DEM"]
    + df["REP"]
    + df["IND"]
    + df["NPA"]
    + df["OTHER"]
)


major_total = (
    df["DEM"]
    + df["REP"]
)


df["DEM %"] = (
    df["DEM"] /
    major_total
)


df["REP %"] = (
    df["REP"] /
    major_total
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
    lambda x: "D" if x > 0 else "R"
)



def rating(margin):

    margin = abs(margin)


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
    .apply(rating)
)



# ==========================
# CHANGE DETECTION
# ==========================

updates = []

rating_changes = []

rating_history = []

unchanged = 0



# Default columns
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


# Default rating status
df["Rating Change"] = "No"



if previous is not None:

    comparison = df.merge(
        previous,
        on="Code",
        suffixes=("_NEW", "_OLD")
    )

    print(comparison.columns.tolist())


    for _, row in comparison.iterrows():

        changes = {}
        total_change = 0

        # -------------------------
        # Margin Diff Comparison
        # -------------------------

        margin_diff = (
            row["Signed Margin_NEW"]
            -
            row["Signed Margin_OLD"]
        )


        if margin_diff > 0:

            margin_diff_text = (
                f"+{margin_diff:.2%} toward Democrats"
            )

        elif margin_diff < 0:

            margin_diff_text = (
                f"{margin_diff:.2%} toward Republicans"
            )

        else:

            margin_diff_text = "No change"


        df.loc[
            df["Code"] == row["Code"],
            "Margin Diff"
        ] = margin_diff_text


        # -------------------------
        # Rating / Forecast Changes
        # -------------------------
        if (
            row["Rating_NEW"] != row["Rating_OLD"]
            or row["Leader_NEW"] != row["Leader_OLD"]
        ):

            margin_change = (
                row["Signed Margin_NEW"]
                -
                row["Signed Margin_OLD"]
            )


            rating_changes.append({

                "County": row["County"],

                "Code": row["Code"],

                "Old": (
                    f"{row['Rating_OLD']} "
                    f"{row['Leader_OLD']}"
                ),

                "New": (
                    f"{row['Rating_NEW']} "
                    f"{row['Leader_NEW']}"
                ),

                "Margin Change": margin_change

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



        # -------------------------
        # Vote Changes
        # -------------------------
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



        # Store total vote movement
        df.loc[
            df["Code"] == row["Code"],
            "Total New"
        ] = total_change



        # -------------------------
        # Store Updates
        # -------------------------
        if changes:

            updates.append({

                "County": row["County"],

                "Code": row["Code"],

                **changes,

                "Total New": total_change

            })

        else:

            unchanged += 1



else:

    print("\nFirst run detected.")
    print("Creating baseline file...")





# ==========================
# LAST UPDATED TRACKER
# ==========================


tracker_updates = []



for _, row in df.iterrows():


    county_code = row["Code"]


    changed = any(
        x["Code"] == county_code
        for x in updates
    )


    old = tracker[
        tracker["Code"] == county_code
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





# ==========================
# COUNTY HISTORY
# ==========================

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
            item.get("DEM",0),

        "REP New":
            item.get("REP",0),

        "IND New":
            item.get("IND",0),

        "NPA New":
            item.get("NPA",0),

        "OTHER New":
            item.get("OTHER",0),

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





# ==========================
# SAVE FILES
# ==========================


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

    datetime.now(ZoneInfo("America/New_York")).strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    +

    ".csv"

)



df.to_csv(
    archive_file,
    index=False
)


# ==========================
# MANIFEST (so the website can find the latest archive file,
# since its name changes every run)
# ==========================

import json

manifest = {
    "run_time": RUN_TIME,
    "previous_file": PREVIOUS_FILE.replace(os.sep, "/"),
    "archive_file": archive_file.replace(os.sep, "/")
}

with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
    json.dump(manifest, f, indent=2)




# ==========================
# STATEWIDE SUMMARY
# ==========================

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
        f"{state_margin:,} votes statewide."
    )

elif state_margin < 0:

    statewide_leader = (
        f"🔴 Republicans lead by "
        f"{abs(state_margin):,} votes statewide."
    )

else:

    statewide_leader = (
        "The statewide vote is tied."
    )



# ==========================
# STATEWIDE MARGIN CHANGE
# ==========================

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
            f"+{statewide_change:.2%} toward Democrats"
        )

    elif statewide_change < 0:

        statewide_margin_change = (
            f"{statewide_change:.2%} toward Republicans"
        )

    else:

        statewide_margin_change = (
            "No change"
        )


else:

    statewide_margin_change = (
        "First update"
    )



# ==========================
# TOP 3 COUNTY UPDATES
# ==========================

top_three = sorted(
    updates,
    key=lambda x: x["Total New"],
    reverse=True
)[:3]
# ==========================
# CONSOLE REPORT
# ==========================


print("\n=================================")
print("FLORIDA TURNOUT UPDATE")
print("=================================")


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



if len(updates) == 0:

    print(
        "No county changes detected."
    )


else:


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





# ==========================
# TOTAL NEW VOTES
# ==========================


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
        x.get(party,0)
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
# ==========================
# TWEET GENERATOR
# ==========================


tweet_time = datetime.now(ZoneInfo("America/New_York")).strftime(
    "%I %p"
).lstrip("0")



new_dem = sum(
    x.get("DEM", 0)
    for x in updates
)


new_rep = sum(
    x.get("REP", 0)
    for x in updates
)


new_other = sum(
    x.get("IND", 0)
    +
    x.get("NPA", 0)
    +
    x.get("OTHER", 0)
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
        county.get("IND", 0)
        +
        county.get("NPA", 0)
        +
        county.get("OTHER", 0)
    )


    tweet += f"""

{medal}{county['County']} County

🔵 DEM: {county.get('DEM',0):+,}
🔴 REP: {county.get('REP',0):+,}
🟣 OTHER: {county_other:+,}
🟢 TOTAL: {county['Total New']:+,}

"""



tweet += """

#Florida #EarlyVoting #VoteByMail
"""



print(tweet)
# ==========================
# SAVE REPORT TXT FILE
# ==========================

report_time = datetime.now(ZoneInfo("America/New_York")).strftime(
    "%Y-%m-%d_%H-%M-%S"
)


report = f"""
=================================
FLORIDA TURNOUT UPDATE
=================================

Run Time:
{RUN_TIME}


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



# ==========================
# SAVE LATEST REPORT
# ==========================

with open(
    os.path.join(
        REPORT_DIR,
        "latest_report.txt"
    ),
    "w",
    encoding="utf-8"
) as file:

    file.write(report)



# ==========================
# SAVE TIMESTAMP REPORT
# ==========================

with open(
    os.path.join(
        REPORT_DIR,
        f"florida_report_{report_time}.txt"
    ),
    "w",
    encoding="utf-8"
) as file:

    file.write(report)



print(
    "Saved report:",
    f"florida_report_{report_time}.txt"
)
