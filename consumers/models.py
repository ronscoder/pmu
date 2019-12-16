from django.db import models
from work.models import Site


class Timestamp(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,  blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True,  blank=True, null=True)

    class Meta:
        abstract = True


class Common(Timestamp):
    changeid = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        abstract = True


class Consumer(Common):
    def __str__(self):
        return "{} - {} - ({}) - {} portal({})".format(self.name, self.consumer_no, self.habitation, self.census, self.isInPortal)

    class Meta:
        unique_together = ('census', 'habitation', 'name', 'consumer_no')
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True)
    hab_id = models.CharField(max_length=50, null=True, blank=True)
    village = models.CharField(max_length=50, null=True, blank=True)
    census = models.IntegerField()
    habitation = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    consumer_no = models.CharField(max_length=50, null=True, blank=True)
    edate = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    aadhar = models.CharField(max_length=50, null=True, blank=True)
    meter_no = models.CharField(max_length=50, null=True, blank=True)
    apl_bpl = models.CharField(max_length=3, null=True, blank=True)
    mobile_no = models.CharField(max_length=20, null=True, blank=True)
    voter_no = models.CharField(max_length=20, null=True, blank=True)
    tariff = models.CharField(max_length=20, null=True, blank=True)
    pdc_date = models.CharField(max_length=20, null=True, blank=True)
    address1 = models.CharField(max_length=100, null=True, blank=True)
    address2 = models.CharField(max_length=100, null=True, blank=True)
    remark = models.CharField(max_length=100, null=True, blank=True)
    isInPortal = models.BooleanField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.habitation = " ".join(str(self.habitation).split()).upper()
        self.name = " ".join(str(self.name).split()).upper()
        self.consumer_no = str(self.consumer_no).replace(" ", "").upper()
        super(Consumer, self).save(*args, **kwargs)
