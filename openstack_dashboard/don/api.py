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
