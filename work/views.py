from django.shortcuts import render, get_object_or_404
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
from work.functions import formatString
from work.models import getHabID
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Permission, User, Group
from django.contrib.auth.decorators import login_required
import work.controller as controller
import pdb


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
    # site = Site.objects.get(id=pickedSite)
    # sites = Site.objects.filter(id__in=checkedSites)
    # print(siteExtras.values())
    res = None
    for s in checkedSites:
        # s.origin = site
        # s.save()
        res = controller.switchSite(s, pickedSite)
    return JsonResponse({'status': res})


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
        #: keep xsite for future ref.
        # s.delete()
        px.delete()
        sx.delete()
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
    excludeString = {}
    status = request.POST.get('status', None)
    review = request.POST.get('review', None)
    additional = request.POST.get('additional', None)
    filtername = request.POST.get('filtername', "filtered_summary")
    with_doc = request.POST.get('with_doc', 'any')
    cert = request.POST.get('cert', None)
    survey = request.POST.get('survey', None)
    hab_id = request.POST.get('habid', None)
    # nonDpr = request.POST.get('non_dpr', None)
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
    village = request.POST.get('village', None)
    village = formatString(village)
    if(village):
        filterString['village__icontains'] = village

    # sel = "-".join([f for f in [district, division, village,
    #                             hab_id, hab_id_exact, status, review, with_doc] if not (f == "" or f == None)])

    filterString1 = filterString.copy()
    filterString2 = filterString.copy()
    if(status):
        filterString1['progressqty__status'] = status
        # filterString2['progressqtyextra__status'] = status
    if(review):
        filterString1['progressqty__review'] = review
        # filterString2['progressqtyextra__review'] = review
    if(with_doc == 'withdoc'):
        filterString1['progressqty__document__gt'] = 0
        # filterString2['progressqtyextra__document__gt'] = 0
    if(with_doc == 'withoutdoc'):
        filterString1['progressqty__document__lt'] = 1
        # filterString2['progressqtyextra__document__lt'] = 1
    if(cert):
        filterString1['progressqty__cert'] = cert
        # filterString2['progressqtyextra__cert'] = cert
    if(survey):
        if(survey == 'approved'):
            filterString1['surveyqty__status'] = 'approved'
        else:
            excludeString['surveyqty__status'] = 'approved'

    if(additional == 'additional'):
        filterString1['surveyqty'] = None

    sites = Site.objects.filter(**filterString1).exclude(**excludeString)

    # siteExtras = SiteExtra.objects.filter(**filterString2)
    # if(siteExtras):
    #     sites |= Site.objects.filter(siteextra__site in siteExtras)

    if(sites):
        siteExtras = SiteExtra.objects.filter(site__in=sites)
    else:
        siteExtras = SiteExtra.objects.filter(**filterString2)
    # if(siteExtras):
    #     sxs = []
    #     for sx in siteExtras:
    #         sxs.append(sx.site.id)
    #     sites |= Site.objects.filter(id__in = sxs)

    # sites = Site.objects.filter(**filterString1).exclude(**excludeString)

    # dprQty = DprQty.objects.filter(site__in=sites, has_infra=True)
    dprQty = DprQty.objects.filter(site__in=sites)
    dfdprQty = pd.DataFrame(dprQty.values())
    addField(dfdprQty, sites)

    progressSites = ProgressQty.objects.filter(site__in=sites)
    dfProgressQty = pd.DataFrame(progressSites.values())
    addField(dfProgressQty, sites)

    progressNonSurvey = progressSites.filter(site__surveyqty=None)
    dfProgressQtyNonSurvey = pd.DataFrame(progressNonSurvey.values())
    addField(dfProgressQtyNonSurvey, sites)

    progressAddtionalSites = ProgressQtyExtra.objects.filter(
        site__in=siteExtras)
    dfProgressQtyX = pd.DataFrame(progressAddtionalSites.values())
    addField(dfProgressQtyX, siteExtras)

    ssum = pd.Series()

    surveyQtys = SurveyQty.objects.filter(site__in=sites)
    dfsurveyQtys = pd.DataFrame(surveyQtys.values())
    addField(dfsurveyQtys, sites)

    ssum['Surveyed habs'] = len(dfsurveyQtys)
    for s in surveyQtys.values('status').annotate(count=Count('status')):
        # if(s['site__category']):
        ssum['▷ ' + s['status']] = s['count']

    for s in surveyQtys.values('site__category').annotate(count=Count('site__category')):
        if(s['site__category']):
            ssum['Surveyed habs cat-' + s['site__category']] = s['count']

    ssum['DPR habs'] = len(dfdprQty)
    for s in dprQty.values('site__category').annotate(count=Count('site__category')):
        if(s['site__category']):
            ssum['DPR habs cat-' + s['site__category']] = s['count']

    # ssum['STATUS ({} habs)'.format(len(progressSites) +
    #                                len(progressAddtionalSites))] = '▪️'*3
    ssum['STATUS ({} Approved habs)'.format(
        surveyQtys.filter(status='approved').count())] = '▪️'*3
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
    ssum['▷ non-surveyed'] = len(dfProgressQtyNonSurvey) + len(dfProgressQtyX)
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
            'progressSites': list(dfProgressQty.fillna('').T.to_dict().values()),
            'progressQtyNonSurvey': list(dfProgressQtyNonSurvey.fillna('').T.to_dict().values()),
            'progressAddtionalSites': list(dfProgressQtyX.fillna('').T.to_dict().values()),
            'summary': summary,
        })


