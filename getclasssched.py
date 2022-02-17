#!/usr/uumath/bin/python3.8


import subprocess
import pandas as pd
import sys
import os

savethedata = True
#savethedata = False

semester = []
from datetime import datetime
thismonth = datetime.now().month
thisyear = datetime.now().year

for yr in range(2006,thisyear+1):
    yrstr = '%02d'%(yr-2000)
    for semcode in ['4','6','8']:
        if yr==thisyear and thismonth <= (int(semcode)-4)*2: break
        semester.append(int('1'+yrstr+semcode))

subject = ["PHYS","ASTR"]

#subject = ['PHYS']
#semester = [1218]

columnsenroll = ["ClassNo","Subj","CatNo","Section","Title","Semester","Cap","Wait","Enrollment","Available"]
columns=["Instructor","uNID","ClassNo","Subj","CatNo","Section","Title","Semester","Type","Component","Location","Days","Times","Units","MeetsWith","Fees","Cap","Wait","Enrollment","Available","MyField"]

# spirit of this, we collect whatever is on the CIS pages.
# some fields are lists, but I may just collect them as a delimited string. think about this.

df = pd.DataFrame(columns=columns)

def semx(x):
    si = ((x%10)-4)//2
    return ['S','U','F'][si]+'%02d'%((x-1000)//10)

def invsemx(x):
    y = 1000 + int(x[1:3])*10
    if x[0] == 'S': y += 4
    elif x[0] == 'U': y += 6
    else: y += 8
    return y

# ====

mode = "getenrollment"  
#mode = "listfac" # just list who is teaching


if len(sys.argv)>1:
    if 'all' in sys.argv:
        pass
    else:
        alis = sys.argv[1:] # is this a copy? fuck.
        semester = [invsemx(x) for x in alis]
else:
    print('usage:',sys.argv[0],'all|S22 F12 [etc]')
    quit()

def spandex(x):
    if not 'span' in x: return x.strip()
    return x.split('<span')[1].split('>')[1].split('</span')[0]

def deref(x):
    if '<a ' in x:
        x = x.split('<a ')[1].split('>')[1].split('</a')[0]
    return x

def myappendlist(x,y): # stoopid! add if not already in there?/
    if x=='': return y
    if y in x: return x
    return x+'|'+y

def parselinesClassSched(lines,columns):
    df = pd.DataFrame(columns=columns)
    instrlis = []
    catno,section = "",""
    # build in pandas
    ser = pd.Series(['']*len(columns),index=columns)
    for i,line in enumerate(lines):
        if 'catno=' in line and 'section=' in line:  # should key off ClassNo but I like CatNo & Section
            catnothis = (line.split('catno=')[1]).split('&')[0]
            sectionthis = (line.split('section=')[1]).split('"')[0]
            subjthis = (line.split('subj=')[1]).split('&')[0]
            if catnothis != catno or sectionthis != section: # first time, lets pack this up!
                catno,section = catnothis,sectionthis
                ser.Semester,ser.Subj,ser.CatNo,ser.Section = semnm,subjthis,catno,section
        if 'sections.html' in line:
            title = spandex(lines[i+3]).replace('&amp;','&').strip()
            if title == '':
                title = deref(lines[i+4]).replace('&amp;','&').strip()
            ser.Title = title
        if 'Instructor:' in line:
            instinfo = lines[i+3]
            if not 'faculty.utah.edu' in instinfo:
                print('cannot find instructor.'); quit()
            instrthis = instinfo.split('>')[1].split('<')[0].strip()
            unidthis = instinfo.split('utah.edu/')[1].split('/')[0]
            # instrthis+=' <'+unidthis+'@utah.edu>'
            if not instrthis in instrlis:
                instrlis.append(instrthis)
            ser.Instructor = myappendlist(ser.Instructor,instrthis)
            ser.uNID = myappendlist(ser.uNID,unidthis)
        if 'Class Number:' in line:
            classno = spandex(lines[i+1]);  # this is messy
            if "name=" in classno:
                classno = lines[i+1].split('name=')[1].split('"')[1]
            ser.ClassNo = classno
        if 'Component:' in line:
            comp = spandex(lines[i+1]);
            ser.Component = comp
        if 'Type:' in line:
            typetype = spandex(lines[i+3]).strip()
            ser.Type = typetype
        if 'data-day' in line:
            days = spandex(line).strip()
            ser.Days = myappendlist(ser.Days,days)
        if 'data-time' in line:
            times = spandex('<span '+line).strip()
            ser.Times = myappendlist(ser.Times,times)
        if 'http://map.utah.edu/index.htm' in line:
            loc = deref(line.strip())
            #loc = spandex('<span '+line).strip()
            ser.Location = myappendlist(ser.Location,loc)
        if 'Fees' in line:
            fees = lines[i+1].strip()
            ser.Fees = myappendlist(ser.Fees,fees)
        if 'Units' in line:
            units = spandex(line).strip()
            ser.Units = units
        if 'Meets With' in line:
            for j in range(99):
                if '<li>' in lines[i+2+j]:
                    meetswiththis = lines[i+2+j].split('li>')[1].split('</')[0]
                    ser.MeetsWith = myappendlist(ser.MeetsWith,meetswiththis)
                else:
                    break
        # are we done with this class?
        if (('class="class-info card mt-3"' in line) and (catno != "")) or ("END MAIN CONTENT" in line):
            if len(ser.Instructor)>1:
                df = df.append(ser,ignore_index=True)
            ser = pd.Series(['']*len(columns),index=columns)
    return df

def parselinesEnrollment(lines,columnsenroll):
    df = pd.DataFrame(columns=columnsenroll)
    catno,section = "",""
    # build in pandas
    ser = pd.Series(['']*len(columnsenroll),index=columnsenroll)
    for i,line in enumerate(lines):
        if 'catno=' in line and 'section=' in line: # or look for "description.html"
            catnothis = (line.split('catno=')[1]).split('&')[0]
            sectionthis = (line.split('section=')[1]).split('"')[0]
            subjthis = (line.split('subj=')[1]).split('&')[0]
            if catnothis != catno or sectionthis != section: # first time, lets pack this up!
                catno,section = catnothis,sectionthis
                classnothis = lines[i-2].strip().replace('>','<').split('<')[2] # ugh, extracint from <td>...</td>
                subj = subjthis
                capthis = lines[i+7].strip().replace('>','<').split('<')[2] # ugh, extracint from <td>...</td>
                waitthis = lines[i+8].strip().replace('>','<').split('<')[2] # ugh, extracint from <td>...</td>
                enrollthis = lines[i+9].strip().replace('>','<').split('<')[2] # ugh, extracint from <td>...</td>
                availthis = lines[i+10].strip().replace('>','<').split('<')[2] # ugh, extracint from <td>...</td>
                ser.Semester,ser.Subj,ser.ClassNo,ser.CatNo,ser.Section = semnm,subjthis,classnothis,catno,section
                ser.Cap,ser.Wait,ser.Enrollment,ser.Available = capthis,waitthis,enrollthis,availthis
                check = True if int(ser.Cap)-int(ser.Enrollment)-int(ser.Available)==0 else False
                if not check:
                    print('check',check,ser.Cap,ser.Enrollment,ser.Available)
                    print("we're fucked.")
                    quit()
                df = df.append(ser,ignore_index=True)
    return df

def getClassSched(sem,subj):
    global columns
    text = ""
    cmd = 'curl -s "https://student.apps.utah.edu/uofu/stu/ClassSchedules/main/'+str(sem)+'/class_list.html?subject='+subj+'"  2>&1'
    lines = subprocess.getoutput(cmd)
    for i,line in enumerate(lines): # why?
        text += line
    lines = text.split('\n')
    df = parselinesClassSched(lines,columns)
    return df


def getEnrollment(sem,subj):
    global columnsenroll
    text = ''
    cmd = 'curl -s "https://student.apps.utah.edu/uofu/stu/ClassSchedules/main/'+str(sem)+'/seating_availability.html?subject='+subj+'"  2>&1'
    lines = subprocess.getoutput(cmd)
    for i,line in enumerate(lines):
        text += line
    lines = text.split('\n')
    dfenroll = parselinesEnrollment(lines,columnsenroll)
    return dfenroll

#pd.set_option('max_row', None)
#pd.set_option('max_column', None)

def do_census(df):
    msk = ~df.Units.str.contains('-')
    tot = df.loc[msk].Enrollment.astype(float).sum()
    sch = (df.loc[msk].Enrollment.astype(float)*df[msk].Units.astype(float)).sum()
    return tot,sch
    


datadir = 'Data' # subdir off of working dir where we keep csv files so we do not have to (slowly) hit CIS
for sem in semester:
    semnm = semx(sem)
    totsem,schsem = 0,0
    for subj in subject:
        if subj=='ASTR' and int(sem) < 1074: continue
        
        fname = datadir+'/ClassSched'+str(sem)+'_'+subj+'.csv'
        if savethedata and os.path.isfile(fname):
            #print('reading from',fname)
            df = pd.read_csv(fname, sep=',',na_filter= False,dtype=str)
        else:
            if not os.path.isdir(datadir):
                print('please "mkdir Data" so we have a place to put saved data. or change savethedata to False.')
                quit()
            # get main class schedule info
            df = getClassSched(sem,subj)
            # add in enrollment info
            dfen = getEnrollment(sem,subj)
            #df, dfen should have same order....
            for i,classno in enumerate(df.ClassNo): # bromley you C coward
                en = dfen.loc[dfen['ClassNo'] == classno].iloc[0]
                df.iloc[i].Cap,df.iloc[i].Wait,df.iloc[i].Enrollment,df.iloc[i].Available = en.Cap,en.Wait,en.Enrollment,en.Available 
            print('# writing to',fname)
            df.to_csv(fname,sep=',')

        if mode == "getenrollment":
            print('# Semester Subj Course-Section: Enrollment [more info!]')
            for cno,sec,en,instr,comp,un in zip(df["CatNo"],df["Section"],df["Enrollment"],df["Instructor"],df["Component"],df.Units):
                print('%3s %4s %4s-%3s: %3s      [units: %3s; %-12s; %s]'%(semnm,subj,cno,sec,en,un,comp,instr))
            tot, sch = do_census(df)
            totsem += tot
            schsem += sch
            
        if mode == "getenrollment":
            print('#',semnm,'total enrollment, SCH:',totsem,schsem)
        #print(df)
quit()

if mode == "full": quit()

instrlis = []

for r in rec:
    instr = r.split(',')[0]+','+r.split(',')[1]
    instrlis.append(instr)
    
instrlis = set(instrlis)
instrlis = sorted(instrlis)
for instr in instrlis:
    print(instr)



'''
            #classno = ((line.split('catno=')[1]).split('>')[1]).split('<')[0]
            #section = ((line.split('section=')[1]).split('>')[1]).split('<')[0]
        if 'data-day' in line:
            days = (line.split('data-day="')[1]).split('"')[0]
        if 'data-tim' in line:
            time = (line.split('data-time="')[1]).split('>')[1].split('<')[0]
            instlist.append(str(sem)+' '+classno+' '+section+' '+component+' '+days+' '+time+' '+instruct)
            gotinst = False
        if 'Type' in line:
            isonline = True
            #instlist.append(str(sem)+' '+classno+' '+section+' '+component+' Online '+instruct)
        if 'Component:' in line:
            componentarea = True
        elif  componentarea:
            component = line.split('span')[1].split('>')[1].split('<')[0]
            componentarea = False
            thisdata = str(sem)+' '+classno+' '+section+' '+component+' Online '+instruct
        if 'Instructor:' in line:
            instructarea = True
        if instructarea:
            if 'href' in line:
                instruct = (line.split('>')[1]).split('<')[0]
                gotinst = True
                print(instruct,classno,section)
        if 'href' in line and instructarea:
            instructarea = False

instlist = list(set(instlist))
instlist = sorted(instlist)

#instlist = [semx(x.split(' ')[0])+' '.join(x.split(' ')[1:]) for x in instlist]

newlist = []
for il in instlist: # cull 3-digit classes
    it = il.split(' ')
    snm = semx(int(it[0]))
    classno,section = int(it[1]),int(it[2])
    if classno < 1000: continue
    # if it[3] == "Discussion": continue
    #    if section % 10 != 1: continue
    newlist.append(snm+' '+il)
instlist = newlist

# fucking nightmare...

newlist = []
i = 0
while i<len(instlist)-1: # get rid if dups from mistakes in main code...
    il = instlist[i]
    ill = instlist[i+1]
    ils = il.split()
    ills = ill.split()
    if ils[:4] == ills[:4]:
        if 'Online' in il:
            newlist.append(ill)
        else:
            newlist.append(il)
        i+= 2
    else:
        newlist.append(il)
        i += 1
instlist = newlist


for il in instlist:
    print(il)



quit()

instonly = []
for i in instlist:
    pieces =i.split(' ')
    subj = pieces[0]
    num = int(pieces[1])
    inst = ' '.join(pieces[2:])
    #if num>999:
    #    print(subj,num,inst)
    instonly.append(inst)



# quit()
#instonly = list(set(instonly))
instonly = sorted(instonly)
for i in instonly:
    print(i)

'''
