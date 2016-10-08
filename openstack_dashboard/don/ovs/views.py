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
from django.http import HttpResponse
from django.shortcuts import render
from forms import PingForm
from horizon import messages
from horizon import views
import json
import os
import shlex
import subprocess

import openstack_dashboard.don.ovs.analyzer as analyzer
from openstack_dashboard.don.ovs.common import execute_cmd
from openstack_dashboard.don.ovs.common import get_env
from openstack_dashboard.don.ovs.common import get_instance_ips
from openstack_dashboard.don.ovs.common import get_router_names
import openstack_dashboard.don.ovs.path as path
from openstack_dashboard.don.ovs.plot import DotGenerator


class IndexView(views.APIView):
    # A very simple class-based view...
    template_name = 'don/ovs/index.html'

    def get_data(self, request, context, *args, **kwargs):
        # Add data to the context here...
        return context


def index(request):
    return HttpResponse('I am DON')


def view(request):
    pwd = settings.ROOT_PATH  # +'/openstack_dashboard/dashboards/admin/don/'

    JSON_FILE = pwd + '/don/ovs/don.json'
    static_path = settings.STATIC_ROOT
    '''
    COMPUTE_DOT_FILE = pwd + '/don/ovs/static/compute.dot'
    COMPUTE_SVG_FILE = pwd + '/don/ovs/static/compute.svg'
    NETWORK_DOT_FILE = pwd + '/don/ovs/static/network.dot'
    NETWORK_SVG_FILE = pwd + '/don/ovs/static/network.svg'
    COMBINED_DOT_FILE = pwd + '/don/ovs/static/don.dot'
    COMBINED_SVG_FILE = pwd + '/don/ovs/static/don.svg'
    '''
    COMPUTE_DOT_FILE = static_path + '/don/compute.dot'
    COMPUTE_SVG_FILE = static_path + '/don/compute.svg'
    NETWORK_DOT_FILE = static_path + '/don/network.dot'
    NETWORK_SVG_FILE = static_path + '/don/network.svg'
    COMBINED_DOT_FILE = static_path + '/don/don.dot'
    COMBINED_SVG_FILE = static_path + '/don/don.svg'

    macro = {}

    plotter = DotGenerator(JSON_FILE,
                           COMPUTE_DOT_FILE,
                           COMPUTE_SVG_FILE,
                           NETWORK_DOT_FILE,
                           NETWORK_SVG_FILE,
                           COMBINED_DOT_FILE,
                           COMBINED_SVG_FILE,
                           None
                           )
    plotter.plot_compute_node()
    plotter.generate_compute_svg()

    plotter.plot_network_node()
    plotter.generate_network_svg()

    plotter.plot_combined()
    plotter.generate_combined_svg()

    return render(request, "don/ovs/views.html", macro)


def analyze(request):
    pwd = settings.ROOT_PATH
    JSON_FILE = pwd + '/don/ovs/don.json'

    params = {
        'error_file': pwd + '/don/templates/don/don.error.txt',
        'test:all': True,
        'test:ping': False,
        'test:ping_count': 1,
        'test:ovs': True,
        'test:report_file': pwd + '/don/templates/don/don.report.html',
    }
    print("params ====> ", params)
    analyzer.analyze(JSON_FILE, params)
    return render(request, "don/ovs/analyze.html")


def test(request):
    return HttpResponse('Testing the setup')


def ping(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = PingForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # redirect to a new URL:
            src_ip = form.cleaned_data['src_ip']
            dst_ip = form.cleaned_data['dst_ip']
            router = form.cleaned_data['router']
            static_path = settings.STATIC_ROOT
            pwd = settings.ROOT_PATH
            JSON_FILE = pwd + '/don/ovs/don.json'

            params = {
                'json_file': pwd + '/don/ovs/don.json',
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'router': router,
                'path_file': static_path + '/don/ping.html',
                'username': 'cirros',
                'passwd': 'cubswin:)',
                'count': 2,
                'timeout': 2,
                'debug': True,
                'plot': False,
            }
            response = path.path(params)
            if response:
                error_text = response
                messages.error(request, error_text)
                return render(request, 'don/ovs/ping.html', {'form': form})

            JSON_FILE = pwd + '/don/ovs/don.json'
            COMPUTE_DOT_FILE = None
            COMPUTE_SVG_FILE = None
            NETWORK_DOT_FILE = None
            NETWORK_SVG_FILE = None
            COMBINED_DOT_FILE = static_path + '/don/ping.dot'
            COMBINED_SVG_FILE = static_path + '/don/ping.svg'
            HIGHLIGHT_FILE = static_path + '/don/ping.html'

            plotter = DotGenerator(JSON_FILE,
                                   COMPUTE_DOT_FILE,
                                   COMPUTE_SVG_FILE,
                                   NETWORK_DOT_FILE,
                                   NETWORK_SVG_FILE,
                                   COMBINED_DOT_FILE,
                                   COMBINED_SVG_FILE,
                                   HIGHLIGHT_FILE,
                                   )
            plotter.plot_combined()
            plotter.generate_combined_svg()

            return render(request, 'don/ovs/path.html')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = PingForm()
        BASE_DIR = settings.ROOT_PATH + '/don/ovs/'
        myenv = os.environ.copy()
        myenv.update(get_env(BASE_DIR + 'admin-openrc.sh'))
        output = execute_cmd(['nova', 'list'], sudo=False,
                             shell=False, env=myenv).split('\n')
        ip_list = get_instance_ips(output)
        ip_list.sort()
        router_op = execute_cmd(
            ['neutron', 'router-list'],
            sudo=False, shell=False, env=myenv).split('\n')
        router_list = get_router_names(router_op)
        router_list.sort()
        # insert first value of select menu
        ip_opt = zip(ip_list, ip_list)
        router_opt = zip(router_list, router_list)
        # ip_opt.insert(0,('','Select IP address'))
        # router_opt.insert(0,('','Select Router'))
        form.fields['src_ip'].widget.choices = ip_opt
        form.fields['dst_ip'].widget.choices = ip_opt
        form.fields['router'].widget.choices = router_opt

    return render(request, 'don/ovs/ping.html', {'form': form})


def collect(request):
    macro = {'collect_status': 'Collection failed'}
    status = 0

    BASE_DIR = settings.ROOT_PATH
    os.chdir(BASE_DIR + '/don/ovs')
    cmd = 'sudo python collector.py'
    for line in run_command(cmd):
        if line.startswith('STATUS:') and line.find(
            'Writing collected info') != -1:
            status = 1
            macro['collect_status'] = \
                "Collecton successful. Click visualize to display"
    os.chdir(BASE_DIR)
    if status:
        messages.success(request, macro['collect_status'])
    else:
        messages.error(request, macro['collect_status'])
    resp = HttpResponse(json.dumps(macro), content_type="application/json")
    return resp


def run_command(cmd):
    ps = subprocess.Popen(shlex.split(
        cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while(True):
        ret = ps.poll()  # returns None while subprocess is running
        line = ps.stdout.readline()
        yield line
        if(ret is not None):
            break


def get_status(request):
    BASE_DIR = settings.ROOT_PATH + '/don/ovs/'
    status = open(BASE_DIR + 'collector_log.txt', 'r').readline()
    if status != " " and status != '\n':
        return HttpResponse(json.dumps(
            {'status': status}), content_type="application/json")
