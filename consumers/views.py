from django.shortcuts import render, HttpResponseRedirect, reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
import pandas as pd
from django.contrib import messages
from .models import Consumer
from work.models import Site
from work.functions import getHabID,formatString
from django.db.models import F, Sum, Count, Q, FileField

@ensure_csrf_cookie
def index(request):
    data = getData()
    return render(request, "consumers/index.html", {'data': data})


def getData():
    c = Consumer.objects.values('district').annotate(records=Count('name'))
    df = pd.DataFrame(c).fillna('None')
    df.set_index('district',inplace=True)
    c = Consumer.objects.filter(isInPortal=True).values('district').annotate(count=Count('name'))
    dfp = pd.DataFrame(c).fillna('None')
    dfp.set_index('district',inplace=True)    
    df['in portal '] = dfp
    return df.to_html()


def upload(request):
    if(not request.method == 'POST'):
        return render(request, "consumers/index.html")
    file = request.FILES['file']
    upid = request.POST['upid']
    df = pd.read_excel(file, 'upload')
    df = df.fillna('')
    df_template = pd.read_excel('files/template_consumer_details.xlsx')
    cols = df_template.columns
    truths = [col in df.columns for col in df_template.columns]
    ifmatch = all(truths)
    ncreated = 0
    nupdated = 0
    if(not ifmatch):
        notmatch = [df_template.columns[i]
                    for i, col in enumerate(truths) if not col]
        messages.error(request, "Field not found– ")
        messages.error(request, notmatch)
        return HttpResponseRedirect(reverse('consumers:index'))
    for index, row in df.iterrows():
        # unique_together = ('census', 'habitation', 'name', 'consumer_no')
        print('Processing..')
        print(row)
        consumer, created = Consumer.objects.get_or_create(
            census=row[cols[0]],
            habitation=" ".join(str(row[cols[1]]).split()).upper(),
            name=" ".join(str(row[cols[3]]).split()).upper(),
            consumer_no=str(row[cols[7]]).replace(" ", "").upper()
        )
        if(created):
            ncreated += 1
        else:
            nupdated += 1
        # consumer.village = row[cols[]]
        consumer.edate = row[cols[2]]
        consumer.status = row[cols[11]]
        consumer.aadhar = row[cols[5]]
        consumer.meter_no = row[cols[8]]
        consumer.apl_bpl = row[cols[6]]
        consumer.mobile_no = row[cols[4]]
        consumer.voter_no = row[cols[9]]
        consumer.tariff = row[cols[10]]
        consumer.pdc_date = row[cols[12]]
        consumer.address1 = row[cols[13]]
        consumer.address2 = row[cols[14]]
        consumer.remark = row[cols[15]]
        censusSite = Site.objects.filter(census = row[cols[0]]).first()
        if(censusSite):
            consumer.district = censusSite.district
            consumer.village = censusSite.village

        consumer.changeid = upid
        hab_id = getHabID(census=row[cols[0]], habitation=row[cols[1]])
        if(Site.objects.filter(hab_id=hab_id).exists()):
            site = Site.objects.get(hab_id=hab_id)
            consumer.site = site
        try:
            consumer.save()
        except Exception as ex:
            messages.error(request, ex.__str__())
            print('Processing..')
            print(row)
            print(ex)
    messages.success(request, '{} updated. {} uploaded of {} records'.format(
        nupdated, ncreated, len(df)))
    return HttpResponseRedirect(reverse('consumers:index'))


def api_getConsumers(request):
    if(request.method != 'POST'):
        return JsonResponse(
            'nothing to do'
        )
    filterString = {}
    habid = request.POST.get('habid', None)
    if(habid):
        filterString['hab_id__icontains'] = habid
    habid_exact = request.POST.get('habid_exact',None)
    if(habid_exact):
        filterString['hab_id__exact'] = habid_exact
    inPortal = request.POST.get('inPortal',None)
    if(inPortal):
        filterString['isInPortal'] = True
    village = request.POST.get('village', None)
    village = formatString(village)
    if(village):
        filterString['village__icontains'] = village

    consumers = Consumer.objects.filter(**filterString)
    df = pd.DataFrame(consumers.values()).iloc[:, 4:]
    df.to_excel('outputs/filtered_consumers.xlsx')
    return JsonResponse(
        {
            'consumers': df.to_html()
        })
