#!/Usr/uumath/bin/python3.8

import subprocess
import pandas as pd
import sys
import os
import numpy as np

savethedata = True
#savethedata = False

Include_SANDY = False
Include_AOCE = 0 # 0,1,2. never show, show if enroll>0, always show. for now, don't add into enrollment
Include_All_Sections = False # include Units==0 (e.g., discussion sections)
Merge_CrossList = True  # e.g., ASTR 1060, PHYS 1060
Merge_TaughtTogether = Merge_CrossList  # e.g., PHYS 3610, PHYS 6610 (under same course title)
Last_Ten_Years = True
Long_Listing = False

CatNoFilter = []  # grep-like filters for catalog #s and Instructors. see do_enrollment
InstrFilter = []

NSemestersShown = 0

def setparms(mode):
    global Include_SANDY, Last_Ten_Years, Merge_CrossList, Merge_TaughtTogether, Include_All_Sections, Include_AOCE, Long_Listing
    if "long" in mode:
        Include_SANDY = True; Include_AOCE = True; Include_All_Sections = True 
        Merge_CrossList = False; Merge_TaughtTogether = Merge_CrossList; 
        Last_Ten_Years = False;
        Long_Listing = True
    else:
        # use defaults above 
        pass
    if '-sandy' in mode:
        Include_SANDY = True
    if '-aoce' in mode:
        Include_AOCE = True
    if 'all' in mode:
        Last_Ten_Years = False;
    return

def showparms():
    global Include_SANDY, Last_Ten_Years, Merge_CrossList, Merge_TaughtTogether, Include_All_Sections, Include_AOCE
    print('# List parameters:')
    print('# ')
    print('#    Include SANDY campus info:',Include_SANDY)
    print('#    Include AOCE/Continuing Ed info:',Include_AOCE)
    print('#    Show last ten years only:',Last_Ten_Years)
    print('#    Show all sections, including discussion sections:',Include_All_Sections)
    print('#    Merge crosslisted classes (e.g., ASTR 1060 and PHYS 1060):',Merge_CrossList)
    print('#    Merge classes taught together (e.g., PHYS 3620 and PHYS 6620):',Merge_TaughtTogether)
    print('# ')
    return

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

def usage():
    print('usage:',sys.argv[0],'[-all|-long|-sandy|-listfaculty] arg1 [arg2 arg3...]')
    print('lists courses and enrollments by semester, as provided by the CIS Class Schedule pages.')
    print('args:')
    print('      * a catalog number ("1060") or an instructor name ("Ben") to limit listings accordingly')
    print('      * a semester "S22"=Spring Semester 2022.')
    print('directives')
    print('      -all: show all semesters I could find on CIS (seems to start at 2006; NB: overrides user\'s args).')
    print('      -long: list in a more detailed output format.')
    print('      -sandy: include Sandy campus offerings')
    return


Semester = []
Subject = ["ASTR","PHYS"]
mode = '-enrollment'

if len(sys.argv)>1:
    argv = []
    for a in sys.argv[1:]:
        if a[0]=='-':
            if a in '-long':
                mode += a
            elif a in '-listfaculty' or a in '-faculty':
                mode += '-listfaculty'
                mode = mode.replace('-enrollment','')
            elif a.lower() in '-sandy':
                mode += '-sandy'
            elif a.lower() in '-all':
                mode += '-all'
            elif a.lower() in '-aoce':
                mode += '-aoce'
            elif a.lower() in '--Help' or a[:2] == '-h':
                usage()
                quit()
            else:
                print('unknown command-line option',a)
                quit()
        else:
            argv.append(a)
    if len(argv):
        ok = True
        argvx = []
        Semester = []
        for s in argv:
            s = s.upper()
            if len(s)!=3: ok = False
            if not s[0] in 'SFU': ok = False
            if not s[1:].isdigit: ok = False
            if ok:
                Semester.append(s)
            else:
                argvx.append(s)
        if '-all' in mode:
            Semester = [] # override individual semesters if all is a directive.
        argv = argvx
        Semester = [invsemx(s) for s in Semester]
        # grep-like course numbers or fac names
        CatNoFilter,InstrFilter = [],[]
        for g in argv:
            if (len(g)==3 or len(g)==4) and g.isdigit():
                CatNoFilter.append(g)
            else:
                InstrFilter.append(g.upper())


