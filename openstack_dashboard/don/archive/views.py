from django.core.urlresolvers import reverse
from don import api
from don import tables as don_tables
from horizon import tables
# from horizon.views import APIView
import time
from django.conf import settings
from django import http


class ArchiveView(tables.DataTableView):
    template_name = 'don/archive/index.html'
    table_class = don_tables.CollectionTable

    def get_data(self):
        data = api.list_collection(self.request)
        for item in data:
            item['timestamp'] = str(time.ctime(float(item.get('timestamp'))))
        return data


def dbview(request):
    id = request.GET.get('id')
    data = api.get_collection(request, id)
    pwd = settings.ROOT_PATH
    JSON_FILE = pwd + '/don/ovs/don.json'
    don = open(JSON_FILE, 'w')
    don.write(str(data.data))
    don.close()
    return http.HttpResponseRedirect(
        reverse('horizon:don:ovs:view'))

'''
class DBView(APIView):
    template_name = 'don/archive/view.html'

    def get_data(self,request, context, *args, **kwargs):
        id = self.request.GET.get('id')
        data =  api.get_collection(self.request,id)
        pwd = settings.ROOT_PATH
        JSON_FILE = pwd + '/don/ovs/don.json'
        don = open(JSON_FILE,'w')
        don.write(str(data.data))
        don.close()
        time.sleep(2)
        return http.HttpResponseRedirect(
            reverse('horizon:don:ovs:view'))

'''
