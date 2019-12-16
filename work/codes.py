from work.models import Site, ShiftedQty, ProgressQty, SurveyQty, ShiftedQtyExtra, ProgressQtyExtra, SiteExtra, DprQty, Log, Resolution
from consumers.models import Consumer
import pandas as pd
from .functions import getHabID, formatString
from django.db.models import F, Func


def getCompletedHabs():
    num_fields = ['site__hab_id', 'site__village', 'site__census', 'site__habitation', 'site__district',
                  'status', 'ht', 'pole_ht_8m', 'lt_3p', 'lt_1p', 'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25']
    # dfP = pd.DataFrame(ProgressQty.objects.filter(status='completed')
    dfP = pd.DataFrame(ProgressQty.objects.all()
                       .values(*num_fields))
    dfP.set_index('site__hab_id', inplace=True)
    dfP['rem'] = 'site'
    # dfPX = pd.DataFrame(ProgressQtyExtra.objects.filter(status='completed')
    dfPX = pd.DataFrame(ProgressQtyExtra.objects.all()
                        .values(*num_fields))
    dfPX.set_index('site__hab_id', inplace=True)
    dfPX['rem'] = 'extra'
    #df = dfP.add(dfPX, fill_value=0, numeric_only=True)
    df = pd.concat([dfP, dfPX])
    df.to_excel('outputs/progress_sites.xlsx')
    return df

def assignSite():
    cs = Consumer.objects.all()
    for rec in cs:
        hab_id = getHabID(census=rec.census, habitation=rec.habitation)
        if(Site.objects.filter(hab_id=hab_id).exists()):
            site = Site.objects.get(hab_id=hab_id)
            rec.site = site
            print(hab_id)
            rec.save()

# file = '102LConsumers.xlsx'
# of = pd.ExcelFile(file)
# ss = of.sheet_names[3:]
def importPortalConsumers(file):
    of = pd.ExcelFile(file)
    ss = of.sheet_names[3:]
    dfs = [pd.read_excel(of, sheet_name=s) for s in ss] 
    [df.dropna(inplace=True) for df in dfs] 
    return dfs

def markPortal(df, label):
    for i, row in df.iterrows():
        print('Processing... {}'.format(row))
        consumers = Consumer.objects.filter(census=row['Census Code'], consumer_no=row['Consumer No'], name=row['Name'])
        row['found'] = False
        for consumer in consumers:
            print('Found')
            # input()
            row['found'] = True
            consumer.isInPortal = True
            if(len(consumers) > 1):
                consumer.remark = 'dup'
            consumer.save()
    df.to_excel('Processed '+ label+'.xlsx')
    return df

# dfs = importPortalConsumers(file)
# markPortal(dfs[0], ss[0])
# markPortal(dfs[1], ss[1])
# markPortal(dfs[1], ss[1])
# markPortal(dfs[1], ss[1])
# markPortal(dfs[1], ss[1])

count = 0
def deleteDuplicate():
    for consumer in Consumer.objects.all():
        print(consumer.name)
        if(Consumer.objects.filter(
            consumer_no = consumer.consumer_no.upper(),
            name = consumer.name.upper(),
            habitation = consumer.habitation.upper(),
            census = consumer.census).count()>1):
                row.delete()
                count += 1
                print(count)

count = 0
def makeUpperStrip():
    global count
    for consumer in Consumer.objects.all():
        count += 1
        print(count)
        consumer.habitation = " ".join(consumer.habitation.split()).upper()
        consumer.name = " ".join(consumer.name.split()).upper()
        consumer.consumer_no = " ".join(consumer.consumer_no.split()).upper()
        try:
            consumer.save()
        except:
            consumer.delete()
    

def deleteDups():
    qs = Consumer.objects.all()
    key_set = set()
    delete_ids_list = []
    dup_c_no = []
    for object in qs:
        object_key1 = object.consumer_no
        # object_key2 = object.name 
        # object_key3 = object.habitation 
        # object_key4 = object.census
        # if((object_key1, object_key2, object_key3, object_key4) in key_set):
        # if((object_key1, object_key2, object_key4) in key_set):
        if(object_key1 in key_set):
            # print(object_key2)
            delete_ids_list.append(object.id)
            dup_c_no.append(object.consumer_no)
        else:
            # key_set.add((object_key1, object_key2, object_key3, object_key4))
            # key_set.add((object_key1, object_key2, object_key4))
            key_set.add(object_key1)
    Consumer.objects.filter(id__in=delete_ids_list).delete()
    return delete_ids_list


