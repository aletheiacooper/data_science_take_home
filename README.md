# Fire Department Incident Time Analysis

## Pre-run environment set up
### Tested systems
This code has been tested with python 3.7 on Linux, specifically Amazon Linux 2. It should run without issue on any system with python 3.7 and higher (and possibly earlier versions of python) as long as the pipenv package can be installed with pip.

### Steps to set up

* If you don't have already have it, install a version of python 3, using 3.7 or higher for guaranteed compatibility

If you need help with this please feel free to email me, `aletheiacooper@gmail.com`. I have experience doing this with a variety of systems.

* Ensure pip is installed and working, and that it's installing packages for python 3

If you need help with this, please feel free to email me, `aletheiacooper@gmail.com`. I have experience doing this with a variety of systems.

* Install pipenv by typing this at the command line:

`pip install pipenv`

* At the top level of this repository, start a virtual environment and install the requirements by typing this:

`pipenv install`

## Running the code

### Quick start

* To run the code offline with cached data, which is faster, type:

`pipenv run python fire_dept.py offline_sample_data.json offline_sample_same_day.json`

### General running

* To pull new data, which will take ~20 seconds, you need to give the program the names of the two files where you want the new data to be cached; these files should not already exist. If these are FILENAMEONE.json and FILENAMETWO.json you would type:

`pipenv run python fire_dept.py FILENAMEONE.json FILENAMETWO.json`

If one of the files exists and the other doesn't, new data will only be pulled for the file that doesn't exist.