setparms(mode)

if len(Semester)<1:
    from datetime import datetime
    thismonth = datetime.now().month
    thisyear = datetime.now().year
    startyear = 2006
    if Last_Ten_Years: startyear = thisyear-10

    for yr in range(startyear,thisyear+1):
        yrstr = '%02d'%(yr-2000)
        for semcode in ['4','6','8']:
            if yr==thisyear and thismonth <= (int(semcode)-4)*2: break
            Semester.append(int('1'+yrstr+semcode))


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


def informal_names(nms):
    nmsinf = []
    for nm in nms.split('|'):
        nmx = nm.replace('&#39;',"'")
        nmx = nmx.title()
        lf = nmx.split(',')
        nmx = lf[1].strip().split()[0]+' '+lf[0].strip()
        if 'Robert Spring' in nmx: nmx = nmx.replace('Robert S','Wayne S')
        if 'Zeev V' in nmx: nmx = nmx.replace('Zeev V','Valy V')
        nmsinf.append(nmx)
    return '; '.join(nmsinf)

def do_enrollment(df,subjlist=Subject,merge_xlist=Merge_CrossList,merge_cotaught=Merge_TaughtTogether,\
                  all_secs=Include_All_Sections,include_SANDY=Include_SANDY,include_AOCE=Include_AOCE,\
                  long_list=Long_Listing,verbose=True):
    # AOCE are continuing ed, 3 digit catnos. 0=never show, 1=show if enrollment>0, 2=always show
    global columns,CatNoFilter,InstrFilter,NSemestersShown # make these cmd line args? yes, eventually....
    dfx = df.copy() #  pd.DataFrame(columns=columns)
    dfx.MyField = pd.to_numeric(dfx.Units,errors='coerce')  # myfield is numerical units!!!
    dfx[dfx.MyField==np.nan].MyField = -1.0
    msk = [True]*len(dfx.index)
    if  all_secs == False:
        msk &= dfx.MyField>=0  # don't include anything with undefined units
    if include_SANDY == False:
        msk &= ~(dfx.Location.str.contains('SANDY')|((dfx.CatNo.str[0]=='2')&(dfx.Section.str.contains('070'))))
    if include_AOCE == 0:
        msk &= dfx.CatNo.str.len()>3
    else:
        msk &= dfx.CatNo.str.len()>0 # put AOCE back in 
    if len(CatNoFilter)>0:
        msk &= dfx.CatNo.str.contains('|'.join(CatNoFilter)) # this is fucking awesome, quoting Macklemore
    if len(InstrFilter)>0:
        msk &= dfx.Instructor.str.contains('|'.join(InstrFilter))
    dfx = dfx[msk]
    if merge_xlist or merge_cotaught:
        dfx.MyField = (dfx.MyField>0).astype(str)
        msk = (dfx.duplicated(subset=["Instructor","Title","MyField"],keep=False))
        dfx.MyField[msk] = dfx.Instructor[msk]+dfx.Title[msk]
        xlis = sorted(set(dfx.MyField[msk].tolist()))
        for x in xlis:
            msk2 = (dfx.MyField==x) & msk
            subjx,cnox,enx = dfx.Subj[msk2].tolist(),dfx.CatNo[msk2].tolist(),dfx.Enrollment[msk2].astype(int).sum()
            if len(set(cnox))==1 and len(set(subjx))==1: # probably a lab or discussion section, not a xlist
                continue
            merged = False
            if len(set(subjx))>1 and len(set(cnox))==1 and merge_xlist: # we're merging classes across subjects # assume only one catno
                merged = True
                subj = '+'.join(sorted(subjx))
                dfx.Subj[msk2] = subj
            elif len(set(cnox))>1 and len(set(subjx))==1 and merge_cotaught: # we're merging classes across catnos w/ only one subject
                merged = True
                cno = '+'.join(sorted(cnox))
                dfx.CatNo[msk2] = cno
            elif len(set(cnox))>1 and len(set(subjx))>1 and merge_xlist and merge_cotaught:
                # multiple subjects and multiple catnos, no way to test this yet!
                merged = True
                subj = '/'.join(subjx)
                cno = '/'.join(cnox)
                dfx.CatNo[msk2] = cno
                dfx.Subj[msk2] = subj
            if merged:
                dfx.MyField[msk2] = 'DUPLICATE'
                j1 = np.argmax(msk2)
                msk2[msk2] = False
                msk2.iat[j1]=True  # select the one class to save, will be getting rid of the duplicate(s)
                dfx.MyField[msk2] = 'SAVE'
                dfx.Enrollment[msk2] = enx
        dfx = dfx[~(dfx.MyField == 'DUPLICATE')]

    if verbose and len(dfx.index):
        if NSemestersShown == 0:
            print('# Semester Subj Course-Section: Enrollment',end='')
            print(' + more info!',end='')
            print('')
            NSemestersShown += 1
    
        zz = zip(dfx.Semester,dfx.Subj,dfx.CatNo,dfx.Section,dfx.Enrollment,\
                 dfx.Instructor,dfx.Component,dfx.Units,dfx.Title,dfx.Location)
        for se,su,cno,sec,en,instr,comp,un,ti,loc in zz:
            #print(se,su,cno,sec,en,instr,comp,un,ti)
            #continue
            sesucno = '%3s %4s %4s'%(se,su,cno)
            if long_list:
                sesucnosec = '%s-%3s units=%s'%(sesucno,sec,un)
                print('%-32s'%(sesucnosec),end='')
            else:
                if len(cno)<4 and int(en)<1 and not show_all_sections:
                    continue
                print('%-20s'%(sesucno),end='')
            print(' %3s     '%(en),end='')
            moin = ''
            if long_list:
                instr = instr.replace('|','; ')
                moin += '"%s"; comp=%s; loc=%s; %s'%(ti,comp,loc,instr)
            else:
                instr = informal_names(instr)
                moin += '%-26s %s '%(ti,instr)
            print('%s'%(moin),end='')
            print('')
    return dfx

