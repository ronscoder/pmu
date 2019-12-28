import os
import math
from work.models import Site, ShiftedQty, ProgressQty, SurveyQty, ShiftedQtyExtra, ProgressQtyExtra, SiteExtra, DprQty, Log, Resolution, ResolutionLink, Log, Loa
import pandas as pd
from work.data import DISTRICTS_ALLOWED, DIVISIONS_ALLOWED, PROGRESS_QFIELDS, SURVEY_QFIELDS, REVIEW_QFIELDS, DPR_INFRA_FIELDS, SHIFTED_QFIELDS
from django.db.models import F, Sum, Count, Q, FileField
from work.functions import formatString
from work.models import getHabID
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Permission, User, Group
from django.contrib.auth.decorators import login_required
import pdb


def getSite(census, habitation):
    site = None
    additional = False
    habid = getHabID(census=census, habitation=habitation)
    site = Site.objects.filter(hab_id=habid).first()
    if(not site):
        #: if None, look into additional
        site = SiteExtra.objects.filter(hab_id=habid).first()
        if(site):
            if(site.site):
                site = site.site
            else:
                additional = True
    return site, additional


def getSiteData(census, habitation):
    site = getSite(census, habitation)
    survey = SurveyQty.objects.filter(site=site).first()
    progress = ProgressQty.objects.filter(site=site).first()
    return site, survey, progress


def getSiteProgressdf():
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


def checkInfraNil(progress, shifted):
    hasError = False
    res = []
    # values = [getattr(progress, f, 0) or 0 for f in PROGRESS_QFIELDS]
    # qtysum = sum([v for v in values if not v == None])
    try:
        pqtysum = sum([getattr(progress, f, 0) or 0 for f in PROGRESS_QFIELDS])
        sqtysum = sum([getattr(shifted, f, 0) or 0 for f in SHIFTED_QFIELDS])
        if(not (pqtysum > 0 and sqtysum > 0)):
            hasError = True
            res.append({'class': 'error', 'text': '{}: infra is nil'.format(progress)})
        return hasError, res
    except Exception as ex:
        hasError = True
        res.append({'class': 'error', 'text': '{}: {}'.format(progress.site, ex.__str__())})
        return hasError, res


def checkAgainstSurvey(site, progress):
    survey = SurveyQty.objects.filter(site=site).first()
    res = []
    hasError = False
    for f in PROGRESS_QFIELDS:
        print('comparing {} against survey'.format(f))
        try:
            comp = (getattr(progress, f, 0) or 0) > 1.2 * (getattr(survey, f, 0) or 0)  # if access 20%
            if(comp):
                res.append(
                    {'class': 'warning', 'text': '{}: {} executed is more than 20% of {} survey'.format(site, f, f)})
        except Exception as ex:
            res.append(
                    {'class': 'error', 'text': '{}: {}'.format(progress.site, ex.__str__())})
    return hasError, res


def validateProgressFile(file):
    status = []
    hasError = False
    try:
        df = pd.read_excel(file, sheet_name='upload', header=None)
    except Exception as ex:
        hasError=True
        status.append({'class':'error','text': ex.__str__()})
        return hasError, status, None
    data_row = 6
    # check format
    dfTemplate = pd.read_excel('files/progress_report.xlsx', header=None)
    try: 
        columns = dfTemplate.iloc[data_row-1]
        for i in range(24):
            if(df.iloc[data_row-1, i] != columns[i]):
                status.append(
                    {'class': 'error', 'text': 'Format error @: {}'.format(columns[i])})
                hasError = True
        if(hasError):
            return hasError, status, None
        df_data = df[data_row:]
        df_data.iloc[:, 7:23].fillna(value=0, inplace=True)
        df_data.iloc[:, 7:23].replace('', 0, inplace=True)
        df_data = df_data.rename(columns=df.iloc[5, :])
        df_data = df_data.fillna('')
    except Exception as ex:
        return True, [{'class':'error', 'text': ex.__str__()}], None
    return hasError, status, df_data


