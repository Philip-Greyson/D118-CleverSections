"""Script to take course and section data from PowerSchool and put it in the correct format for upload to Clever.

https://github.com/Philip-Greyson/D118-CleverSections

Needs pysftp: pip install pysftp
Needs oracledb: pip install oracledb
"""

# importing modules
import os
from datetime import datetime

import oracledb
import pysftp

DB_UN = os.environ.get('POWERSCHOOL_READ_USER')  # username for read-only database user
DB_PW = os.environ.get('POWERSCHOOL_DB_PASSWORD')  # the password for the database account
DB_CS = os.environ.get('POWERSCHOOL_PROD_DB')  # the IP address, port, and database name to connect to

#set up sftp login info, stored as environment variables on system
SFTP_UN = os.environ.get('CLEVER_SFTP_USERNAME')
SFTP_PW = os.environ.get('CLEVER_SFTP_PASSWORD')
SFTP_HOST = os.environ.get('CLEVER_SFTP_ADDRESS')
CNOPTS = pysftp.CnOpts(knownhosts='known_hosts')  # connection options to use the known_hosts file for key validation

OUTPUT_FILE_NAME = 'Sections.csv'

print(f"Database Username: {DB_UN} |Password: {DB_PW} |Server: {DB_CS}")  # debug so we can see where oracle is trying to connect to/with
print(f'SFTP Username: {SFTP_UN} | SFTP Password: {SFTP_PW} | SFTP Server: {SFTP_HOST}')  # debug so we can see what info sftp connection is using

VALID_SUBJECTS = ['English/language arts', 'Math', 'Science', 'Social studies', 'Language', 'Homeroom/advisory', 'Interventions/online learning', 'Technology and engineering', 'PE and health', 'Arts and music', 'other']  # the supported values of course subjects from the Clever documentation
SUBJECT_MAP = {'Eng': 'English/language arts', 'Mat': 'Math', 'Gls' : 'Social studies', 'Gov': 'Social studies', 'Uhi': 'Social studies', 'Pe': 'PE and health', 'Sci': 'Science', 'Hlt': 'PE and health', 'Social Studies': 'Social studies', 'Socialstudies': 'Social studies'}

