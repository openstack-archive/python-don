from don import models


def save_data(timestamp, data):
    wb = models.collector.objects.create(timestamp=timestamp, data=data)
    wb.save()
    return True


def list_collection(request):
    return models.collector.objects.values('id', 'timestamp', 'data')


def get_collection(request, id=None):
    try:
        return models.collector.objects.get(id=id)
    except models.collector.DoesNotExist:
        return None


def remove_collection(request, id):
    models.collector.objects.get(id=id).delete()