FacLis = []
FacEn = {}

def do_faclist(df,summary=False,summarysort="a-z"):
    if summary:
        fl = [f for f in FacEn]
        if summarysort == 'a-z':
            fl = sorted(fl)
        elif 'enroll' in summarysort:
            en = [FacEn[f] for f in fl]
            enfl = sorted(zip(en,fl))
            fl = [f for e,f in enfl]
        for f in fl:
            print(f,' total enrollment:',FacEn[f])
        return
    facnames = []
    for fac in df.Instructor:
        for f in fac.split('|'):
            facnames.append(f)
    facnames = sorted(list(set(facnames)))
    for f in facnames:
        msk = df.Instructor.str.contains(f)
        sem,subjs,cnos,secs,ens = df.Semester[msk],df.Subj[msk],df.CatNo[msk],df.Section[msk],df.Enrollment[msk]
        for sm,su,cn,se,en in zip(sem,subjs,cnos,secs,ens):
            print(f,sm,su,cn,se,en)
            if f in FacEn:
                FacEn[f] += int(np.sum(np.int(en)))
            else:
                FacEn[f] = int(np.sum(np.int(en)))

datadir = 'Data' # subdir off of working dir where we keep csv files so we do not have to (slowly) hit CIS

if len(sys.argv) > 1:
    showparms()

for sem in Semester:
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

    Filtered = len(InstrFilter) or len(CatNoFilter)
    if "enroll" in mode:
        if not Filtered:
            do_enrollment(dfsem)
            en, sch = do_census(dfsem)
            for j,subj in enumerate(Subject):
                print('#',semnm,subj,'enrollment, SCH:',en[j],sch[j])
            print('#',semnm,'total enrollment, SCH:',np.sum(np.array(en)),np.sum(np.array(sch)))
        #print(df)
        else: # filtered by course or instructor
            dfx = do_enrollment(dfsem)
            en, sch = do_census(dfx)
            if np.sum(en):
                print('#',semnm,'total enrollment, SCH:',np.sum(np.array(en)),np.sum(np.array(sch)))
            

    if "faculty" in mode:
        dfx = do_enrollment(dfsem,verbose=False)
        do_faclist(dfx)
        
do_faclist('',summary=True,summarysort="enrollment")

if len(sys.argv) == 1:
    showparms()
    usage()

quit()

