#!/usr/uumath/bin/python3.8

import subprocess
import pandas as pd
import sys
import os
import numpy as np

savethedata = True
#savethedata = False

Include_SANDY = False
Last_Ten_Years = False
Merge_CrossList = False
Show_All_Sections = False # include Units==0 (e.g., discussion sections)

semester = []
from datetime import datetime
thismonth = datetime.now().month
thisyear = datetime.now().year
startyear = 2006
if Last_Ten_Years: startyear = thisyear-10

for yr in range(startyear,thisyear+1):
    yrstr = '%02d'%(yr-2000)
    for semcode in ['4','6','8']:
        if yr==thisyear and thismonth <= (int(semcode)-4)*2: break
        semester.append(int('1'+yrstr+semcode))

Subject = ["ASTR","PHYS"]

#subject = ['PHYS']
#semester = [1218]

columnsenroll = ["ClassNo","Subj","CatNo","Section","Title","Semester","Cap","Wait","Enrollment","Available"]
columns=["Instructor","uNID","ClassNo","Subj","CatNo","Section","Title","Semester","Type","Component","Location","Days","Times","Units","MeetsWith","Fees","Cap","Wait","Enrollment","Available","MyField"]

# spirit of this, we collect whatever is on the CIS pages.
# some fields are lists, but I may just collect them as a delimited string. think about this.

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

mode = "get enrollment with census"  

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
            ser.Location = myappendlist(ser.Location,loc)
        if "https://sandy.utah.edu/" in line:
            loc = deref(line.strip())
            ser.Location = myappendlist(ser.Location,loc)
        if 'Fees' in line:
            fees = lines[i+1].strip()
            ser.Fees = myappendlist(ser.Fees,fees)
        if 'Units' in line:
            units = spandex(line).strip()
            ser.Units = units.replace(' ','')
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

def do_census(df,subjlist=Subject,include_SANDY=Include_SANDY):
    en = np.zeros(len(subjlist))
    sch = np.zeros(en.shape)
    for i,subj in enumerate(subjlist):
        dfthis = df[df.Subj == subj].copy()
        if len(dfthis.index)==0:
            continue
        dfthis.MyField = pd.to_numeric(dfthis.Units,errors='coerce')
        msk = (dfthis.MyField != np.nan) & (dfthis.MyField > 0.0) & (dfthis.MyField < 99.0)
        if include_SANDY == False:
            msk &= ~(dfthis.Location.str.contains('SANDY')|((dfthis.CatNo.str[0]=='2')&(dfthis.Section.str.contains('070'))))
        en[i] = dfthis.loc[msk].Enrollment.astype(float).sum()
        sch[i] = (dfthis.loc[msk].Enrollment.astype(float)*dfthis[msk].Units.astype(float)).sum()
    return en,sch


