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

# common.py: Common functions and data structures used by multiple modules.
import json
import paramiko
import pprint
import re
import subprocess
import sys
import yaml

# Program settings
settings = {
    'debug': False,
}

# Helper functions.


def debug(msg):
    if settings['debug']:
        if sys.stdout != sys.__stdout__:
            tmp = sys.stdout
            sys.stdout = sys.__stdout__
            print('DEBUG: ' + msg)
            sys.stdout = tmp
        else:
            print('DEBUG: ' + msg)


def error(msg):
    if sys.stdout != sys.__stdout__:
        tmp = sys.stdout
        sys.stdout = sys.__stdout__
        print('ERROR: ' + msg)
        sys.stdout = tmp
    else:
        print('ERROR: ' + msg)


def warning(msg):
    if sys.stdout != sys.__stdout__:
        tmp = sys.stdout
        sys.stdout = sys.__stdout__
        print('WARNING: ' + msg)
        sys.stdout = tmp
    else:
        print('WARNING: ' + msg)


def status_update(msg):
    # storing in log file for interactive display on UI
    log = open('collector_log.txt', 'w')
    if sys.stdout != sys.__stdout__:
        tmp = sys.stdout
        sys.stdout = sys.__stdout__
        print('STATUS: ' + msg)
        log.write('msg')
        sys.stdout = tmp
    else:
        print('STATUS: ' + msg)
        log.write(msg)


def dump_json(json_info, json_filename):
    try:
        outfile = open(json_filename, "w")
    except IOError as e:
        print(e)
        print('Couldn\'t open <%s>; Redirecting output to stdout' % json_filename)
        outfile = sys.stdout

    json.dump(json_info, outfile)
    outfile.flush()
    outfile.close()


def load_json(json_filename):
    try:
        infile = open(json_filename, "r")
    except IOError as e:
        print(e)
        print('Couldn\'t open <%s>; Error!' % json_filename)
        return None

    tmp = json.load(infile)
    infile.close()
    return tmp


def connect_to_box(server, username, password, timeout=3):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(server, username=username,
                    password=password, timeout=timeout)
    except Exception:
        return None
    return ssh
# def connect_to_box (server, username, password,timeout=3) :
#     pass

# this function i will modify to get data from a file instead of giving
# command directly


def ssh_cmd(ssh, cmd):
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    error = ssh_stderr.read()
    if len(error):
        print('ERROR: ' + error)
    output = ssh_stdout.read()
    ssh_stdout.flush()
    return output

# TODO (right now assumes subnet mask to be 24 bits long)


def get_subnet(ip):
    subnet = '.'.join(ip.split('.')[:3])
    return subnet


def get_router(namespace, info):
    routers = info.get('routers', None)
    if not routers:
        return 'Unknown'
    for router in routers.keys():
        if routers[router]['id'] in namespace:
            return router

    return 'Unknown'

# TODO (guaranteed way of figuring out whether network is private or public)


def is_network_public(ip, vm, info):
    vm_entry = info['vms'].get(vm)
    entry = vm_entry['interfaces'].get(ip, None)
    if not entry:
        error('Interface: ' + ip + ' does not exist!')
        return False
    if re.search('public', entry['network']):
        return True
    return False


def get_intf_ip(info, interface):
    intf = strip_interface(interface)
    return info['tap_to_ip'].get(intf, 'x.x.x.x')


def ip_to_intf(info, ip):
    for intf, intf_ip in info['tap_to_ip'].iteritems():
        if intf_ip == ip:
            return intf
    return None


def router_to_namespace(info, router):
    router_entry = info['routers'].get(router, None)
    if not router_entry:
        return None
    net_id = router_entry.get('id', None)
    if not net_id:
        return None
    return 'qrouter-' + net_id


def intf_to_namespace(info, intf):
    nms_dict = info['namespaces']
    for nms in nms_dict.keys():
        if nms_dict[nms].has_key('interfaces'):
            if nms_dict[nms]['interfaces'].has_key(intf):
                return nms
    return None


def get_ip_network(info, vm, ip):
    intf_entry = info['vms'][vm]['interfaces'].get(ip, None)
    if not intf_entry:
        return 'unknown'
    return intf_entry.get('network', 'unknown')


def get_vlan_tag(info, interface):
    intf = strip_interface(interface)

    intf = 'qvo' + intf
    br_int = info['bridges']['br-int']
    debug('Getting vlan tag for ' + intf)
    if br_int['ports'].has_key(intf):
        return br_int['ports'][intf].get('tag', '0')
    return '0'


def strip_interface(intf):
    x = intf
    x = x.replace('tap', '')
    x = x.replace('qbr', '')
    x = x.replace('qvb', '')
    x = x.replace('qvo', '')
    return x


def get_port_ovs_id_tag(info, vm, port_ip):
    for key, ip in info['tap_to_ip'].iteritems():
        if ip == port_ip:
            qvo = 'qvo' + key
            qvo_entry = info['bridges']['br-int']['ports'].get(qvo, None)
            if not qvo_entry:
                return None
            ovs_id = qvo_entry.get('id', None)
            ovs_tag = qvo_entry.get('tag', None)
            return (ovs_id, ovs_tag)
    return None


def execute_cmd(cmd, sudo=False, shell=False, env=None):
    if sudo:
        if shell is False:
            mycmd = ['sudo'] + cmd
        else:
            mycmd = 'sudo ' + cmd
    else:
        mycmd = cmd

    pprint.pprint(mycmd)
    return subprocess.check_output(mycmd,
                                   shell=shell,
                                   stderr=subprocess.STDOUT,
                                   env=env,
                                   universal_newlines=True).replace(
                                       '\t', '    ')


def get_instance_ips(objs):
    ip_list = []
    for line in objs:
        if re.search('^\+', line) or re.search('^$', line) or re.search(
            'Networks', line):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts]
        # vm = parts[2]
        networks = parts[6].split(';')
        networks = [x.strip() for x in networks]
        for entry in networks:
            # excluding ipv6 ip
            if len(entry.split(',')) > 1:
                # network = entry.split('=')[0]
                ip = filter(lambda a: re.search("(\d+\.\d+\.\d+\.\d+)",
                                                a) is not None,
                            entry.split('=')[1].split(','))[0].strip()
                ip_list.append(ip)
            else:
                ip_list.append(entry.split(',')[0].split('=')[1])
    return ip_list


def get_router_names(objs):
    routers = []

    for line in objs:
        if re.search('^\+', line) or re.search('^$', line) or re.search(
            'external_gateway_info', line):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts]

        name = parts[2]
        routers.append(name)
    return routers


def get_env(file_path):
    try:
        lines = open(file_path, 'r').read().splitlines()
    except IOError as e:
        raise "%s :%s" % (e.args[1], file_path)
    env = {}
    for line in lines:
        if line.startswith('export'):
            m = re.search(r'export (.+)=(.+)', line)
            if m:
                key = m.group(1).replace('"', '')
                val = m.group(2).replace('"', '')
                env.update({key: val})
    return env


def get_vm_credentials(config_file='credentials.yaml'):
    try:
        with open(config_file, 'r') as s:
            return yaml.safe_load(s)
    except IOError as e:
        raise '%s :%s' % (e.args[1], config_file)