@ensure_csrf_cookie
def index(request):
    return render(request, "work/index.html")


def undoextra(request):
    if(request.method == 'POST'):
        updateid = request.POST['updateid']
        SiteExtra.objects.filter(changeid=updateid).delete()
        messages.success(request, 'changeid <b>{}</b> undone'.format(updateid))
        return HttpResponseRedirect(reverse('work:index'))
    else:
        return render(request, "work/index.html")


def updateProgress2(request):
    return render(request, 'work/progress_validation.html')


def updateConfirmation(request):
    if(not len(request.FILES)):
        return JsonResponse({'status': [{'class': 'error', 'text': 'File not selected'}]})
    file = request.FILES['file']
    updateid = request.POST.get('updateid', None)
    if(not updateid):
        updateid = file.name
    status = []
    hasError, dfstatus, dfProgress = controller.validateProgressFile(file)
    updated = False
    if(hasError):
        status.extend(dfstatus)
        # print(status)
        return JsonResponse({
            'status': 'error', 'text': "; ".join([st['text'] for st in status])})
    # qfields = ['ht','ht_conductor','lt_1p','lt_3p','dtr_25','dtr_63','dtr_100','pole_lt_8m','pole_ht_8m','pole_9m']
    vfields = ['ht', 'pole_ht_8m', 'lt_3p', 'lt_1p',
               'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25', 'status', 'remark']
    headerfields = ['village', 'census', 'habitation']
    items = []
    try:
        for index, row in dfProgress.iterrows():
            item = {}
            hasError = False
            site, survey, progress = controller.getSiteData(
                census=row['census'], habitation=row['habitation'])

            if(not site):
                item['site'] = {'error': "site not found", 'data': {f: getattr(row, f, 0) for f in headerfields}}
                hasError = True
            else:
                item['site'] = {f: getattr(
                    site, f, 0) for f in headerfields}

            if(not progress):
                hasError = True
                item['progress'] = {'error': "progress not found"}
            else:
                item['progress'] = {f: getattr(progress, f, 0) for f in vfields}
                item['progress']['remark'] = " | ".join([x or "--" for x in [progress.remark, progress.review, progress.review_text]])
                item['pid'] = progress.id
                item['review_status'] = progress.review
                item['doc'] = str(progress.document)

            if(not survey):
                hasError = True
                item['survey'] = {'error': "survey not found"}
            else:
                item['survey'] = {f: getattr(survey, f, 0) for f in vfields}

            item['update'] = {f: getattr(row, f, 0) for f in vfields}
            item['hasError'] = hasError
            # if(progress):
            item['changes'] = {f: getattr(row, f, 0) == getattr(progress, f, 0) for f in vfields}
            items.append(item)
        return JsonResponse({'status': 'ok', 'items': items, 'headerfields': headerfields, 'vfields': vfields})
    except Exception as ex:
        return JsonResponse({'status': 'error', 'text': ex.__str__()})