if __name__ == '__main__':  # main file execution
    with open('sections_log.txt', 'w') as log:
        startTime = datetime.now()
        startTime = startTime.strftime('%H:%M:%S')
        print(f'INFO: Execution started at {startTime}')
        print(f'INFO: Execution started at {startTime}', file=log)
        with open(OUTPUT_FILE_NAME, 'w') as output:  # open the output file
            print('"School_id","Section_id","Teacher_id","Teacher_2_id","Teacher_3_id","Teacher_4_id","Teacher_5_id","Teacher_6_id","Teacher_7_id","Teacher_8_id","Teacher_9_id","Teacher_10_id","Course_name","Course_number","Section_number","Period","Subject","Grade","Term_start","Term_end","Term_name"', file=output)  # print out the header row
            try:
                with oracledb.connect(user=DB_UN, password=DB_PW, dsn=DB_CS) as con:  # create the connecton to the database
                    with con.cursor() as cur:  # start an entry cursor
                        print(f'INFO: Connection established to PS database on version: {con.version}')
                        print(f'INFO: Connection established to PS database on version: {con.version}', file=log)

                        # first we need to find all school ids, ignoring schools that are exluded from state reporting
                        cur.execute('SELECT school_number, name FROM schools WHERE state_excludefromreporting = 0')
                        schools = cur.fetchall()
                        for school in schools:
                            yearID = None  # reset the year ID to null for each school at the start so that if we dont find a year we skip trying to find sections
                            yearExpression = None  # we will keep the common language year expression in this term, reset it each school
                            schoolID = school[0]
                            print(f'DBUG: Found school with id {schoolID}: {school[1]}')
                            print(f'DBUG: Found school with id {schoolID}: {school[1]}', file=log)
                            # next find the current termyear and terms in that year
                            today = datetime.now()  # store todays datetime for comparison
                            cur.execute('SELECT firstday, lastday, yearid FROM terms WHERE schoolid = :school AND isyearrec = 1', school=schoolID)  # search for only year terms to narrow our list
                            years = cur.fetchall()
                            for year in years:
                                if (year[0] < today) and (year[1] > today):
                                    yearID = year[2]  # store that terms yearcode into yearID so we can use it to search for all terms this year
                                    print(f'DBUG: Found current year code for school {schoolID} to be {yearID}')
                                    print(f'DBUG: Found current year code for school {schoolID} to be {yearID}', file=log)

                            # now find all terms that are in the termyear we found above, so we can find past/future semesters/quarters in the same school year
                            try:
                                if yearID:
                                    cur.execute('SELECT id, firstday, lastday, schoolid, yearid, abbreviation, isyearrec FROM terms WHERE schoolid = :school AND yearid = :year ORDER BY id', school=schoolID, year=yearID)
                                    terms = cur.fetchall()
                                    for term in terms:
                                        try:
                                            # print(f'DBUG: Found term {term}')
                                            termID = term[0]
                                            termStart = term[1].strftime('%m/%d/%Y')
                                            termEnd = term[2].strftime('%m/%d/%Y')
                                            termName = str(term[5])
                                            isFullYear = True if term[6] == 1 else False
                                            if isFullYear:
                                                if not yearExpression:
                                                    yearExpression = termName  # store the termname in the year expression. for us the yearlong term name abbreviations are always like 24-25 so this makes sense as the year expression
                                                termName = f'Year {termName}'  # add the term "year" in front of the year expression for full year terms
                                            else:
                                                termName = f'{termName} {yearExpression}'  # for nonyear terms (Q1, S2, etc) add the year expression on the end so we can visually see at a glance when going through the data browser what year it belongs to
                                            print(f'DBUG: Found term {termName} with ID {termID} that goes from {termStart} until {termEnd}')
                                            print(f'DBUG: Found term {termName} with ID {termID} that goes from {termStart} until {termEnd}', file=log)
                                            # for each term, look for sections in that term
                                            cur.execute('SELECT sections.id, sections.section_number, sections.course_number, sections.grade_level, sections.expression, courses.course_name, courses.credittype FROM sections LEFT JOIN courses ON sections.course_number = courses.course_number WHERE sections.termid = :term AND sections.schoolid = :school', term=termID, school=schoolID)
                                            sections = cur.fetchall()
                                            for section in sections:
                                                try:
                                                    sectionID = int(section[0])
                                                    sectionNum = str(section[1]) if section[1] else ''
                                                    courseNum = str(section[2]) if section[2] else ''
                                                    gradeLevel = int(section[3]) if section[3] else None
                                                    period = str(section[4]) if section[4] else None
                                                    courseName = str(section[5]) if section[5] else ''
                                                    courseType = str(section[6]).title() if section[6] else None
                                                    # print(section)
                                                    # print(section, file=log)

                                                    # fix the period expression so we dont have the track info since we only have one track at the moment
                                                    if period:  # if there was a period returned
                                                        period = period.split('(')[0]  # remove the (A) track info from the expression so its just the period number
                                                    else:
                                                        period = ''
                                                    # do some fixing of grade levels to change it to what Clever expects
                                                    if gradeLevel:
                                                        if gradeLevel < 0:
                                                            gradeLevel = "Preschool"
                                                        elif gradeLevel > 12 or (gradeLevel > 10 and schoolID != 5):  # if their grade does not make sense, its probably meant to be a range and just doesnt have a hypen in it, fix that
                                                            gradeLevel = str(gradeLevel)  # convert the integer to a string
                                                            gradeLevel = gradeLevel[0] + "-" + gradeLevel[len(gradeLevel)-1]  # take the first character and last character and put a hyphen between them
                                                    else:
                                                        gradeLevel = ''

                                                    # process subject a little bit to better conform to Clever supported values
                                                    if courseType:
                                                        if not courseType in VALID_SUBJECTS:  # if the subject does not already match
                                                            courseType = SUBJECT_MAP.get(courseType, '')  # use the subject map to remap the most common strings we get from PS, just return a blank if there is no match
                                                    else:
                                                        courseType = ''  # if there was no course type returned from PS, just set it to a blank

                                                    # for each section we find, we also need to find the teacher and any co-teachers or support staff that are in the section
                                                    try:
                                                        sectionTeachers = []  # create a new empty list each time to store the teachers info in
                                                        cur.execute('SELECT teachers.users_dcid, teachers.first_name, teachers.last_name, roledef.name FROM sectionteacher LEFT JOIN teachers ON sectionteacher.teacherid = teachers.id LEFT JOIN roledef ON sectionteacher.roleid = roledef.id WHERE sectionteacher.sectionid = :section', section=sectionID)
                                                        teachers = cur.fetchall()
                                                        for teacher in teachers:
                                                            # print(teacher, file=log)  # debug
                                                            sectionTeachers.append(teacher[0])  # append their DCID, which is really the only info we need
                                                        if len(sectionTeachers) > 10:  # if the number of staff in the sections is above 10, throw an error since the max Clever supports is 10
                                                            print(f'ERROR: More than 10 teachers which is the maximum supported by Clever for section ID {sectionID}, course name {courseName}')
                                                            print(f'ERROR: More than 10 teachers which is the maximum supported by Clever for section ID {sectionID}, course name {courseName}', file=log)
                                                        else:  # fill in the list so there are always 10 entries. probably a better way to do this but it works
                                                            for i in range(len(sectionTeachers),10):  # get an iterable starting at the length of the array and going through 9. This will fill in blanks for the list to fill it up to 10 entries
                                                                sectionTeachers.append('')  # append a blank entry in the section teachers list
                                                        # print(sectionTeachers, file=log)  # debug

                                                    except Exception as er:
                                                        print(f'ERROR while getting teachers for section with ID {sectionID}: {er}')
                                                        print(f'ERROR while getting teachers for section with ID {sectionID}: {er}', file=log)
                                                    # do final output of section info to output file
                                                    # print(f'{schoolID},{sectionID},{sectionTeachers[0]},{sectionTeachers[1]},{sectionTeachers[2]},{sectionTeachers[3]},{sectionTeachers[4]},{sectionTeachers[5]},{sectionTeachers[6]},{sectionTeachers[7]},{sectionTeachers[8]},{sectionTeachers[9]},{courseName},{courseNum},{sectionNum},{period},{courseType},{termStart},{termEnd},{termName}')
                                                    print(f'{schoolID},{sectionID},{sectionTeachers[0]},{sectionTeachers[1]},{sectionTeachers[2]},{sectionTeachers[3]},{sectionTeachers[4]},{sectionTeachers[5]},{sectionTeachers[6]},{sectionTeachers[7]},{sectionTeachers[8]},{sectionTeachers[9]},{courseName},{courseNum},{sectionNum},{period},{courseType},{gradeLevel},{termStart},{termEnd},{termName}', file=output)
                                                except Exception as er:
                                                    print(f'Error while processing general section info for section ID {sectionID} in building {schoolID}: {er}')
                                                    print(f'Error while processing general section info for section ID {sectionID} in building {schoolID}: {er}', file=log)
                                        except Exception as er:
                                            print(f'ERROR while processing term info or executing section query for term {termID} in building {schoolID}: {er}')
                                            print(f'ERROR while processing term info or executing section query for term {termID} in building {schoolID}: {er}', file=log)
                                else:
                                    print(f'WARN: Could not find a year term in building {schoolID} for todays date of {today}')
                                    print(f'WARN: Could not find a year term in building {schoolID} for todays date of {today}', file=log)
                            except Exception as er:
                                print(f'ERROR while processing terms for building {schoolID} in year ID {yearID}: {er}')
                                print(f'ERROR while processing terms for building {schoolID} in year ID {yearID}: {er}', file=log)
            except Exception as er:
                print(f'ERROR while connecting to PowerSchool or doing query: {er}')
                print(f'ERROR while connecting to PowerSchool or doing query: {er}', file=log)

        try:
            # connect to the Clever SFTP server using the login details stored as environement variables
            with pysftp.Connection(SFTP_HOST, username=SFTP_UN, password=SFTP_PW, cnopts=CNOPTS) as sftp:
                print(f'INFO: SFTP connection to Clever at {SFTP_HOST} successfully established')
                print(f'INFO: SFTP connection to Clever at {SFTP_HOST} successfully established', file=log)
                # print(sftp.pwd) # debug, show what folder we connected to
                # print(sftp.listdir())  # debug, show what other files/folders are in the current directory
                # sftp.put(OUTPUT_FILE_NAME)  # upload the file onto the sftp server
                print("INFO: Sections sync file placed on remote server")
                print("INFO: Sections sync file placed on remote server", file=log)
        except Exception as er:
            print(f'ERROR while connecting or uploading to Clever SFTP server: {er}')
            print(f'ERROR while connecting or uploading to Clever SFTP server: {er}', file=log)

        endTime = datetime.now()
        endTime = endTime.strftime('%H:%M:%S')
        print(f'INFO: Execution ended at {endTime}')
        print(f'INFO: Execution ended at {endTime}', file=log)
