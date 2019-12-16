from django.db import models
import re
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from simple_history.models import HistoricalRecords
# from work.functions import getHabID, getSiteProgress, formatString

def getHabID(census, habitation):
    return re.sub('[\W]+', '', "{}{}".format(census, habitation)).upper()


class Test(models.Model):
    def __str__(self):
        return self.hab_id
    ref_id = models.CharField(max_length=200)

# Create your models here.
# DPR sites plus surveyed


class Timestamp(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,  blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True,  blank=True, null=True)

    class Meta:
        abstract = True


class Common(Timestamp):
    changeid = models.CharField(max_length=50, blank=True, null=True)
    history = HistoricalRecords(inherit=True)
    # to save without history!!

    def _save(self, *args, **kwargs):
        self.skip_history_when_saving = True
        try:
            ret = self.save(*args, **kwargs)
        finally:
            del self.skip_history_when_saving
        return ret

    class Meta:
        abstract = True


class Log(Common):
    model = models.CharField(max_length=50, blank=True, null=True)


class SiteMeta(models.Model):
    class Meta:
        abstract = True
    hab_id = models.CharField(max_length=50, unique=True)
    approve_id = models.CharField(max_length=50, blank=True, null=True)
    village = models.CharField(max_length=50)
    census = models.CharField(max_length=6, blank=True)
    habitation = models.CharField(max_length=50)
    district = models.CharField(max_length=50)
    division = models.CharField(max_length=50)
    category = models.CharField(max_length=50, null=True, blank=True)
    block = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        self.hab_id = getHabID(census=self.census, habitation=self.habitation)
        self.habitation = str(self.habitation).upper()
        self.village = str(self.village).upper()
        print('saving... {}'.format(self.hab_id))
        # super(SiteMeta, self).save(*args, **kwargs)
        super().save(*args, **kwargs)

class Qfields(models.Model):
    ht = models.FloatField(blank=True, null=True)
    ht_conductor = models.FloatField(blank=True, null=True)
    lt_1p = models.FloatField(blank=True, null=True)
    lt_3p = models.FloatField(blank=True, null=True)
    dtr_25 = models.IntegerField(blank=True, null=True)
    dtr_63 = models.IntegerField(blank=True, null=True)
    dtr_100 = models.IntegerField(blank=True, null=True)
    pole_lt_8m = models.IntegerField(blank=True, null=True)
    pole_ht_8m = models.IntegerField(blank=True, null=True)
    pole_8m = property(lambda self: sum(
        [qty for qty in [self.pole_lt_8m, self.pole_ht_8m] if qty != None]))
    pole_9m = models.IntegerField(blank=True, null=True)
    class Meta:
        abstract = True

class Site(Common, SiteMeta):
    def __str__(self):
        return self.hab_id
    origin = models.ForeignKey(
        "self", on_delete=models.SET_NULL, blank=True, null=True)
    # def save(self, *args, **kwargs):
    #     self.hab_id = getHabID(census=self.census, habitation=self.habitation)
    #     super(Site, self).save(*args, **kwargs)


class DprQty(Common, Qfields):
    def __str__(self):
        return "{}".format(self.site)
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    category = models.CharField(max_length=50)
    mode = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    hh_bpl = models.IntegerField(blank=True, null=True)
    hh_bpl_metered = models.IntegerField(blank=True, null=True)
    hh_metered = models.IntegerField(blank=True, null=True)
    hh_unmetered = models.IntegerField(blank=True, null=True)
    hh_apl_free = models.IntegerField(blank=True, null=True)
    hh_apl_not_free = models.IntegerField(blank=True, null=True)
    # ht = models.FloatField(blank=True, null=True)
    # lt_3p = models.FloatField(blank=True, null=True)
    # lt_1p = models.FloatField(blank=True, null=True)
    # dtr_100 = models.IntegerField(blank=True, null=True)
    # dtr_63 = models.IntegerField(blank=True, null=True)
    # dtr_25 = models.IntegerField(blank=True, null=True)
    remark = models.CharField(max_length=100, blank=True, null=True)
    has_infra = models.BooleanField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if(sum([self.ht, self.lt_3p, self.lt_1p, self.dtr_100, self.dtr_63, self.dtr_25]) > 0):
            self.has_infra = True
        else:
            self.has_infra = False
        super(DprQty, self).save(*args, **kwargs)

class SurveyQty(Common, Qfields):
    def __str__(self):
        return "{} - {}".format(self.site, self.approval_status)
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    approval_status = models.CharField(max_length=200, blank=True, null=True)
    remark = models.CharField(max_length=200, blank=True, null=True)


