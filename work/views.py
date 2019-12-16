from django.shortcuts import render, get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
import os
import math
import mimetypes
from work.models import Site, ShiftedQty, ProgressQty, SurveyQty, ShiftedQtyExtra, ProgressQtyExtra, SiteExtra, DprQty, Log, Resolution, ResolutionLink, Loa
import pandas as pd
from work.data import DISTRICTS_ALLOWED, DIVISIONS_ALLOWED, PROGRESS_QFIELDS, SURVEY_QFIELDS, REVIEW_QFIELDS, DPR_INFRA_FIELDS
from django.core.files import File
import datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import F, Sum, Count, Q, FileField
from work.functions import getSiteProgress, formatString
from work.models import getHabID
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Permission, User, Group
from django.contrib.auth.decorators import login_required


@login_required(login_url='/admin/login/?next=/work/detail/')
@ensure_csrf_cookie
def detail(request):
    return render(request, "work/detail.html", {'districts': DISTRICTS_ALLOWED, 'divisions': DIVISIONS_ALLOWED})


@login_required(login_url='/admin/login/?next=/work/review/')
@ensure_csrf_cookie
def review(request, pid, additional):
    access = request.user.groups.filter(name__in=['pmu3']).exists()
    noEdit = 0
    if(not access):
        noEdit = 1
    return render(request, "work/review.html", {'pid': pid, 'additional': additional, 'noEdit': noEdit})


def api_deleteDoc(request, model, id):
    print(model, id)
    if(model == 'ProgressQty'):
        q = ProgressQty.objects.get(id=id)
    else:
        q = ProgressQtyExtra.objects.get(id=id)
    q.document.delete()
    # q.save()
    return JsonResponse({'status': "Deleted"})


def api_uploadDoc(request):
    if(not request.method == 'POST'):
        return JsonResponse({'status': 'nothing'})
    model = request.POST['to']
    id = request.POST['id']
    doc = request.FILES['file']
    print('upload doc')
    print(model, id, doc)
    if(model == 'ProgressQty'):
        progress = ProgressQty.objects.get(id=id)
    else:
        progress = ProgressQtyExtra.objects.get(id=id)

    if(not progress):
        return JsonResponse({'status': 'record not found'})

    try:
        progress.document = doc
        progress.cert = True
        progress.save()
    except Exception as ex:
        return JsonResponse({'status': ex.__str__()})
    return JsonResponse({'status': 'success'})


def api_markVariations(request):
    pickedSite = request.POST['pickedSite']
    checkedSites = request.POST['checkedSites'].split(",")
    # print(checkedSites)
    site = Site.objects.get(id=pickedSite)
    siteExtras = SiteExtra.objects.filter(id__in=checkedSites)
    # print(siteExtras.values())
    for sitex in siteExtras:
        sitex.site = site
        sitex.save()
    return JsonResponse({'status': 'success'})


def api_markSiteOrigin(request):
    pickedSite = request.POST['pickedSite']
    checkedSites = request.POST['checkedSites'].split(",")
    # print(checkedSites)
    site = Site.objects.get(id=pickedSite)
    sites = Site.objects.filter(id__in=checkedSites)
    # print(siteExtras.values())
    for s in sites:
        s.origin = site
        s.save()
    return JsonResponse({'status': 'success'})


def api_mergeToSite(request):
    log1 = []
    checkedSites = request.POST['checkedSites'].split(",")
    sitesx = SiteExtra.objects.filter(id__in=checkedSites).exclude(site=None)
    for s in sitesx:
        site = s.site
        print('copying...')
        pq, created1 = ProgressQty.objects.get_or_create(site=site)
        sq, created2 = ShiftedQty.objects.get_or_create(site=site)
        # check for values
        sum_qty = sum([pq.__dict__[f]
                       for f in PROGRESS_QFIELDS if pq.__dict__[f] != None])
        if(sum_qty):
            log1.append(
                {'class': 'warning', 'text': "{}: Existing qtys. Override".format(site)})
            # continue
        px = ProgressQtyExtra.objects.get(site=s)
        sx = ShiftedQtyExtra.objects.get(site=s)
        # copy all values
        pq.ht = px.ht
        pq.pole_ht_8m = px.pole_ht_8m
        pq.lt_3p = px.lt_3p
        pq.lt_1p = px.lt_1p
        pq.pole_lt_8m = px.pole_lt_8m
        pq.dtr_100 = px.dtr_100
        pq.dtr_63 = px.dtr_63
        pq.dtr_25 = px.dtr_25
        pq.remark = px.remark
        pq.status = px.status
        pq.document = px.document
        pq.cert = px.cert
        pq.save()
        sq.acsr = sx.acsr
        sq.cable_3p = sx.cable_3p
        sq.cable_1p = sx.cable_1p
        sq.pole_8m = sx.pole_8m
        sq.pole_9m = sx.pole_9m
        sq.dtr_100 = sx.dtr_100
        sq.dtr_63 = sx.dtr_63
        sq.dtr_25 = sx.dtr_25
        sq.remark = sx.remark
        sq.save()
        s.delete()
        log1.append(
            {'class': 'success', 'text': '{} qtys moved to {}'.format(s, site)})
    return JsonResponse({'status': log1})


