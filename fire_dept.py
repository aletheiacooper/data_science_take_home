import requests
import json
import csv
from datetime import datetime, timedelta
import scipy.stats
import sys
import os

file_name = sys.argv[1]
url = "https://data.sfgov.org/resource/RowID.json"
header = {"$$app_token" : "I6QzPzDfpk4SrU7Eo0PBYhyiT"}

if os.path.exists(file_name):
    with open(file_name, "r") as data_file:
        initial_data = json.load(data_file)
else:

    # In production environment, would do error checking in case the data doesn't load properly
    print("Pulling new data, creating new data file")
    params = {"$limit" : 60000}
    response = requests.get(url, headers=header, params=params)
    
    with open(file_name, "w") as output_file:
        json.dump(response.json(), output_file)

    initial_data = json.loads(json.dumps(response.json()))


print("Finished loading data")

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

fire_dept_data_first_60000 = initial_data
before_2010_in_first_60k = len([thing for thing in fire_dept_data_first_60000 if thing["call_date"].find("200") != -1])

print("Total number of rows pulled: " + str(len(fire_dept_data_first_60000)))
print("Rows pulled from before 2010: " + str(before_2010_in_first_60k))

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
            #Assume a zero or negative turnout time is inaccurate
            row["turnout_time"] = turnout_time

task1_data = []

for row in fire_dept_data_first_60000:
    if "turnout_time" in list(row.keys()):
        current_dict = {}
        current_dict["is_evening"] = row["is_evening"]
        current_dict["turnout_time"] = row["turnout_time"]
        task1_data.append(current_dict)

print("Number of rows with turnout time: " + str(len(task1_data)))

evening = [row for row in task1_data if row["is_evening"]]
not_evening = [row for row in task1_data if not row["is_evening"]]

print("Number of evening rows: " + str(len(evening)))

# quick spot check that the turnout times seem different at all

evening_turnouts = [row["turnout_time"].seconds for row in evening]
not_evening_turnouts = [row["turnout_time"].seconds for row in not_evening]
                        
evening_average = sum(evening_turnouts)/len(evening)
print("Average turnout time in seconds for evening data: " + str(evening_average))
# Rounds to 82
not_evening_average = sum(not_evening_turnouts)/len(not_evening)
print("Average turnout time in seconds for not-evening data: " + str(not_evening_average))
# Rounds to 62

"""This suggests that in fact the evening turnouts ARE slower.  Let's get more precise.

First of all, we need to decide what p-value we should use.  I plan on running fewer than 100 tests on this data, so a p-value of .01 makes sense.  I will come back and change this if I end up running close to 100 tests or more."""

print("We will accept significance at the p=.01 level.  Please change this if you run close to 100 tests or more.")

u_value, p_value = scipy.stats.mannwhitneyu(evening_turnouts, not_evening_turnouts, alternative="two-sided")

print("Mann Whitney test on evening vs. not-evening turnout times yields a p-value of " + str(p_value))

"""The p-value is ~1.4e-174, so it passes our pre-determined significance test, and I'm willing to say that evening turnouts are slower than non-evening turnouts."""

"""Now for task1, part b.  We need to access the previous call for a given unit, which may very well not be in our subsample. So we need to pull them from the API if possible.  I'm going to just pull the other calls in a given day for that unit, which introduces a small amount of error because of not including consecutive calls that fall on opposite sides of midnight.

I'm ending up needing, for performance reasons, to use a subset of the 60k rows."""

same_day_filename = sys.argv[2]

if os.path.exists(same_day_filename):
    with open(same_day_filename, "r") as same_day_file:
        include_previous_incidents = json.load(same_day_file)

else:
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

        with open(same_day_filename, "w") as output_file:
            json.dump(include_previous_incidents, output_file)

    print("Finished pulling rows for same unit, same day from API.")

print("Total number of rows for same unit, same day is: " + str(len(include_previous_incidents)))

