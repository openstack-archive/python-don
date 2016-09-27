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

import pprint
import sys

from openstack_dashboard.don.ovs.common import load_json

if len(sys.argv) != 2:
    print ('Usage: ' + sys.argv[0] + ' <json file to display>')
    exit(1)

info = load_json(sys.argv[1])
pprint.pprint(info)