def addField(dfqty, header):
    if(not dfqty.empty):
        dfqty['district'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).district)
        dfqty['division'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).division)
        dfqty['habitation'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).habitation)
        dfqty['census'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).census)
        dfqty['village'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).village)
        dfqty['hab_id'] = dfqty['site_id'].apply(
            lambda x: header.get(id=x).hab_id)


def api_getSite(request):
    if(request.method != 'POST'):
        return JsonResponse(
            'nothing to do'
        )
    filterString = {}
    status = request.POST.get('status', None)
    review = request.POST.get('review', None)
    filtername = request.POST.get('filtername', "filtered_summary")
    with_doc = request.POST.get('with_doc', 'any')
    cert = request.POST.get('cert', None)
    hab_id = request.POST['habid']
    if(hab_id):
        filterString['hab_id__icontains'] = hab_id
    hab_id_exact = request.POST['habid_exact']
    if(hab_id_exact):
        filterString['hab_id'] = hab_id_exact
    district = request.POST['district']
    if(district):
        filterString['district'] = district
    division = request.POST['division']
    if(division):
        filterString['division'] = division
    village = request.POST.get('village',None)
    village = formatString(village)
    if(village):
        filterString['village__icontains'] = village

    # sel = "-".join([f for f in [district, division, village,
    #                             hab_id, hab_id_exact, status, review, with_doc] if not (f == "" or f == None)])

    filterString1 = filterString.copy()
    filterString2 = filterString.copy()
    if(status):
        filterString1['progressqty__status'] = status
        filterString2['progressqtyextra__status'] = status
    if(review):
        filterString1['progressqty__review'] = review
        filterString2['progressqtyextra__review'] = review
    if(with_doc == 'withdoc'):
        filterString1['progressqty__document__gt'] = 0
        filterString2['progressqtyextra__document__gt'] = 0
    if(with_doc == 'withoutdoc'):
        filterString1['progressqty__document__lt'] = 1
        filterString2['progressqtyextra__document__lt'] = 1
    if(cert):
        filterString1['progressqty__cert'] = cert
        filterString2['progressqtyextra__cert'] = cert

    sites = Site.objects.filter(**filterString1)
    siteExtras = SiteExtra.objects.filter(**filterString2)

    dprQty = DprQty.objects.filter(site__in=sites, has_infra=True)
    dfdprQty = pd.DataFrame(dprQty.values())
    addField(dfdprQty, sites)

    progressSites = ProgressQty.objects.filter(site__in=sites)
    dfProgressQty = pd.DataFrame(progressSites.values())
    addField(dfProgressQty, sites)

    progressAddtionalSites = ProgressQtyExtra.objects.filter(
        site__in=siteExtras)
    dfProgressQtyX = pd.DataFrame(progressAddtionalSites.values())
    addField(dfProgressQtyX, siteExtras)

    ssum = pd.Series()

    surveyQtys = SurveyQty.objects.filter(site__in=sites)
    dfsurveyQtys = pd.DataFrame(surveyQtys.values())
    addField(dfsurveyQtys, sites)

    ssum['Surveyed habs'] = len(dfsurveyQtys)
    for s in surveyQtys.values('site__category').annotate(count=Count('site__category')):
        if(s['site__category']):
            ssum['Surveyed habs cat-' + s['site__category']] = s['count']

    ssum['DPR habs'] = len(dfdprQty)
    for s in dprQty.values('site__category').annotate(count=Count('site__category')):
        if(s['site__category']):
            ssum['DPR habs cat-' + s['site__category']] = s['count']

    ssum['STATUS ({} habs)'.format(len(progressSites) +
                                   len(progressAddtionalSites))] = '▪️'*3
    sqty = pd.Series()
    for status in progressSites.values('status').distinct():
        status = status['status']
        sqty[status] = progressSites.filter(status=status).count()
    for status in progressAddtionalSites.values('status').distinct():
        status = status['status']
        if(status in sqty and sqty[status] > 0):
            sqty[status] += progressAddtionalSites.filter(
                status=status).count()
        else:
            sqty[status] = progressAddtionalSites.filter(status=status).count()
    if(not sqty.empty):
        ssum = ssum.append(sqty.rename(lambda x: '▷ ' + str(x).title()))

    for c in progressSites.filter(status='completed').values('site__category').annotate(count=Count('site__category')):
        if(c['site__category']):
            ssum['▷ Completed cat-' + c['site__category']] = c['count']

    # doc submitted
    count1 = progressSites.filter(cert=True).count()
    count2 = progressAddtionalSites.filter(cert=True).count()
    ssum['▷ Cert submitted 📑'] = count1 + count2
    sumt = pd.Series()
    if(not dfProgressQty.empty):
        sumt = dfProgressQty[PROGRESS_QFIELDS].sum(numeric_only=True)
    if(not dfProgressQtyX.empty):
        sum2 = dfProgressQtyX[PROGRESS_QFIELDS].sum(numeric_only=True)
        if(not sumt.empty):
            sumt += sum2
        else:
            sumt = sum2
    if(not sumt.empty):
        ssum['Progress Qty'] = "▪️"*3
        ssum = ssum.append(sumt[PROGRESS_QFIELDS].fillna(
            0).rename(lambda x: '▷ ' + x.upper()))

    ssum.name = 'aggr'
    ssum.index.name = filtername
    dfsummary = ssum.to_frame()
    dfsummary.to_excel('outputs/filtered_summary.xlsx')
    summary = dfsummary.to_html()
    sel_fields = ['site__village', 'site__census', 'site__habitation', 'site__district', 'site__division', 'status',
                  'ht', 'pole_ht_8m', 'lt_3p', 'lt_1p', 'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25', 'review']
    dfP = pd.DataFrame(progressSites.values(*sel_fields))
    # dfP.set_index('site__hab_id', inplace=True)
    dfPX = pd.DataFrame(progressAddtionalSites.values(*sel_fields))
    # dfPX.set_index('site__hab_id', inplace=True)
    pd.concat([dfP, dfPX]).to_excel('outputs/last_fetch_progress.xlsx')

    fields = ['village', 'census', 'habitation']
    dfSites = pd.concat([pd.DataFrame(sites.values(*fields)),
                         pd.DataFrame(siteExtras.values(*fields))])
    dfSites.to_excel('outputs/filtered_sites.xlsx')

    return JsonResponse(
        {
            'site': list(sites.values()),
            'siteAdditional': list(siteExtras.values()),
            'dprData': list(dfdprQty.T.to_dict().values()),
            'surevyQtys': list(dfsurveyQtys.T.to_dict().values()),
            'progressSites': list(dfProgressQty.fillna(0).T.to_dict().values()),
            'progressAddtionalSites': list(dfProgressQtyX.T.to_dict().values()),
            'summary': summary,
        })


