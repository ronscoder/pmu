import re
from work.models import Site, ShiftedQty, ProgressQty, SurveyQty, ShiftedQtyExtra, ProgressQtyExtra, SiteExtra, DprQty, Log
import pandas as pd


def getHabID(census, habitation):
    return re.sub('[\W]+', '', "{}{}".format(census, habitation)).upper()


def formatString(x):
    if(not x):
        return x
    return " ".join(x.__str__().split()).upper()


def getSiteProgress():
    num_fields = ['site__hab_id', 'site__village', 'site__census', 'site__habitation', 'site__district', 'status',
                  'ht', 'pole_ht_8m', 'lt_3p', 'lt_1p', 'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25']
    dfP = pd.DataFrame(ProgressQty.objects.all().values(*num_fields))
    dfP.set_index('site__hab_id', inplace=True)
    dfP['rem'] = 'site'
    dfPX = pd.DataFrame(ProgressQtyExtra.objects.all().values(*num_fields))
    dfPX.set_index('site__hab_id', inplace=True)
    dfPX['rem'] = 'extra'
    #df = dfP.add(dfPX, fill_value=0, numeric_only=True)
    df = pd.concat([dfP, dfPX])
    df.to_excel('outputs/progress_sites.xlsx')
    return df

