from work.models import Resolution


def context_data(request):
    resolutions = Resolution.objects.exclude(status="done").order_by(
        '-deadline', '-updated_at', '-created_at')
    return {'resolutions': resolutions}
