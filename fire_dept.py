import requests
import json
import csv
from datetime import datetime, timedelta

response = requests.get("https://data.sfgov.org/resource/RowID.json")
# In production environment, would do error checking in case the data doesn't load properly

json_string = json.dumps(response.json())
fire_dept_data = json.loads(json_string)

# Only loads the first 1000 rows.  Let's see if we can do better.

url = "https://data.sfgov.org/resource/RowID.json"
header = {"$$app_token" : "I6QzPzDfpk4SrU7Eo0PBYhyiT"}
params = {"$limit" : 60000}
response = requests.get(url, headers=header, params=params)

"""This took about 10 seconds, so getting all 5.58 million would take
~1000 seconds assuming I'm not throttled by the website, so at least
15 minutes but probably less than 20, which is not bad as an OPTION to
the analysis if we want to see how we're doing on the whole dataset
but we need something faster as well.
"""

"""Playing around with the filter option on the SFData website, I see
that the whole data set goes back to the year 2000.  Let's see if the first 60k records seem to span the entire time."""

"""I'm re-using the json loading code above, so time to write a function!"""

def load_from_response_to_dict(response):
    json_string = json.dumps(response.json())
    return json.loads(json_string)

fire_dept_data_first_60000 = load_from_response_to_dict(response)
before_2010_in_first_60k = len([thing for thing in fire_dept_data_first_60000 if thing["call_date"].find("200") != -1])

"""This shows me that there are 4504 rows for which the call date is before 2010 in the first 60k records. I think I'm going to move forward with this sample, although I would want to do some more checking that the sample is representative before using it in a production setting."""

""" TIme to look at the data!  There's no substitute for actually seeing the data before starting to deal with it!"""

for row in fire_dept_data_first_60000:
    for column_name in list(row.keys()):
        all_columns.append(column_name)
csv_file = "first_60k.csv"

with open(csv_file, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=all_columns)
    writer.writeheader()
    for data in fire_dept_data_first_60000:
        writer.writerow(data)

"""Ok, looking at the data and the first task, I see there's a
dispatch time that might be when the run is created, and a received
time that might also be that.  A quick spotcheck shows that the
received time seems to be before the dispatch time, so I'll use
received time as the creation time; in a production setting I'd want
to check this assumption.

It's not clear what the "on route" field should be: I'm going to use
the "response" time as that, since it seems to be usually after the dispatch time."""

for row in fire_dept_data_first_60000:
    row["creation_datetime"] = datetime.strptime(row["dispatch_dttm"], "%Y-%m-%dT%H:%M:%S.000")
    if "response_dttm" in list(row.keys()):
        row["response_datetime"] = datetime.strptime(row["response_dttm"], "%Y-%m-%dT%H:%M:%S.000")

# mark evening data

for row in fire_dept_data_first_60000:
    creation_time = row["creation_datetime"].hour
    row["is_evening"] = creation_time >= 22 or creation_time < 6 #creation time 10pm or greater, or before 6am


for row in fire_dept_data_first_60000:
    if "response_datetime" in row.keys():
        turnout_time = row["response_datetime"] - row["creation_datetime"]
        if turnout_time > timedelta(seconds=0):
            #Assume a zero turnout time is inaccurate
            row["turnout_time"] = turnout_time


task1_data = []

for row in fire_dept_data_first_60000:
    if "turnout_time" in list(row.keys()):
        current_dict = {}
        current_dict["is_evening"] = row["is_evening"]
        current_dict["turnout_time"] = row["turnout_time"]
        task1_data.append(current_dict)
