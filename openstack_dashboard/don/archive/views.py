# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from django.conf import settings
from django.core.urlresolvers import reverse
from django import http
from horizon import tables
import time

from don import api
from don import tables as don_tables


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
    with open(JSON_FILE, 'w') as f:
        f.write(str(data.data))
    return http.HttpResponseRedirect(
        reverse('horizon:don:ovs:view'))