import json
def updateHabProgress(request):
    pid = request.POST['pid']
    pdata = request.POST['progress']
    pdata = json.loads(pdata) 
    print('to update', pdata)
    try:
        progress = ProgressQty.objects.get(id=pid)
        for f in pdata:
            setattr(progress, f, pdata[f])
        progress.save()
        progress.remark = " | ".join([x or "--" for x in [progress.remark, progress.review, progress.review_text]])
        vfields = ['ht', 'pole_ht_8m', 'lt_3p', 'lt_1p',
               'pole_lt_8m', 'dtr_100', 'dtr_63', 'dtr_25', 'status', 'remark']        
        return JsonResponse({'status': 'success', 'progress': {f: getattr(progress, f, 0) for f in vfields}})
    except Exception as ex:
        return JsonResponse({'status': 'error', 'text': ex.__str__()})

def updateProgress(request):
    if(request.method == 'POST'):
        if(len(request.FILES)):
            file = request.FILES['file']
            isTest = request.POST.get('isTest', False)
            if(isTest == 'false'):
                isTest = False
            elif(isTest == 'True'):
                isTest = True
            updateid = request.POST.get('updateid', None)
            if(not updateid):
                updateid = file.name
            status = controller.UpdateProgress(file, updateid, isTest)
            return JsonResponse({
                'status': status})
        else:
            return JsonResponse({
                'status': [{'class': 'error', 'text': 'File not selected'}]})
    else:
        return JsonResponse({'status': 'somethings not right'})


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
        recq = Site.objects.filter(hab_id=getHabID(
            census=census, habitation=habitation))
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
                    messages.error(request, 'site: {}, error: {}'.format(
                        [row['census'], row['habitation']], ex.__str__()))
                    continue
                qty.ht = row['ht']
                qty.ht_conductor = getattr(row, 'ht_conductor', qty.ht * 3.15)
                qty.lt_1p = row['lt1']
                qty.lt_3p = row['lt3']
                qty.dtr_25 = row['dtr_25kva']
                qty.dtr_63 = row['dtr_63kva']
                qty.dtr_100 = row['dtr_100kva']
                # qty.pole_8m = row[cols[13]]
                qty.pole_ht_8m = row['pole_ht_8m']
                qty.pole_lt_8m = row['pole_lt_8m']
                qty.pole_9m = row['pole_9m']
                qty.status = row['status']
                qty.remark = row['remark']
                qty.changeid = file
                try:
                    qty.save()
                except Exception as ex:
                    messages.error(
                        request, 'Error {}: '.format(rec, ex.__str__()))
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
                    # print(row)
                    # site = Site.objects.get(hab_id=hab_id)
                    site, additional = controller.getSite(
                        census=row['census'], habitation=row['habitation'])
                    qty = DprQty()
                    # qty, created = DprQty.objects.get_or_create(
                    #     site=site, category=row['category'],
                    #     mode=row['mode'],
                    #     status=row['status'])
                    qty.site = site
                    qty.category = row['category']
                    qty.status = row['status']
                    qty.mode = row['mode']
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
                    print(vars(qty))
                    qty.save()
                    messages.success(
                        request, 'DPR Site Qty updated: {}'.format(site))
            except Exception as ex:
                messages.error(request, 'Error DPR Qty {}'.format(ex.__str__()))
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


def api_data(request):
    data = controller.getDistrictProgressSummary()
    logs = controller.getLog()
    return JsonResponse({'data': data, 'logs': logs})