def _assignQty(pqty, sqty, data):
    fields_shifted = ['acsr', 'cable_3p', 'cable_1p',
                      'pole_8m', 'pole_9m', 'dtr_100', 'dtr_63', 'dtr_25']
    for field in fields_shifted:
        setattr(sqty, field, getattr(data, field + '_shifted', 0))

    fields_progress = ['ht', 'pole_ht_8m', 'lt_3p', 'lt_1p',
                       'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25', 'remark', 'status']
    for field in fields_progress:
        setattr(pqty, field, getattr(data, field, 0))

    return pqty, sqty


def updateProgressSingle(progressdata, updateid, isTest):
    updated = False
    status = []
    hasError = False
    village = formatString(progressdata['village'])
    census = progressdata['census']
    habitation = formatString(progressdata['habitation'])
    site, additional = getSite(census, habitation)
    pqty = None
    sqty = None
    print('Processing... {}'.format(site))
    if(site and not additional):
        sqty = ShiftedQty.objects.filter(site=site).first()
        if(not sqty):
            sqty = ShiftedQty(site=site)
        pqty = ProgressQty.objects.filter(site=site).first()
        if(not pqty):
            pqty = ProgressQty(site=site)
        _assignQty(pqty, sqty, progressdata)

        hasError, warnings = checkAgainstSurvey(site, pqty)
        status.extend(warnings)

        pqty.changeid = updateid
        sqty.changeid = updateid
        status.append(
            {'class': 'success', 'text': 'Updating: {village} {census} {habitation}'.format(**progressdata)})
    elif(site and additional):
        sqty = ShiftedQtyExtra.objects.filter(site=site).first()
        if(not sqty):
            sqty = ShiftedQtyExtra(site=site)
        pqty = ProgressQtyExtra.objects.filter(site=site).first()
        if(not pqty):
            pqty = ProgressQtyExtra(site=site)
        _assignQty(pqty, sqty, progressdata)
        pqty.changeid = updateid
        sqty.changeid = updateid
        status.append(
            {'class': 'success', 'text': 'Updating (additional): {village} {census} {habitation}'.format(**progressdata)})
    else:
        #: another additional site... requires formal approval
        status.append(
            {'class': 'error', 'text': "Unknown site: {village} {census} {habitation}".format(**progressdata)})
        hasError = True
    if(pqty):
        if((not pqty.review == 'not reviewed' ) or (pqty.status == 'completed') or (pqty.cert == True)):
            status.append(
            {'class': 'info', 'text': "skipped: {village} {census} {habitation} completed, under review".format(**progressdata)})            
            return False, status, False
        hasError, errors = checkInfraNil(pqty, sqty)
        status.extend(errors)
    print(isTest, hasError)
    # input('check')
    if(not isTest and not hasError):
        pqty.save()
        sqty.save()
        print('saving...')
        status.append(
            {'class': 'success', 'text': "Updated {village} {census} {habitation}".format(**progressdata)})
        updated = True
    # print(status)
    return hasError, status, updated


def UpdateProgress(file, updateid, isTest):
    status = []
    hasError, dfstatus, dfProgress = validateProgressFile(file)
    updated = False
    if(hasError):
        status.extend(dfstatus)
        # print(status)
        return status
    for index, row in dfProgress.iterrows():
        iferror, stat, updated = updateProgressSingle(row, updateid, isTest)
        status.extend(stat)
    if(updated and not isTest):
        log = Log(model='Progress', changeid=updateid)
        log._save()
    # print(status)
    return status


