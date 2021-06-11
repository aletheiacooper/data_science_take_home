import requests

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