def downloadFile(request):
    if(request.method == 'POST'):
        # fill these variables with real values
        tabtype = request.POST['tabtype']
        fl_path = request.POST['path']
        filename = request.POST['filename']
        if(tabtype == 'sites'):
            controller.getSiteProgressdf()
        fl = open(fl_path, 'rb')
        # mime_type, _ = mimetypes.guess_type(fl_path)
        # response = HttpResponse(fl, content_type=mime_type)
        response = HttpResponse(fl, content_type='application/ms-excel')
        # response = HttpResponse(fl, content_type='Document')
        response['Content-Disposition'] = "attachment; filename=%s" % filename
        return response


def survey(request, site_id):
    print(site_id)
    site = Site.objects.get(id=site_id)
    pqty, created = SurveyQty.objects.get_or_create(site=site)
    return HttpResponseRedirect("/admin/work/surveyqty/" + str(pqty.id))


def progress(request, site_id):
    print(site_id)
    site = Site.objects.get(id=site_id)
    pqty, created = ProgressQty.objects.get_or_create(site=site)
    # prefill data from survey
    # sqty = SurveyQty.objects.filter(site=site)
    # if(created and sqty.exists()):
    #     sqty = sqty[0]
    #     pqty.ht = sqty.ht
    #     pqty.pole_ht_8m = round(14*sqty.ht)
    #     pqty.lt_3p = sqty.lt_3p
    #     pqty.lt_1p = sqty.lt_1p
    #     pqty.pole_lt_8m = round(22*sqty.lt_3p + 25*sqty.lt_1p)
    #     pqty.dtr_100 = sqty.dtr_100
    #     pqty.dtr_63 = sqty.dtr_63
    #     pqty.dtr_25 = sqty.dtr_25
    #     pqty.status = 'ongoing'
    #     pqty.save()

    return HttpResponseRedirect("/admin/work/progressqty/" + str(pqty.id))


def shifted(request, site_id):
    site = Site.objects.get(id=site_id)
    sqty, created = ShiftedQty.objects.get_or_create(site=site)
    return HttpResponseRedirect("/admin/work/shiftedqty/" + str(sqty.id))


def api_load_review(request):
    pid = request.POST['pid']
    # site_id = request.POST.get('site_id', None)
    additional = request.POST['additional']
    msg = []
    surveyed = None
    progress = None
    site = None
    quants = []
    valid = True
    print('additona {}'.format(additional))
    # controller.getSite()
    if(int(additional) > 0):
        progress = ProgressQtyExtra.objects.get(id=pid)
    else:
        progress = ProgressQty.objects.get(id=pid)
        surveyed = SurveyQty.objects.filter(site=progress.site).first()
    site = progress.site

    if(not site):
        msg.append({
            'type': 'error',
            'text': 'Site not found!'})
    if(not surveyed):
        msg.append({
            'type': 'error',
            'text': 'Not a surveyed habitation!'})
    else:
        site.survey_id = surveyed.id
    if(not progress):
        msg.append({
            'type': 'error',
            'text': 'No progress data!'})
    if(site == None or surveyed == None or progress == None):
        valid = False
    # else:
        # REVIEW_QFIELDS.sort()
    for f in REVIEW_QFIELDS:
        vsurvey = getattr(surveyed, f, 0) if (not surveyed == None) else 0
        vexecuted = getattr(progress, f, 0) if (not progress == None) else 0
        quants.append({
            'field': f,
            'surveyed': vsurvey,
            'executed': vexecuted,
            'meta': {'dbfield': {'surveyed': f in vars(surveyed) if surveyed else False, 'executed': f in vars(progress)}}
            # 'diff': round(getattr(surveyed, f) - getattr(progress, f), 2)
        })
    # if(progress):
    #     rlink = ResolutionLink.objects.get(object_id=progress.id, content_type__model=progress.__class__.__name__.lower())
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
            'approval': surveyed.status if surveyed != None else None,
            # 'resolution': {'rid':rlink.resolution.id, 'rlinkid': rlink.id} if rlink else None,
            # 'model': progress.__class__.__name__.lower(),
        })


