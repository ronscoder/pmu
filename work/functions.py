import re
import pandas as pd

# def getHabID(census, habitation):
#     return re.sub('[\W]+', '', "{}{}".format(census, habitation)).upper()
def getHabID(**kwargs):
    return re.sub('[\W]+', '', "{}{}".format(kwargs['census'], kwargs['habitation'])).upper()

def formatString(x):
    if(not x):
        return x
    return " ".join(x.__str__().split()).upper()