for row in include_previous_incidents:
    row["creation_datetime"] = datetime.strptime(row["dispatch_dttm"], "%Y-%m-%dT%H:%M:%S.000")
        
def previous_incident(incident):
    all_previous = [row for row in include_previous_incidents if row["creation_datetime"] < incident["creation_datetime"]]
    unit_previous = [row for row in all_previous if row["unit_id"] == incident["unit_id"]]
    if len(unit_previous) > 0:
        just_previous = max([row["creation_datetime"] for row in unit_previous])
        previous_incident = [row for row in unit_previous if row["creation_datetime"] == just_previous][0]
        return previous_incident
                            
for row in include_previous_incidents:
    if "available_dttm" in row.keys():
        row["available_datetime"] = datetime.strptime(row["available_dttm"], "%Y-%m-%dT%H:%M:%S.000")

count_errors = 0
for row in include_previous_incidents:
    maybe_previous = previous_incident(row)
    if maybe_previous and "available_datetime" in maybe_previous.keys():
        row["previous_available"] = previous_incident(row)["available_datetime"]
    else:
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

print("Calculated back-to-back-ness for: " + str(len(back_to_backable)) + " rows.")
print("Was unable to find previous incident for: " + str(count_errors) + " rows.")
print("It's perfectly fine for the previous number to be large, but it shouldn't be more than half the rows.")

back_to_back = [row for row in back_to_backable if row["back_to_back"]]
not_back_to_back = [row for row in back_to_backable if not row["back_to_back"]]

b_to_b_turnouts = [row["turnout_time"].seconds for row in back_to_back]
not_b_to_b_turnouts = [row["turnout_time"].seconds for row in not_back_to_back]

b_to_b_average = sum(b_to_b_turnouts)/len(b_to_b_turnouts)
print("Average turnout for back to back calls: " + str(b_to_b_average))
"""34.50961538461539"""
not_b_to_b_average = sum(not_b_to_b_turnouts)/len(not_b_to_b_turnouts)
print("Average turnout for calls with longer gaps: " + str(not_b_to_b_average))
"""60.88715953307393"""

u_value, p_value = scipy.stats.mannwhitneyu(not_b_to_b_turnouts, b_to_b_turnouts, alternative="two-sided")

print("Mann Whitney test on back-to-back vs. not-back-to-back turnout times yields a p-value of " + str(p_value))

for row in fire_dept_data_first_60000:
    if "available_dttm" in row.keys():
        row["available_datetime"] = datetime.strptime(row["available_dttm"], "%Y-%m-%dT%H:%M:%S.000")
        row["total_time"] = row["available_datetime"] - row["creation_datetime"]

all_total = []
all_turnout = []
for row in fire_dept_data_first_60000:
    if "available_dttm" in row.keys() and "turnout_time" in row.keys():
        all_total.append(row["total_time"].seconds)
        all_turnout.append(row["turnout_time"].seconds)

r_value = scipy.stats.pearsonr(all_turnout, all_total)
print("The Pearson r-value for the possible linear correlation between turnout times and total call times is: " + str(r_value))
"""(-0.1719694725893584, 0.0)"""

training_data = fire_dept_data_first_60000[::60]
test_data = fire_dept_data_first_60000[1::60]

print("Selected training data and test data for the predictive model.")
print("Training data has " + str(len(training_data)) + " rows.")
print("Test data has " + str(len(test_data)) + " rows.")

training_total = []

for row in training_data:
    if "total_time" in row.keys():
        training_total.append(row["total_time"].seconds)

predicted_value = sum(training_total)/len(training_total)

print("Created model using training data only.")

has_total_time_test = [row for row in test_data if "total_time" in row.keys()]
total_squared_percent_error = sum([((predicted_value - row["total_time"].seconds)/predicted_value)**2 for row in has_total_time_test])

average_error = total_squared_percent_error/len(test_data)

print("Evaluated model on test data. Average percent error was: " + str(average_error)) 
""">>> average_error
0.8943626452506162"""
