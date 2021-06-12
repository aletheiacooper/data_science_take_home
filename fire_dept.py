import requests
import json
import csv
from datetime import datetime, timedelta
import scipy.stats

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

""" TIme to look at the data!  There's no substitute for actually seeing the data before sta
rting to deal with it!"""

"""all_columns = []

for row in fire_dept_data_first_60000:
    for column_name in list(row.keys()):
        all_columns.append(column_name)
csv_file = "first_60k.csv"

with open(csv_file, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=all_columns)
    writer.writeheader()
    for data in fire_dept_data_first_60000:
        writer.writerow(data)
"""
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

for row in fire_dept_data_first_60000:
    dispatch_time = row["creation_datetime"].hour
    row["is_evening"] = creation_time >= 22 or creation_time < 6 #creation time 10pm or greater, or before 6am

task1_data = []

for row in fire_dept_data_first_60000:
    if "turnout_time" in list(row.keys()):
        current_dict = {}
        current_dict["is_evening"] = row["is_evening"]
        current_dict["turnout_time"] = row["turnout_time"]
        task1_data.append(current_dict)

evening = [row for row in task1_data if row["is_evening"]]
not_evening = [row for row in task1_data if not row["is_evening"]]

# quick spot check that the turnout times seem different at all

evening_turnouts = [row["turnout_time"].seconds for row in evening]
not_evening_turnouts = [row["turnout_time"].seconds for row in not_evening]
                        
evening_average = sum(evening_turnouts)/len(evening)
# Rounds to 82
not_evening_average = sum(not_evening_turnouts)/len(not_evening)
# Rounds to 62

"""This suggests that in fact the evening turnouts ARE slower.  Let's get more precise.

First of all, we need to decide what p-value we should use.  I plan on running fewer than 100 tests on this data, so a p-value of .01 makes sense.  I will come back and change this if I end up running close to 100 tests or more."""

u_value, p_value = scipy.stats.mannwhitneyu(evening_turnouts, not_evening_turnouts, alternative="two-sided")

"""The p-value is ~1.4e-174, so it passes our pre-determined significance test, and I'm willing to say that evening turnouts are slower than non-evening turnouts."""

"""Now for task1, part b.  We need to access the previous call for a given unit, which may very well not be in our subsample. So we need to pull them from the API if possible.  I'm going to just pull the other calls in a given day for that unit, which introduces a small amount of error because of not including consecutive calls that fall on opposite sides of midnight.

I'm ending up needing, for performance reasons, to use a subset of the 60k rows."""

include_previous_incidents = []

for row in fire_dept_data_first_60000[::600]:
    begin_day_of_call = datetime.strftime(row["creation_datetime"], "%Y-%m-%dT00:00:00.000")
    end_day_datetime = row["creation_datetime"] + timedelta(days=1)
    end_day_of_call = datetime.strftime(end_day_datetime, "%Y-%m-%dT00:00:00.000")
    unit = row["unit_id"]
    params = {}
    params["unit_id"] = unit
    q = "dispatch_dttm between '" + begin_day_of_call + "' and '" + end_day_of_call + "'"
    params["$where"] = q
    response = requests.get(url, headers=header, params=params)
    new_rows = load_from_response_to_dict(response)
    for new_row in new_rows:
        include_previous_incidents.append(new_row)


for row in include_previous_incidents:
    row["creation_datetime"] = datetime.strptime(row["dispatch_dttm"], "%Y-%m-%dT%H:%M:%S.000")
        
def previous_incident(incident):
    all_previous = [row for row in include_previous_incidents if row["creation_datetime"] < incident["creation_datetime"]]
    unit_previous = [row for row in all_previous if row["unit_id"] == incident["unit_id"]]
    just_previous = max([row["creation_datetime"] for row in unit_previous])
    if len(unit_previous) > 0:
        previous_incident = [row for row in a_i if row["creation_datetime"] == just_previous][0]
    return previous_incident
                            
for row in include_previous_incidents:
    row["available_datetime"] = datetime.strptime(row["available_dttm"], "%Y-%m-%dT%H:%M:%S.000")

count_errors = 0
for row in include_previous_incidents:
    try:
        row["previous_available"] = previous_incident(row)["available_datetime"]
    except:
        print("Errored on previous_incident function")
        count_errors += 1
        continue
    row["gap"] = row["creation_datetime"] - row["previous_available"]
    row["back_to_back"] = row["gap"] <= timedelta(minutes=10)
    
    
    

    
for row in include_previous_incidents:
    if "response_dttm" in list(row.keys()):
        row["response_datetime"] = datetime.strptime(row["response_dttm"], "%Y-%m-%dT%H:%M:%S.000")
        turnout_time = row["response_datetime"] - row["creation_datetime"]
        if turnout_time > timedelta(seconds=0):
            #Assume a zero turnout time is inaccurate                                       
            row["turnout_time"] = turnout_time

back_to_backable = []
for row in include_previous_incidents:
    if "back_to_back" in row.keys() and "turnout_time" in row.keys():
        back_to_backable.append(row)

back_to_back = [row for row in back_to_backable if row["back_to_back"]]
not_back_to_back = [row for row in back_to_backable if not row["back_to_back"]]

b_to_b_turnouts = [row["turnout_time"].seconds for row in back_to_back]
not_b_to_b_turnouts = [row["turnout_time"].seconds for row in not_back_to_back]


""">>> sum(b_to_b_turnouts)/len(b_to_b_turnouts)
34.50961538461539
>>> sum(not_b_to_b_turnouts)/len(not_b_to_b_turnouts)
60.88715953307393"""

u_value, p_value = scipy.stats.mannwhitneyu(not_b_to_b_turnouts, b_to_b_turnouts, alternative="two-sided")
