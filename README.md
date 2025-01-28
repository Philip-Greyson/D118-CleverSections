
# D118-CleverSections

Script to synchronize section data from PowerSchool into Clever by outputting to a .csv file and uploading via SFTP to their server.

## Overview

This script is a fairly straightforward passing of data from PowerSchool to Clever. For the most part, it just does a few SQL queries in loops to retrieve all sections for each term in each building, and mostly uses the fields returned directly, but for a few fields there is some massaging of data to get it into a format Clever wants.
The script opens the output file and writes the header row, then does a query to find all schools in the PS instance that are not excluded from state reporting. Once all the schools are retrieved, each school is processed, first finding the current term year by comparing to the current date, and then finding all terms within that term year (so we get all courses in the year, not just the current term). Then each term is iterated through, and all course sections for that term are retrieved. The period, grade level, and subject are massaged a little bit, and then all staff members attached to the section are retrieved. Clever accepts a maximum of 10 staff members, so the staff members are put in a list which is then padded to always contain 10 entries to make the output more simple. All of the section information is output to the .csv file, and once all sections in all terms and buildings are output, the file is closed and uploaded to the Clever SFTP server for import.

## Requirements

The following Environment Variables must be set on the machine running the script:

- POWERSCHOOL_READ_USER
- POWERSCHOOL_DB_PASSWORD
- POWERSCHOOL_PROD_DB
- CLEVER_SFTP_USERNAME
- CLEVER_SFTP_PASSWORD
- CLEVER_SFTP_ADDRESS

These are fairly self explanatory, and just relate to the usernames, passwords, and host IP/URLs for PowerSchool and the Clever SFTP server (provided by them). If you wish to directly edit the script and include these credentials or to use other environment variable names, you can.

Additionally, the following Python libraries must be installed on the host machine (links to the installation guide):

- [Python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html)
- [pysftp](https://pypi.org/project/pysftp/)

**As part of the pysftp connection to the output SFTP server, you must include the server host key in a file** with no extension named "known_hosts" in the same directory as the Python script. You can see [here](https://pysftp.readthedocs.io/en/release_0.2.9/cookbook.html#pysftp-cnopts) for details on how it is used, but the easiest way to include this I have found is to create an SSH connection from a linux machine using the login info and then find the key (the newest entry should be on the bottom) in ~/.ssh/known_hosts and copy and paste that into a new file named "known_hosts" in the script directory.

## Customization

"Out of the box" the script should work assuming you meet the requirements above. However, there are some things that you may want to change to have a better output for some fields:

- `OUTPUT_FILE_NAME` is simply the name of the file that will have the output written to it and which will be uploaded to Clever. You can change this if needed but "Sections.csv" is the default that Clever expects.
- `VALID_SUBJECTS` is a list of the currently accepted Clever subject names. If this changes, or you have a need for other ones, you can add it to this list near the top of the script.
- Similarly, `SUBJECT_MAP` is a dictionary which translates the results that are returned from the PowerSchool courses.credittype field to the expected Clever values. You can add the values that are returned for you courses and which subject they best map to. If the credittype field does not match a valid subject or one in this dictionary, the section will just be output with a blank subject so that Clever can do its best guess to figure out the subject (and it does a pretty good job most of the time).
- The grade level is set to overwrite any grades below 0 to "Preschool" since Clever does not accept negative numbers. If you need to change this to a different value you can just edit that string assignment.
- The script currently strips out the track information from the section expression so that it only leaves the numerical value - i.e. 3(A) just becomes 3. We only have a single schedule track at all our buildings so it is redundant to include this information which only confuses students and staff. If you do not want this to happen, change the `STRIP_TRACK_INFO` constant near the top to `False`
- There are occasions in our district where a section covers multiple grades, but the sections.grade_level is only a number value so the grades are all included in one multi-digit number (i.e a 2-3 grade course would have a grade_level of 23, 3-5 would be 345). To account for this, the script checks if the grade level returned from PS is greater than 12 or greater than 10 when a certain schoolID is not true (in our case, it is the high school schoolID). This way, if there is a grade level that does not make much sense, we convert the integer to a string with a hyphen in the middle by taking the first and last number, so 345 would be correctly converted to 3-5. This might not be how your district handles inputting the grade_level in PS for courses, so you would need to change how that works. Additionally, you will need to change the schoolID that corresponds to whichever building(s) have grade levels that are 10 or above.
- The script currently has no logic in handling sections that have more than 10 staff members attached to them, it will just output the first 10 returned by the query but will log an error in the log to make you aware. Our district does not approach this number except in a tiny handful of cases, so I did not implement anything. If you need to, you will likely want to sort or filter the sectionteacher results by roleid to make sure you include the lead and co-teachers first.