import django.dispatch
#: TODO make this transactional


def api_updateExecQty(request):
    try:
        x = request.POST['value']
        try:
            value = int(float(x)) if int(float(x)) == float(x) else float(x)
        except:
            value = x
        field = request.POST['field']
        pid = request.POST['pid']
        isAdditional = request.POST['isAdditional']
    except Exception as ex:
        print(ex.__str__())
    p = None
    msg = []
    print('updating... field {}, value {}, pid: {}, add: {}'.format(
        field, value, pid, isAdditional))
    # print('additona ' + isAdditional)
    fields = field.split('.')
    try:
        if(not int(isAdditional) > 0):
            p = ProgressQty.objects.get(id=pid)
        else:
            print('pqtyx')
            p = ProgressQtyExtra.objects.get(id=pid)

        for f in fields[:-1]:
            p = getattr(p, f)
        setattr(p, fields[-1], value)
        print('{} updating'.format(p))
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

    return JsonResponse({'msg': msg, 'value': getattr(p, fields[-1])})


def api_create_resolution_link(request):
    statement = request.POST.get('statement', "")
    resolutiontxt = request.POST.get('resolution', "")
    status = request.POST.get('status', "")
    pid = request.POST.get('pid', "")
    link = request.POST.get('link', "")
    model = request.POST.get('model', "")
    site = request.POST.get('site', "")
    resolution = Resolution()
    resolution.statement = "{}\n\n[habid: {}]\n[link:{}]".format(
        statement, site, link)
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
    resolution = get_object_or_404(Resolution, id=id)
    statement = resolution.statement
    link = None
    g = re.search('\[link:(.*)\]', statement)
    if(g):
        link = g.group(1)
    return render(request, "work/resolution_page.html", {'res_link': '/admin/work/resolution/' + str(id), 'link': link})


def resolution(request):
    return render(request, "work/resolution.html")


def variations(request, site_id):
    site = Site.objects.filter(id=site_id).first()
    variants = SiteExtra.objects.filter(site=site)
    if(request.method == 'POST'):
        return JsonResponse({
            'variants': list(variants.values()),
            'site': {f: getattr(site, f, 0) for f in vars(site) if f[0] != '_'},
        })
    else:
        return render(request, "work/variations.html", {'site_id': site_id})


def addVariation(request):
    habitation = request.POST.get('habitation', None)
    census = request.POST.get('census', None)
    village = request.POST.get('village', None)
    site_id = request.POST.get('site_id', None)
    if(not habitation or not site_id):
        return JsonResponse({'status': 'error'})
    site = Site.objects.filter(id=site_id).first()
    if(not site):
        return JsonResponse({'status': 'site not found'})
    xsite = SiteExtra()
    xsite.village = village or site.village
    xsite.census = census or site.census
    xsite.habitation = habitation
    xsite.district = site.district
    xsite.division = site.division
    xsite.category = site.category
    xsite.block = site.block
    xsite.site = site
    xsite.save()
    return JsonResponse({'status': 'done'})


def api_switch_site(request):
    from_site_id = request.POST.get('from_site_id', None)
    to_site_id = request.POST.get('to_site_id', None)
    res = controller.switchSite(from_site_id, to_site_id)
    return JsonResponse({'status': res})


def revertProgress(request):
    pid = request.POST.get('pid', None)
    if(not pid):
        return JsonResponse({'status': 'progress id not found'})
    progress = ProgressQty.objects.get(id=pid)
    