def stripUpper(s):
    return s.map(lambda x: " ".join(x.__str__().split()).upper())

def ___():
    cols = ['Name', 'Consumer No']
for df in dfs:
    df['Name'] = stripUpper(df['Name'])
    df['Consumer No'] = stripUpper(df['Consumer No'])

# df1['Name'] = stripUpper(df1['Name'])

# consumer_nos = Consumer.objects.all().values_list('consumer_no', flat=True)
# dfNF = []
# for df in dfs:
#     df1 = df[~df['Consumer No'].isin(consumer_nos)]
#     dfNF.append(df1)

# sum = 0
# for df in dfNF:
#     sum += len(df)

# dfa[~dfa['Consumer No'].isin(consumer_nos)]
# dfa[~dfa['Consumer No'].isin(q.values_list('consumer_no'))]
# dfa[~dfa['Consumer No'].isin(f)]
# dfa[~dfa['Consumer No'].isin(['460069'])]

# dfNot = dfNF[0]
# for df in dfNF[1:]:
#     dfNot = dfNot.append(df)
def updateNotFoundConsumers():
    consumerNotFound = 'missingPortalConsumers.xlsx'
    dfNot = pd.read_excel(consumerNotFound)
    consumer_nos = Consumer.objects.all().values_list('consumer_no', flat=True)
    df1 = dfNot[~dfNot['Consumer No'].isin(consumer_nos)]
    df1.to_excel(consumerNotFound)
    print(len(df1))

def markPortalConsumer():
    consumerNotFound = 'missingPortalConsumers.xlsx'
    dfNot = pd.read_excel(consumerNotFound)
    modi = False
    for i, row in dfNot.iterrows():
        print(i)
        consumers = Consumer.objects.filter(census=row['Census Code'], name=row['Name'])
        dropped = False
        for consumer in consumers:
            print('Found')
            consumer.isInPortal = True
            # if(len(consumers) > 1):
            #     consumer.remark = 'dup'
            # consumer.remark = 'truncated'
            consumer.save()
            modi = True
            if(not dropped):
                dfNot = dfNot.drop(i)
                dropped = True
    if(modi):
        print(len(dfNot))
        dfNot.to_excel(consumerNotFound)

from consumers.models import Consumer
count = 0
for consumer in Consumer.objects.all():
    count += 1
    cno = consumer.consumer_no
    consumer.consumer_no = str(consumer.consumer_no).replace(" ","").upper()
    try:
        consumer.save()
    except:
        print('Error {}'.format(cno))
        input()
        consumer.remark = str(consumer.remark) + "dup_cno"
        consumer.consumer_no = cno
        consumer.save()
    print(count)



for row in Site.objects.all():
    try:
        row.habitation = formatString(row.habitation)
        row.village = formatString(row.village)
        row.district = formatString(row.district)
        row.division = formatString(row.division)
        row.save()
    except:
        print(row)
        input()

for row in Site.objects.all():
    try:
        row.hab_id = formatString(row.hab_id)
        row.save()
    except Exception as ex:
        print(row)
        print(ex.__str__())


Site.objects.get(
                    hab_id='270949LONKHU',
                    village='LONKHU',
                    census=270949,
                    habitation='LONKHU',
                    district='CHANDEL',
                    division='CHANDEL')



def movToSite():
    extras = SiteExtra.objects.exclude(site = None)
    progress = ProgressQty.objects.filter(site__in = extras.values('site'))
    progressxtra = ProgressQtyExtra.objects.filter(site__in = extras)


def copyProgress(obj,model):
    return model(**{x:getattr(obj,x) for x in vars(obj) if not x[0]=='_'}).save()

def moveExtraToSite():
# whether in Survey or not can be done by query SurveyQty site
    xsites = SiteExtra.objects.all()
    #1: move xsites to sites
    for sx in xsites:
        if(not sx.site == None):
            copyProgress(sx.progressqtyextra, ProgressQty)
            copyProgress(sx.shiftedqtyextra, ShiftedQty)