def getDistrictProgressSummary():
    num_fields = ['ht', 'ht_conductor', 'pole_ht_8m', 'lt_3p', 'lt_1p',
                  'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25']
    df_district = pd.DataFrame(ProgressQty.objects.values(
        district=F('site__district')).annotate(
            *[Sum(f) for f in num_fields],
            completed=Count('status', filter=Q(status='completed')),
            cert=Count('cert', filter=Q(cert=True))
    ))
    df_district.set_index('district', inplace=True)

    df_extra = pd.DataFrame(ProgressQtyExtra.objects.values(
        district=F('site__district')).annotate(
            *[Sum(f) for f in num_fields],
        completed=Count(
                'status', filter=Q(status='completed')),
        cert=Count(
                'cert', filter=Q(cert=True))))
    df_extra.set_index('district', inplace=True)

    if(not df_extra.empty):
        df_district = df_district.add(df_extra, fill_value=0)
    dfProgress = df_district.copy()
    # Add surveyed hab count from SurveyQty
    sqty = SurveyQty.objects.filter(approval_status='approved')
    dfSuveyed = pd.DataFrame(sqty.values(
        district=F('site__district')).annotate(surveyed=Count('site')))
    dfSuveyed.set_index('district', inplace=True)
    df_district['surveyed'] = dfSuveyed

    dpr = DprQty.objects.filter(has_infra=True)
    dfDPR = pd.DataFrame(dpr.values(
        district=F('site__district')).annotate(surveyed=Count('site')))
    dfDPR.set_index('district', inplace=True)
    df_district['DPRHabs'] = dfDPR

    dfDprqty = pd.DataFrame(dpr.values(district=F('site__district')).annotate(
        *[Sum(f) for f in [*DPR_INFRA_FIELDS, 'ht_conductor']]))
    dfDprqty.columns = [f.replace('__sum', '') for f in dfDprqty.columns]
    dfDprqty.set_index('district', inplace=True)
    dfDprqty['section'] = '1. DPR'
    # dfDprqty['pole_ht_8m'] = pd.np.ceil(dfDprqty['ht'] * 15).astype(int)
    # dfDprqty['pole_lt_8m'] = pd.np.ceil(dfDprqty['lt_3p'] * 25 + dfDprqty['lt_1p'] * 22).astype(int)
    dfDprqty['pole_ht_8m'] = dfDprqty['ht'] * 15
    dfDprqty['pole_lt_8m'] = dfDprqty['lt_3p'] * 25 + dfDprqty['lt_1p'] * 22
    dfDprqty['pole_9m'] = (dfDprqty['dtr_100'] +
                           dfDprqty['dtr_63'] + dfDprqty['dtr_25'])*2
    dfDprqty['pole_8m'] = dfDprqty['pole_ht_8m'] + dfDprqty['pole_lt_8m']

    loa = Loa.objects.all()
    dfLoa = pd.DataFrame(loa.values())
    dfLoa['district'] = dfLoa['area']
    dfLoa.set_index('district', inplace=True)
    dfLoa['pole_8m'] = dfLoa['pole_ht_8m'] + dfLoa['pole_lt_8m']
    dfLoa['section'] = '2. LOA'

    dfPQty = df_district.copy()

    dfPQty.columns = [f.replace('__sum', '') for f in dfPQty.columns]
    dfPQty['section'] = '4. Executed'
    dfPQty['pole_9m'] = (dfPQty['dtr_100'] +
                         dfPQty['dtr_63'] + dfPQty['dtr_25'])*2
    dfPQty['pole_8m'] = dfPQty['pole_ht_8m'] + dfPQty['pole_lt_8m']

    dfSurvQty = pd.DataFrame(sqty.values(district=F('site__district')).annotate(
        *[Sum(f) for f in SURVEY_QFIELDS]))
    dfSurvQty.columns = [f.replace('__sum', '') for f in dfSurvQty.columns]
    dfSurvQty['section'] = '3. Approved'
    dfSurvQty.set_index('district', inplace=True)
    dfSurvQty['pole_8m'] = dfSurvQty['pole_ht_8m'] + dfSurvQty['pole_lt_8m']

    sfield = [*SURVEY_QFIELDS, 'pole_8m']
    dfQtyBal = dfLoa[sfield].subtract(dfSurvQty[sfield])
    dfQtyBal['section'] = '5. Balance (LOA)'

    dfExePc = (dfPQty[sfield]/dfLoa[sfield] * 100).fillna(0).astype(int)
    # dfExePc = dfExePc.apply(lambda x : str(x))
    dfExePc['section'] = '6. Completed %'

    dfQty = pd.concat([dfDprqty, dfLoa, dfSurvQty, dfPQty,
                       dfQtyBal, dfExePc], sort=False)
    dfQty.sort_values(by=['district', 'section'], inplace=True)
    dfQty.set_index([dfQty.index, dfQty['section']], inplace=True)
    del dfQty['section']
    display_fields = ['ht_conductor', *DPR_INFRA_FIELDS, 'pole_8m', 'pole_9m']
    dfQty = dfQty[display_fields]
    dfQty.loc[('TOTAL', '1. DPR'),
              display_fields] = dfDprqty[display_fields].sum()
    dfQty.loc[('TOTAL', '2. LOA'),
              display_fields] = dfLoa[display_fields].sum()
    dfQty.loc[('TOTAL', '3. Approved'),
              display_fields] = dfSurvQty[display_fields].sum()
    dfQty.loc[('TOTAL', '4. Executed'),
              display_fields] = dfPQty[display_fields].sum()
    dfQty.loc[('TOTAL', '5. Balance'),
              display_fields] = dfQtyBal[display_fields].sum()
    dfQty.loc[('TOTAL', '6. Completed %'), display_fields] = dfQty.loc[(
        'TOTAL', '4. Executed'), display_fields]/dfQty.loc[('TOTAL', '2. LOA'), display_fields]*100
    dfQty = pd.np.around(dfQty, 1)
    intFields = [f for f in display_fields if ('pole' in f or 'dtr' in f)]
    dfQty.fillna(0, inplace=True)
    dfQty[intFields] = dfQty[intFields].astype(int)

    dfQty.to_excel('outputs/balance_progress.xlsx')
    # additional sites are those not included in DPR
    dfNotDPR = pd.DataFrame(SurveyQty.objects.exclude(site__in=DprQty.objects.values('site')).values(
        district=F('site__district')).annotate(additional=Count('site')))
    dfNotDPR.set_index('district', inplace=True)
    df_district['Non DPR'] = dfNotDPR
    # if(not dfNotDPR.empty):
    #     df_district = df_district.add(dfNotDPR, fill_value=0)

    #: non surveyed
    nonsurveyed = ProgressQty.objects.exclude(site__in=sqty.values('site')).values(
        district=F('site__district')).annotate(non_surveyed=Count('site'))
    dfNonSurveyed = pd.DataFrame(nonsurveyed)
    dfNonSurveyed.set_index('district', inplace=True)

    nonsurveyednosite = ProgressQtyExtra.objects.exclude(site__site__in=SurveyQty.objects.all(
    ).values('site')).values(district=F('site__district')).annotate(non_surveyed=Count('site'))
    dfNonSurveyedNonSite = pd.DataFrame(nonsurveyednosite)
    dfNonSurveyedNonSite.set_index('district', inplace=True)

    if(not dfNonSurveyedNonSite.empty):
        dfNonSurveyed.add(dfNonSurveyedNonSite, fill_value=0)

    df_district['Non Surveyed'] = dfNonSurveyed

    df_district.fillna(0, inplace=True)
    df_district.loc['∑'] = df_district.sum(numeric_only=True)
    int_fields = ['completed', 'cert', 'surveyed', 'DPRHabs', 'Non DPR', 'Non Surveyed', *[f+'__sum' for f in ['pole_ht_8m',
                                                                                                               'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25']]]
    df_district[int_fields] = df_district[int_fields].astype(int)
    df_district.columns = [c.replace('__sum', '') for c in df_district.columns]

    # materials shifted qtys
    num_fields = ['acsr', 'cable_3p', 'cable_1p',
                  'pole_8m', 'pole_9m', 'dtr_100', 'dtr_63', 'dtr_25']
    df_shifted = pd.DataFrame(ShiftedQty.objects.values(district=F('site__district')).annotate(*[Sum(f) for f in
                                                                                                 num_fields
                                                                                                 ]))
    df_shifted.set_index('district', inplace=True)

    df_shiftedExtra = pd.DataFrame(ShiftedQtyExtra.objects.values(district=F('site__district')).annotate(*[Sum(f) for f in
                                                                                                           num_fields
                                                                                                           ]))
    df_shiftedExtra.set_index('district', inplace=True)

    if(not df_shiftedExtra.empty):
        df_shifted = df_shifted.add(df_shiftedExtra, fill_value=0)

    df_shifted.loc['∑'] = df_shifted.sum()
    int_fields = [f+'__sum' for f in ['pole_8m',
                                      'pole_9m', 'dtr_100', 'dtr_63', 'dtr_25']]
    df_shifted[int_fields] = df_shifted[int_fields].astype(int)
    df_shifted.columns = [c.replace('__sum', '') for c in df_shifted.columns]

    df_summary = df_shifted.join(df_district, lsuffix="(shifted)")
    df_summary.columns = [c.replace('__sum', '') for c in df_summary.columns]
    df_summary.to_excel('outputs/progess_summary.xlsx')

    # completed sites
    dfCatsAll = pd.DataFrame(DprQty.objects.filter(has_infra=True).values(district=F('site__district')).annotate(
        dprhab_II=Count('category', filter=Q(category="II")), dprhab_III=Count('category', filter=Q(category="III"))))
    dfCatsAll.set_index('district', inplace=True)
    dfCatsAll['DPR total'] = dfDPR

    completedSites = ProgressQty.objects.filter(
        status='completed').values('site')
    dfCats = pd.DataFrame(DprQty.objects.filter(site__in=completedSites).values(district=F('site__district')).annotate(
        completed_II=Count('category', filter=Q(category="II")), completed_III=Count('category', filter=Q(category="III"))))
    dfCats.set_index('district', inplace=True)
    dfCats['completed_unassigned'] = (df_district['completed'] - dfCats['completed_II'] -
                                      dfCats['completed_III']).fillna(0).astype(int)
    dfCats['completed_total'] = df_district['completed']

    surveyedSites = SurveyQty.objects.all().values('site')
    dfCatsSurv = pd.DataFrame(DprQty.objects.filter(site__in=completedSites).values(district=F('site__district')).annotate(
        surveyed_II=Count('category', filter=Q(category="II")), surveyed_III=Count('category', filter=Q(category="III"))))
    dfCatsSurv.set_index('district', inplace=True)
    dfCatsSurv['surveyed_unassigned'] = (df_district['surveyed'] - dfCatsSurv['surveyed_II'] -
                                         dfCatsSurv['surveyed_III']).fillna(0).astype(int)
    dfCatsSurv['surveyed_total'] = df_district['surveyed']

    dfCats = pd.concat([dfCatsSurv, dfCatsAll, dfCats], axis=1, sort=True)

    dfCats.loc['∑'] = dfCats.sum()
    fs = ['surveyed_II', 'surveyed_III', 'surveyed_unassigned', 'surveyed_total', 'dprhab_II',
          'dprhab_III', 'DPR total', 'completed_II',	'completed_III', 'completed_unassigned', 'completed_total']
    dfCats[fs] = dfCats[fs].fillna(0).astype(int)

    # remove ht_conductor for progress display
    del df_district['ht_conductor']
    result1 = df_district.to_html(
        na_rep="", justify="center", classes=['datatable'])
    result2 = df_shifted.to_html(
        na_rep="", justify="center", classes=['datatable'])
    result3 = dfCats.to_html(
        na_rep="", justify="center", classes=['datatable'])
    result4 = dfQty.to_html(
        na_rep="", justify="center", classes=['datatable'])

    result = result1 + '<br>Shifted Qty<br>' + result2 + \
        '<br>Categorywise' + result3 + '<BR>Balance' + result4
    result = result.replace("_", " ").title()
    return result


def getLog():
    return Log.objects.values()[::-1][:20]