class ShiftedMeta(models.Model):
    class Meta:
        abstract = True
    acsr = models.FloatField(blank=True, null=True)
    cable_3p = models.FloatField(blank=True, null=True)
    cable_1p = models.FloatField(blank=True, null=True)
    pole_8m = models.IntegerField(blank=True, null=True)
    pole_9m = models.IntegerField(blank=True, null=True)
    dtr_100 = models.IntegerField(blank=True, null=True)
    dtr_63 = models.IntegerField(blank=True, null=True)
    dtr_25 = models.IntegerField(blank=True, null=True)
    remark = models.CharField(max_length=200, blank=True, null=True)


class ShiftedQty(Common, ShiftedMeta):
    def __str__(self):
        return "{}".format(self.site)
    site = models.OneToOneField(Site, on_delete=models.CASCADE)


def habCompletionDocPath(instance, filename):
    return 'CompletionDocuments/{}/{}'.format(instance.site.district, instance.site.hab_id + "-" + filename)


class ProgressMeta(Common, Qfields):
    class Meta:
        abstract = True
    remark = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=200, blank=True, null=True,
                              choices=(
                                  ('completed', 'completed'),
                                  ('ongoing', 'ongoing'),
                                  ('not started', 'not started'),
                                  ('canceled', 'canceled'),
                              ))

    cert = models.BooleanField(default=False)
    document = models.FileField(
        upload_to=habCompletionDocPath, null=True, blank=True)
    
    review = models.CharField(default='not reviewed', max_length=50, blank=True, null=True,
                              choices=(
                                  ('ok', 'ok'),
                                  ('issue', 'issue'),
                                  ('not reviewed', 'not review'),
                              ))
    review_text = models.TextField(null=True, blank=True)

    # def _pole_8m(self):
    #     return sum([qty for qty in [self.pole_lt_8m, self.pole_ht_8m] if qty != None])
    # pole_8m = property(lambda self: sum(
    #     [qty for qty in [self.pole_lt_8m, self.pole_ht_8m] if qty != None]))
    # pole_9m = property(lambda self: sum(self.dtr_100, self.dtr_63, self.dtr_25))

class ProgressQty(ProgressMeta):
    def __str__(self):
        return "{}".format(self.site)
    site = models.OneToOneField(Site, on_delete=models.CASCADE)


class SiteExtra(Common, SiteMeta):
    def __str__(self):
        return self.hab_id
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, blank=True, null=True)
    # def save(self, *args, **kwargs):
    #     self.hab_id = getHabID(census=self.census, habitation=self.habitation)
    #     super(SiteExtra, self).save(*args, **kwargs)


class ProgressQtyExtra(ProgressMeta):
    def __str__(self):
        return "{}".format(self.site)
    site = models.OneToOneField(SiteExtra, on_delete=models.CASCADE)


class ShiftedQtyExtra(Common, ShiftedMeta):
    def __str__(self):
        return "{}".format(self.site)
    site = models.OneToOneField(SiteExtra, on_delete=models.CASCADE)


def HeadlineDocPath(instance, filename):
    return 'Resolutions/{}-{}'.format(instance.created_at, filename)


class Resolution(Timestamp):
    def __str__(self):
        if(self.status == 'pending'):
            status = "🔴"
        elif(self.status == 'done'):
            status = "✅"
        else:
            status = "🌕"
        len = 30
        return "{} {} | {}".format(status, self.statement[:len], self.resolution[:len])
        # return "{} | {}".format(status, self.__dict__)
    statement = models.TextField()
    resolution = models.TextField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(null=True, blank=True,
                              max_length=10,
                              choices=(
                                  ("done", "done"),
                                  ("pending", "pending"),
                                  ("deferred", "deferred"),
                              )
                              )
    document = models.FileField(
        upload_to=HeadlineDocPath, blank=True, null=True)
    history = HistoricalRecords(inherit=True)


class ResolutionLink(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    resolution = models.ForeignKey(
        Resolution, on_delete=models.CASCADE, null=True)
    # user1 = models.CharField(max_length=100, null=True, blank=True)

def LoaDocPath(instance, filename):
    return 'LOA/{}-{}'.format(filename)

class Loa(Qfields):
    area = models.CharField(max_length=50, unique=True)
    supply_cost = models.FloatField(blank=True, null=True)
    erection_cost = models.FloatField(blank=True, null=True)
    document = models.FileField(
        upload_to=LoaDocPath, blank=True, null=True)