@ensure_csrf_cookie
def index(request):
    data = getDistrictProgressSummary()
    data = data.replace("_", " ").title()
    logs = getLog()
    return render(request, "work/index.html", {'data': data, 'logs': logs})


def getLog():
    return Log.objects.all()[::-1][:20]


def undoextra(request):
    if(request.method == 'POST'):
        updateid = request.POST['updateid']
        SiteExtra.objects.filter(changeid=updateid).delete()
        messages.success(request, 'changeid <b>{}</b> undone'.format(updateid))
        return HttpResponseRedirect(reverse('work:index'))
    else:
        return render(request, "work/index.html")


def updateProgress(request):
    if(request.method == 'POST'):
        if(len(request.FILES)):
            file = request.FILES['file']
            updateid = request.POST['updateid']
            # f  = File(file)
            if(updateid == ""):
                updateid = file.name
            updateProgressQty(request, file, updateid)
        else:
            messages.error(request, 'File not selected!')
        return HttpResponseRedirect(reverse('work:index'))
    else:
        print('Get...')
        return render(request, "work/index.html")


def handle_uploaded_file(f):
    with open('update.xlsx', 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

def createSite(**kwargs):
    village = formatString(kwargs['village'])
    census = formatString(kwargs['census'])[:6]
    habitation = formatString(kwargs['habitation'])
    district = formatString(kwargs['district'])
    division = formatString(kwargs['division'])
    print("creating site {}".format(kwargs))
    try:
        recq = Site.objects.filter(hab_id = getHabID(census=census, habitation=habitation))
        if(recq.exists()):
            return recq[0]
        rec = Site()
        rec.census = census
        rec.habitation = habitation
        rec.village = village
        rec.district = district
        rec.division = division
        rec.save()
        return rec
    except Exception as ex:
        print('Error: '.format(ex.__str__()))
        raise ex

def addSite(request):
    if(request.method == 'POST'):
        if(len(request.FILES)):
            file = request.FILES['file']
            df = pd.read_excel(file)
            for index, row in df.iterrows():
                rec = createSite(**row)
            messages.success(request, '{} sites added'.format(len(df)))
        else:
            messages.error(request, 'File not selected!')
        return HttpResponseRedirect(reverse('work:index'))
    else:
        print('Get...')
        return render(request, "work/index.html")


def uploadSurvey(request):
    if(request.method == 'POST'):
        if(len(request.FILES)):
            file = request.FILES['file']
            df = pd.read_excel(file)
            # template_approval.xlsx
            dfF = pd.read_excel('files/template_approval.xlsx')

            # check for field match
            truths = df.columns == dfF.columns
            ifmatch = all(truths)
            if(not ifmatch):
                notmatch = [df.columns[i] + ' ≠ ' + dfF.columns[i]
                            for i, col in enumerate(truths) if not col]
                messages.error(request, "Format error – ")
                messages.error(request, notmatch)
                return HttpResponseRedirect(reverse('work:index'))

            df.iloc[:, 7:15] = df.iloc[:, 7:15].fillna(value=0)
            df = df.fillna('')
            cols = dfF.columns
            for index, row in df.iterrows():
                # census = row[cols[3]]
                # habitation = row[cols[4]]
                # hab_id = getHabID(census, habitation)
                # village = row[cols[2]]
                # district = row[cols[5]]
                # division = row[cols[6]]
                # hab_id = hab_id
                # village = formatString(village)
                # census = formatString(census)
                # habitation = formatString(habitation)
                # district = formatString(district)
                # division = formatString(division)
                # print('Updating site {}'.format(hab_id))
                try:
                    rec = createSite(**row)
                    qty, created = SurveyQty.objects.get_or_create(site=rec)
                except Exception as ex:
                    messages.error(request, 'site: {}, error: {}'.format([row['census'], row['habitation']], ex.__str__()))
                    continue
                qty.ht = row['ht']
                qty.lt_1p = row['lt1']
                qty.lt_3p = row['lt3']
                qty.dtr_25 = row['dtr_25kva']
                qty.dtr_63 = row['dtr_63kva']
                qty.dtr_100 = row['dtr_100kva']
                # qty.pole_8m = row[cols[13]]
                qty.pole_ht_8m = row['pole_ht_8m']
                qty.pole_lt_8m = row['pole_lt_8m']
                qty.pole_9m = row['pole_9m']
                qty.approval_status = row['status']
                qty.remark = row['remark']
                qty.changeid = file
                try:
                    qty.save()
                except Exception as ex:
                    messages.error(request,'Error {}: '.format(rec, ex.__str__()))        
                    continue
            messages.success(request, 'Survey Report updated')
        else:
            messages.error(request, 'No Survey data file in legacy')
        return HttpResponseRedirect(reverse('work:index'))
    else:
        return render(request, "work/index.html")


def loadDprQty(request):
    if(request.method == 'POST'):
        if(len(request.FILES)):
            file = request.FILES['file']
            df = pd.read_excel(file)
            df.fillna(0, inplace=True)
            df.replace('', 0, inplace=True)
            try:
                for index, row in df.iterrows():
                    hab_id = getHabID(
                        census=row['census'], habitation=row['habitation'])
                    print('Updating site {}'.format(hab_id))
                    site = Site.objects.get(hab_id=hab_id)
                    qty, created = DprQty.objects.get_or_create(
                        site=site, category=row['category'],
                        mode=row['mode'],
                        status=row['status']
                    )
                    qty.hh_bpl = row['hh_bpl']
                    qty.hh_bpl_metered = row['hh_bpl_metered']
                    qty.hh_metered = row['hh_metered']
                    qty.type = row['type']
                    qty.hh_unmetered = row['hh_unmetered']
                    qty.hh_apl_free = row['hh_apl_free']
                    qty.hh_apl_not_free = row['hh_apl_not_free']
                    qty.lt_3p = row['lt_3p']
                    qty.lt_1p = row['lt_1p']
                    qty.ht = row['ht']
                    qty.dtr_100 = row['dtr_100']
                    qty.dtr_63 = row['dtr_63']
                    qty.dtr_25 = row['dtr_25']
                    qty.save()
                    messages.success(
                        request, 'DPR Site Qty updated: {}'.format(site))
            except Exception as ex:
                messages.error(request, 'Error DPR Qty site {}: {}'.format(
                    row['hab_id'], ex.__str__()))
            messages.success(request, 'DPR HH updated')
    else:
        messages.error(request, 'No DPR Qty data file in legacy')
    return HttpResponseRedirect(reverse('work:index'))


def getSummary(model):
    pqty = model.objects.all()
    if(pqty.count() == 0):
        return pd.DataFrame()
    df = pd.DataFrame(pqty.values())
    df['division'] = ''
    df['district'] = ''
    df['completed'] = 0
    # df['surveyed habs'] = 1
    for index, rec in enumerate(pqty):
        df.loc[index, 'division'] = rec.site.division
        df.loc[index, 'district'] = rec.site.district
        if(rec.status == 'completed'):
            df.loc[index, 'completed'] = 1

    # df_district = df.iloc[:, 4:].groupby(
    df_district = df[['district', 'division', 'completed', 'ht', 'pole_ht_8m', 'lt_3p', 'lt_1p', 'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25']].groupby(
        'district').sum().sort_values('district')

    print(df_district)
    return df_district


def getSummaryShifted(model):
    pqty = model.objects.all()
    if(pqty.count() == 0):
        return pd.DataFrame()
    df = pd.DataFrame(pqty.values())
    df['division'] = ''
    df['district'] = ''
    for index, rec in enumerate(pqty):
        df.loc[index, 'division'] = rec.site.division
        df.loc[index, 'district'] = rec.site.district
    # df_district = df.iloc[:, 4:].groupby(
    df_district = df[[
        'district',
        'division',
        'acsr',
        'cable_3p',
        'cable_1p',
        'pole_8m',
        'pole_9m',
        'dtr_100',
        'dtr_63',
        'dtr_25',
    ]].groupby(
        'district').sum().sort_values('district')
    return df_district


def getDistrictProgressSummary():
    num_fields = ['ht','ht_conductor', 'pole_ht_8m', 'lt_3p', 'lt_1p',
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

    dfDprqty = pd.DataFrame(dpr.values(district=F('site__district')).annotate(*[Sum(f) for f in [*DPR_INFRA_FIELDS, 'ht_conductor']]))
    dfDprqty.columns = [f.replace('__sum', '') for f in dfDprqty.columns]
    dfDprqty.set_index('district', inplace=True)
    dfDprqty['section'] = '1. DPR'
    # dfDprqty['pole_ht_8m'] = pd.np.ceil(dfDprqty['ht'] * 15).astype(int)
    # dfDprqty['pole_lt_8m'] = pd.np.ceil(dfDprqty['lt_3p'] * 25 + dfDprqty['lt_1p'] * 22).astype(int)
    dfDprqty['pole_ht_8m'] = dfDprqty['ht'] * 15
    dfDprqty['pole_lt_8m'] = dfDprqty['lt_3p'] * 25 + dfDprqty['lt_1p'] * 22
    dfDprqty['pole_9m'] = (dfDprqty['dtr_100'] + dfDprqty['dtr_63'] + dfDprqty['dtr_25'])*2
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
    dfPQty['pole_9m'] = (dfPQty['dtr_100'] + dfPQty['dtr_63'] + dfPQty['dtr_25'])*2
    dfPQty['pole_8m'] = dfPQty['pole_ht_8m'] + dfPQty['pole_lt_8m']    
    

    dfSurvQty = pd.DataFrame(sqty.values(district=F('site__district')).annotate(*[Sum(f) for f in SURVEY_QFIELDS]))    
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

    dfQty = pd.concat([dfDprqty, dfLoa, dfSurvQty, dfPQty, dfQtyBal, dfExePc], sort=False)
    dfQty.sort_values(by=['district','section'], inplace=True)
    dfQty.set_index([dfQty.index, dfQty['section']], inplace=True)
    del dfQty['section']
    display_fields = ['ht_conductor', *DPR_INFRA_FIELDS, 'pole_8m', 'pole_9m']
    dfQty= dfQty[display_fields]
    dfQty.loc[('TOTAL', '1. DPR'),display_fields] = dfDprqty[display_fields].sum()
    dfQty.loc[('TOTAL', '2. LOA'),display_fields] = dfLoa[display_fields].sum()
    dfQty.loc[('TOTAL', '3. Approved'),display_fields] = dfSurvQty[display_fields].sum()
    dfQty.loc[('TOTAL', '4. Executed'),display_fields] = dfExePc[display_fields].sum()
    dfQty.loc[('TOTAL', '5. Balance'),display_fields] = dfQtyBal[display_fields].sum()
    dfQty = pd.np.around(dfQty,1)
    intFields = [f for f in display_fields if ('pole' in f or 'dtr' in f)]
    dfQty.fillna(0, inplace=True)
    dfQty[intFields] = dfQty[intFields].astype(int)

    dfQty.to_excel('outputs/balance_progress.xlsx')
    # additional sites are those not included in DPR
    dfAdditional = pd.DataFrame(SurveyQty.objects.exclude(site__in=DprQty.objects.values('site')).values(
        district=F('site__district')).annotate(additional=Count('site')))
    dfAdditional.set_index('district', inplace=True)
    df_district['additional'] = dfAdditional
    # if(not dfAdditional.empty):
    #     df_district = df_district.add(dfAdditional, fill_value=0)

    df_district.fillna(0, inplace=True)
    df_district.loc['∑'] = df_district.sum(numeric_only=True)
    int_fields = ['completed', 'cert', 'surveyed', 'DPRHabs', 'additional', *[f+'__sum' for f in ['pole_ht_8m',
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

    dfCats = pd.concat([dfCatsSurv, dfCatsAll, dfCats], axis=1)

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
    

    return result1 + '<br>Shifted Qty<br>' + result2 + '<br>Categorywise' + result3 + '<BR>Balance' + result4


def validate_progress(request):
    if(not len(request.FILES)):
        return JsonResponse({'Error': 'No file'})
    df = updateProgressQty(request, request.FILES['file'], "", True)
    # file = request.FILES['file']
    # df = pd.read_excel(file, sheet_name='upload', header=None)
    # data_row = 6
    # # check format
    # dfTemplate = pd.read_excel('files/progress_report.xlsx', header=None)
    # columns = dfTemplate.iloc[data_row-1]
    # for i in range(24):
    #     if(df.iloc[data_row-1, i] != columns[i]):
    #         messages.error(request, 'Format error @: {}'.format(
    #             columns[i]))
    #         return
    # # update data
    # df_data = df[data_row:]
    # df_data.iloc[:, 7:23].fillna(value=0, inplace=True)
    # df_data.iloc[:, 7:23].replace('', 0, inplace=True)
    # df_data = df_data.rename(columns=df.iloc[5, :])
    # df_data = df_data.fillna('')

    res = []
    resx = []
    for i, row in df.iterrows():
        if(row['ID']):
            hab_id = row['ID']
        else:
            hab_id = getHabID(
                census=row['Census Code'], habitation=row['Habitation'])
        if(not Site.objects.filter(hab_id=hab_id).exists()):
            # res.append(
            #     {'class': 'warning', 'text': 'Not in Site: {}'.format(hab_id)})
            if(SiteExtra.objects.filter(hab_id=hab_id).exists()):
                res.append(
                    {'class': 'warning', 'text': 'in add. site: {}'.format(hab_id)})
            else:
                res.append(
                    {'class': 'error', 'text': 'not in add. site: {}'.format(hab_id)})
        else:
            res.append(
                {'class': 'success', 'text': 'in site: {}'.format(hab_id)})

    # if(not len(res)):
    #     res.append({'class': 'success', 'text': 'All in Site'})
    return JsonResponse({'data': res})
    # return render(request, 'work/progress_validation.html',{'data': res})
    # return HttpResponseRedirect('/work/progress_validation.html',{'data': res})
    # return render_to_response('work/progress_validation.html',{'data': res} )

# def validation_page(request)

def api_data(request):
    messages.info(request, 'Helloooooo')
    return JsonResponse({'a': 1})


def downloadFile(request):
    if(request.method == 'POST'):
        # fill these variables with real values
        tabtype = request.POST['tabtype']
        fl_path = request.POST['path']
        filename = request.POST['filename']
        if(tabtype == 'sites'):
            getSiteProgress()
        fl = open(fl_path, 'rb')
        # mime_type, _ = mimetypes.guess_type(fl_path)
        # response = HttpResponse(fl, content_type=mime_type)
        response = HttpResponse(fl, content_type='application/ms-excel')
        response['Content-Disposition'] = "attachment; filename=%s" % filename
        return response


def updateProgressQty(request, file, updateid, getParseData=False):
    df = pd.read_excel(file, sheet_name='upload', header=None)
    data_row = 6
    # check format
    dfTemplate = pd.read_excel('files/progress_report.xlsx', header=None)
    columns = dfTemplate.iloc[data_row-1]
    for i in range(24):
        if(df.iloc[data_row-1, i] != columns[i]):
            messages.error(request, 'Format error @: {}'.format(
                columns[i]))
            return
    # update data
    df_data = df[data_row:]
    df_data.iloc[:, 7:23].fillna(value=0, inplace=True)
    df_data.iloc[:, 7:23].replace('', 0, inplace=True)
    df_data = df_data.rename(columns=df.iloc[5, :])
    df_data = df_data.fillna('')
    if(getParseData):
        return df_data

    messages.info(
        request, 'Running <b>{}</b> on <b>{}</b>'.format(updateid, file))
    if(updateid == ''):
        updateid = file
    log = Log()
    log.changeid = updateid
    log.model = 'Progress'
    log.save()
    for index, row in df_data.iterrows():
        if(len(row['ID']) > 0):
            habid = row['ID']
        else:
            habid = getHabID(row['Census Code'], row['Habitation'])
        print(row)
        print('habid: {}'.format(habid))
        # if(input('check')=="x"):
        #     continue
        messages.info(request, 'Processing: {}'.format(habid))
        try:
            if(Site.objects.filter(hab_id=habid).exists()):
                site = Site.objects.get(hab_id=habid)
                # materials shifted
                sqty, created = ShiftedQty.objects.get_or_create(site=site)
                sqty.acsr = row[columns[7]]  # 'ACSR Conductor (km)']
                sqty.cable_3p = row[columns[8]]  # '3 Phase AB Cable (km)']
                sqty.cable_1p = row[columns[9]]  # '1 Phase AB Cable (km)']
                sqty.pole_8m = row[columns[10]]  # '8m Pole (Nos)']
                sqty.pole_9m = row[columns[11]]  # '9m Pole (Nos)']
                sqty.dtr_100 = row[columns[12]]  # '100 KVA DTR (nos)']
                sqty.dtr_63 = row[columns[13]]  # '63 KVA DTR (nos)']
                sqty.dtr_25 = row[columns[14]]  # '25 KVA DTR (nos)']
                sqty.changeid = updateid
                sqty.save()
                # Work executed
                progress, created = ProgressQty.objects.get_or_create(
                    site=site)
                # skip the verified sites
                if(not created and progress.review == 'ok'):
                    continue
                progress.ht = row[columns[15]]
                progress.pole_ht_8m = row[columns[16]]
                progress.lt_3p = row[columns[17]]
                progress.lt_1p = row[columns[18]]
                progress.pole_lt_8m = row[columns[19]]
                progress.dtr_100 = row[columns[20]]  # '100 KVA DTR (nos)']
                progress.dtr_63 = row[columns[21]]  # '63 KVA DTR (nos)']
                progress.dtr_25 = row[columns[22]]  # '25 KVA DTR (nos)']
                progress.remark = row[columns[23]]
                progress.status = row[columns[5]]
                progress.changeid = updateid
                progress.save()
                messages.success(request, 'Updated: {}'.format(site.hab_id))
            else:
                messages.warning(request, 'Extra Site: {}'.format(habid))
                siteexta, created = SiteExtra.objects.get_or_create(
                    hab_id=habid)
                if(created):
                    siteexta.approve_id = row[columns[1]]
                    siteexta.village = formatString(row[columns[2]])
                    siteexta.census = row[columns[3]]
                    siteexta.habitation = formatString(row[columns[4]])
                    district = formatString(df.iloc[0, 3])
                    division = formatString(df.iloc[1, 3])
                    if(not district in DISTRICTS_ALLOWED):
                        siteexta.delete()
                        raise Exception('District not found')
                    if(not division in DIVISIONS_ALLOWED):
                        siteexta.delete()
                        raise Exception('Division not found')
                    siteexta.district = district
                    siteexta.division = division
                    siteexta.changeid = updateid
                    siteexta.save()
                    messages.warning(
                        request, 'Extra Site Created: {}'.format(row[0]))

                sq, createds = ShiftedQtyExtra.objects.get_or_create(
                    site=siteexta)
                sq.acsr = row[columns[7]]  # row['ACSR Conductor (km)']
                sq.cable_3p = row[columns[8]]  # row['3 Phase AB Cable (km)']
                sq.cable_1p = row[columns[9]]  # row['1 Phase AB Cable (km)']
                sq.pole_8m = row[columns[10]]  # row['8m Pole (Nos)']
                sq.pole_9m = row[columns[11]]  # row['9m Pole (Nos)']
                sq.dtr_100 = row[columns[12]]  # row['100 KVA DTR (nos)']
                sq.dtr_63 = row[columns[13]]  # row['63 KVA DTR (nos)']
                sq.dtr_25 = row[columns[14]]  # row['25 KVA DTR (nos)']
                sq.save()
                pq, createdp = ProgressQtyExtra.objects.get_or_create(
                    site=siteexta)
                # skip the verified sites
                if(not createdp and pq.review == 'ok'):
                    messages.add_message(
                        request, messages.WARNING, "skipped: {} already reviewed".format(pq))
                    continue
                pq.ht = row[columns[15]]
                pq.pole_ht_8m = row[columns[16]]
                pq.lt_3p = row[columns[17]]
                pq.lt_1p = row[columns[18]]
                pq.pole_lt_8m = row[columns[19]]
                pq.dtr_100 = row[columns[20]]
                pq.dtr_63 = row[columns[21]]
                pq.dtr_25 = row[columns[22]]
                pq.remark = row[columns[23]]
                pq.status = row[columns[5]]
                pq.changeid = updateid
                pq.save()
                messages.success(
                    request, 'Updated in extra: {}'.format(sq.site.hab_id))
        except Exception as ex:
            print('{}: {}'.format(row[0], ex.__str__()))
            messages.add_message(request, messages.ERROR,
                                 '{}: {}'.format(row[0], ex.__str__()))


def progress(request, site_id):
    print(site_id)
    site = Site.objects.get(id=site_id)
    pqty, created = ProgressQty.objects.get_or_create(site=site)
    # prefill data from survey
    sqty = SurveyQty.objects.filter(site=site)
    if(created and sqty.exists()):
        sqty = sqty[0]
        pqty.ht = sqty.ht
        pqty.pole_ht_8m = round(14*sqty.ht)
        pqty.lt_3p = sqty.lt_3p
        pqty.lt_1p = sqty.lt_1p
        pqty.pole_lt_8m = round(22*sqty.lt_3p + 25*sqty.lt_1p)
        pqty.dtr_100 = sqty.dtr_100
        pqty.dtr_63 = sqty.dtr_63
        pqty.dtr_25 = sqty.dtr_25
        pqty.status = 'ongoing'
        pqty.save()

    return HttpResponseRedirect("/admin/work/progressqty/" + str(pqty.id))


def shifted(request, site_id):
    site = Site.objects.get(id=site_id)
    sqty, created = ShiftedQty.objects.get_or_create(site=site)
    return HttpResponseRedirect("/admin/work/shiftedqty/" + str(sqty.id))


def api_load_review(request):
    pid = request.POST['pid']
    additional = request.POST['additional']
    msg = []
    surveyed = None
    progress = None
    site = None
    quants = []
    valid = True
    print('additona {}'.format(additional))
    if(int(additional) > 0):
        progress = ProgressQtyExtra.objects.get(id=pid)
    else:
        progress = ProgressQty.objects.get(id=pid)
        surveyed = SurveyQty.objects.get(site=progress.site)
    site = progress.site
    if(not site):
        msg.append({
            'type': 'error',
            'text': 'Site not found!'})
    if(not surveyed):
        msg.append({
            'type': 'error',
            'text': 'Not a surveyed habitation!'})
    if(not progress):
        msg.append({
            'type': 'error',
            'text': 'No progress data!'})
    if(site == None or surveyed == None or progress == None):
        valid = False
    else:
        # REVIEW_QFIELDS.sort()
        for f in REVIEW_QFIELDS:
            vsurvey = getattr(surveyed, f) if (not surveyed == None) else 0
            vexecuted = getattr(progress, f) if (not progress == None) else 0
            quants.append({
                'field': f,
                'surveyed': vsurvey,
                'executed': vexecuted,
                'meta': {'dbfield':{'surveyed': f in vars(surveyed), 'executed': f in vars(progress)}}
                # 'diff': round(getattr(surveyed, f) - getattr(progress, f), 2)
            })
    # if(progress):
    #     rlink = ResolutionLink.objects.get(object_id=progress.id, content_type__model=progress.__class__.__name__.lower())
    print('getting data')
    return JsonResponse(
        {
            'valid': valid,
            'msg': msg,
            'quants': quants,
            'site': {f: getattr(site, f) for f in vars(site) if type(getattr(site, f)) in [str, int]} if not site == None else None,
            # 'isAdditional': isAdditional,
            # 'pid': progress.id if not progress == None else None,
            'doc_url': progress.document.url if progress.document else "",
            'cert': progress.cert,
            'status': progress.status,
            'remark': progress.remark,
            'review_text': progress.review_text,
            'review': progress.review,
            'approval': surveyed.approval_status if surveyed!=None else None,
            # 'resolution': {'rid':rlink.resolution.id, 'rlinkid': rlink.id} if rlink else None,
            # 'model': progress.__class__.__name__.lower(),
        })

import django.dispatch
def api_updateExecQty(request):
    try:
        value = request.POST['value']
        field = request.POST['field']
        pid = request.POST['pid']
        isAdditional = request.POST['isAdditional']
    except Exception as ex:
        print(ex.__str__())
        input('error check')
    p = None
    msg = []
    print('updating... field {}, value {}, pid: {}, add: {}'.format(
        field, value, pid, isAdditional))
    # print('additona ' + isAdditional)
    try:
        if(not int(isAdditional) > 0):
            p = ProgressQty.objects.get(id=pid)
        else:
            print('pqtyx')
            p = ProgressQtyExtra.objects.get(id=pid)

        setattr(p, field, value)
        print(p)
        p.save()
        msg.append(
            {'type': 'success', 'text': "{} updated '{}': {}".format(p, field, value)})
    except Exception as ex:
        print(ex.__str__())
        msg.append({
            'type': 'error',
            'text': ex.__str__()
        })

    # test
    # django.dispatch.Signal(providing_args=["toppings", "size"])

    return JsonResponse({'msg': msg, 'value': getattr(p, field)})


def api_create_resolution_link(request):
    statement = request.POST.get('statement', "")
    resolutiontxt = request.POST.get('resolution', "")
    status = request.POST.get('status', "")
    pid = request.POST.get('pid', "")
    link = request.POST.get('link', "")
    model = request.POST.get('model', "")
    site = request.POST.get('site', "")
    resolution = Resolution()
    resolution.statement = "{}\n\n[habid: {}]\n[link:{}]".format(statement, site, link)
    resolution.resolution = resolutiontxt
    resolution.status = status
    resolution.save()
    msg = {
    'type': 'success',
    'text': 'Added to resolution: id {}'.format(resolution.id)
    }
    # rlink= ResolutionLink(object_id=id, content_type__model=model, resolution=resolution)
    # rlink.save()
    return JsonResponse({'resolution': resolution.id, 'msg': [msg]})

# from django.core.signals import request_finished
# from django.dispatch import receiver
# @receiver(request_finished)
# def my_callback(sender, **kwargs):
#     print("Request finished!")
#     print(kwargs)
# request_finished.connect(my_callback)

import re
def resolutionlinkedpage(request, id):
    # resolution = Resolution.objects.get(id=id)
    resolution = get_object_or_404(Resolution,id=id)
    statement=resolution.statement
    link=None
    g = re.search('\[link:(.*)\]',statement)
    if(g):
        link = g.group(1)
    return render(request, "work/resolution_page.html", {'res_link':'/admin/work/resolution/' + str(id), 'link': link})

def resolution(request):
    return render(request, "work/resolution.html")