def do_enrollment(df,subjlist=Subject,merge_crosslist=Merge_CrossList,show_all_sections=Show_All_Sections,\
                  include_SANDY=Include_SANDY,verbose=True):
    global columns
    dfx = df.copy() #  pd.DataFrame(columns=columns)
    dfx.MyField = pd.to_numeric(dfx.Units,errors='coerce')  # myfield is numerical units!!!
    dfx[dfx.MyField==np.nan].MyField = -1.0
    msk = [True]*len(dfx.index)
    if show_all_sections == False:
        msk &= dfx.MyField>=0  # don't include anything with undefined units
    if include_SANDY == False:
        msk &= ~(dfx.Location.str.contains('SANDY')|((dfx.CatNo.str[0]=='2')&(dfx.Section.str.contains('070'))))
    dfx = dfx[msk]
    if merge_crosslist:
        dfx.MyField = (dfx.MyField>0).astype(str)
        msk = (dfx.duplicated(subset=["Instructor","Title","MyField"],keep=False))
        dfx.MyField[msk] = dfx.Instructor[msk]+dfx.Title[msk]
        xlis = sorted(set(dfx.MyField[msk].tolist()))
        for x in xlis:
            msk2 = (dfx.MyField==x) & msk
            subjx,cnox,enx = dfx.Subj[msk2].tolist(),dfx.CatNo[msk2].tolist(),dfx.Enrollment[msk2].astype(int).sum()
            if len(set(cnox))==1 and len(set(subjx))==1: # probably a lab or discussion section, not a xlist
                continue
            dfx.MyField[msk2] = 'DUPLICATE'
            j1 = np.argmax(msk2)
            msk2[msk2] = False
            msk2.iat[j1]=True  # select the one class to save, will be getting rid of the duplicate(s)
            dfx.MyField[msk2] = 'SAVE'
            if len(set(subjx))>1 and  len(set(cnox))==1: # we're merging classes across subjects # assume only one subject
                subj = '+'.join(sorted(subjx))
                dfx.Subj[msk2] = subj
            elif len(set(cnox))>1 and len(set(subjx))==1: # we're merging classes across catnos # assume only one subject
                cno = '+'.join(sorted(cnox))
                dfx.CatNo[msk2] = cno
            elif len(set(cnox))>1 and len(set(subjx))>1: # multiple subjects and multiple catnos, no way to test this yet!
                subj = '/'.join(subjx)
                cno = '/'.join(cnox)
                dfx.CatNo[msk2] = cno
                dfx.Subj[msk2] = subj
            dfx.Enrollment[msk2] = enx
        dfx = dfx[~(dfx.MyField == 'DUPLICATE')]

    if verbose:
        more_info = True
        print('# Semester Subj Course-Section: Enrollment',end='')
        if more_info: print(' [more info!]',end='')
        print('')
    
        zz = zip(dfx.Semester,dfx.Subj,dfx.CatNo,dfx.Section,dfx.Enrollment,\
                 dfx.Instructor,dfx.Component,dfx.Units,dfx.Title)
        for se,su,cno,sec,en,instr,comp,un,ti in zz:
            #print(se,su,cno,sec,en,instr,comp,un,ti)
            #continue
            sesucno = '%3s %4s %4s'%(se,su,cno)
            if show_all_sections:
                sesucnosec = '%s-%3s units=%s'%(sesucno,sec,un)
                print('%-32s'%(sesucnosec),end='')
            else:
                print('%-20s'%(sesucno),end='')
            print('    %3s     '%(en),end='')
            moin = ''
            if more_info:
                if show_all_sections:
                    moin += '"%s"; %s; '%(ti,comp)
                else:
                    moin += '%-26s '%('"'+ti+'",')
                moin += instr
                print('[%s]'%(moin),end='')
            print('')
    return


datadir = 'Data' # subdir off of working dir where we keep csv files so we do not have to (slowly) hit CIS
for sem in semester:
    semnm = semx(sem)
    totsem,schsem = 0,0
    dfsem = pd.DataFrame(columns=columns) # includes all subjects
    for subj in Subject:
        if subj=='ASTR' and int(sem) < 1074: continue
        
        fname = datadir+'/ClassSched'+str(sem)+'_'+subj+'.csv'
        if savethedata and os.path.isfile(fname):
            df = pd.read_csv(fname, sep=',',na_filter= False,dtype=str)
        else:
            if not os.path.isdir(datadir):
                print('please "mkdir Data" so we have a place to put saved data. or change savethedata to False.')
                quit()
            # get main class schedule info
            df = getClassSched(sem,subj)
            # add in enrollment info
            dfen = getEnrollment(sem,subj)
            # merge enrollment data and classsched data. 
            for i,classno in enumerate(df.ClassNo): # bromley you C coward
                en = dfen.loc[dfen['ClassNo'] == classno].iloc[0]
                df.iloc[i].Cap,df.iloc[i].Wait,df.iloc[i].Enrollment,df.iloc[i].Available = en.Cap,en.Wait,en.Enrollment,en.Available 
            print('# writing to',fname)
            df.to_csv(fname,sep=',')

        dfsem = dfsem.append(df)

    if "enroll" in mode:
        do_enrollment(dfsem)
    if "census" in mode:        
        en, sch = do_census(dfsem)
        for j,subj in enumerate(Subject):
            print('#',semnm,subj,'enrollment, SCH:',en[j],sch[j])
        print('#',semnm,'total enrollment, SCH:',np.sum(np.array(en)),np.sum(np.array(sch)))
        #print(df)
quit()