def projectwise(request):
    ps = ProgressQty.objects.all()
    psv = ps.values('site__hab_id','site__district','site__village', 'site__census', 'site__habitation', *PROGRESS_QFIELDS, 'site__project__name', 'site__dprqty__has_infra', 'status', 'review')
    df = pd.DataFrame(psv)
    df.to_excel('outputs/project_hab_progress.xlsx')
    
    df['site__project__name'].fillna('extra',inplace=True)

    dfsummaryDistrict = df.groupby(['site__district','site__project__name']).sum()
    output = '<h2>Progress</h3>' + dfsummaryDistrict.to_html()
    
    dfProjectwise = df.groupby(['site__project__name']).sum()
    output += '<hr>' + dfProjectwise.to_html()
    # DPR
    dpr = DprQty.objects.filter(has_infra=True)
    dfD = pd.DataFrame(dpr.values('site__district', *PROGRESS_QFIELDS, 'site__project__name', 'has_infra'))
    dfD['site__project__name'].fillna('extra',inplace=True)
    dfDsummary = dfD.groupby(['site__project__name']).sum()
    output += '<hr><h2>DPR</h2>' + dfDsummary.to_html()

    loa = Loa.objects.all()
    dfLoa = pd.DataFrame(loa.values(*PROGRESS_QFIELDS))
    # dfDsummary = dfLoa.groupby(['area']).sum()
    dfDsummary = dfLoa.sum().to_frame()
    output += '<hr><h2>LOA</h2>' + dfDsummary.T.to_html()

    scope = SurveyQty.objects.all()
    dfD = pd.DataFrame(scope.values('site__district', *PROGRESS_QFIELDS, 'site__project__name'))
    dfD['site__project__name'].fillna('extra',inplace=True)
    dfDsummary = dfD.groupby(['site__project__name']).sum()
    output += '<hr><h2>Scope</h2>' + dfDsummary.to_html()

    return render(request, 'work/projectwise.html', {'data': output})

def divisionwise(request):
    groupby = ['site__district','site__division']
    fields = [*groupby, *PROGRESS_QFIELDS]
    output = ""

    progress = ProgressQty.objects.all()
    dfProgress = pd.DataFrame(progress.values(*fields))
    dfProgressSummary = dfProgress.groupby(groupby).sum()
    dfProgressSummary['index'] = 'Executed'
    # output = '<h2>Progress</h3>' + dfProgressSummary.to_html()
    
    # DPR
    dpr = DprQty.objects.filter(has_infra=True)
    dfDpr = pd.DataFrame(dpr.values(*fields))
    dfDprSummary = dfDpr.groupby(groupby).sum()
    dfDprSummary['index'] = 'DPR'
    # output += '<hr><h2>DPR</h2>' + dfDprSummary.to_html()

    loa = Loa.objects.all()
    dfLoa = pd.DataFrame(loa.values('area',*PROGRESS_QFIELDS))
    dfLoa['site__district'] = dfLoa['area']
    dfLoaSummary = dfLoa.groupby(['site__district']).sum()
    dfLoaSummary['index'] = 'LOA'
    # output += '<hr><h2>LOA</h2>' + dfLoaSummary.to_html()

    scope = SurveyQty.objects.all()
    dfscope = pd.DataFrame(scope.values(*fields))
    dfscopesummary = dfscope.groupby(groupby).sum()
    dfscopesummary['index'] = 'Scope'
    # output += '<hr><h2>Scope</h2>' + dfscopesummary.to_html()

    df = pd.concat([dfDprSummary, dfscopesummary, dfProgressSummary])
    df = df.reset_index()
    df = df.sort_values(['site__district','site__division'])
    df = df.set_index(['site__district','site__division','index'])
    output += df.to_html()

    dfLoaSummary = dfLoaSummary.reset_index()
    df = df.reset_index()
    dfDistrict = pd.concat([dfLoaSummary, df])
    dfDistrict = dfDistrict.groupby(['site__district','index']).sum()
    # dfDistrict = dfDistrict.set_index(['site__district', 'index'])
    # dfDistrict = dfDistrict.sort_values(['site__district','index'])
    output += '<hr>' + dfDistrict.to_html()


    return render(request, 'work/divisionwise.html', {'data': output})
