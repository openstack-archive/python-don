# -*- coding: utf-8 -*-

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

import argparse
import ConfigParser
import os
import pprint
import re

import openstack_dashboard.don.ovs.common as common

don_config = ConfigParser.ConfigParser()
try:
    don_config.read('/etc/don/don.conf')
except Exception as e:
    print(e.value)
deployment_type = don_config.get('DEFAULT', 'deployment_type')


def get_env(filename):
    try:
        lines = open(os.getcwd() + os.sep + filename, 'r').read().splitlines()
    except IOError as e:
        print("%s :%s" % (e.args[1], filename))
        raise
    env = {}
    for line in lines:
        if line.startswith('export'):
            m = re.search(r'export (.+)=(.+)', line)
            if m:
                key = m.group(1).replace('"', '')
                val = m.group(2).replace('"', '')
                env.update({key: val})
    return env

myenv = os.environ.copy()
myenv.update(get_env('admin-openrc.sh'))

# Contains all info gathered by parsing the output of commands
info = {
    'vms': {},
    'brctl': {},
    'bridges': {
        'br-ex': {'ports': {}},
        'br-int': {'ports': {}},
        'br-tun': {'ports': {}}
    },
    'floating_ips': {},
}


def add_new_command(cmd_dict, cmd_key, cmd):
    if cmd_dict.has_key(cmd_key):
        common.error(cmd_key + ' already exists in command dictionary')
        return
    cmd_dict[cmd_key] = cmd


def record_linuxbridge(bridge, interface_list):
    brctl_dict = info['brctl']
    if brctl_dict.has_key(bridge):
        common.error('Bridge ' + bridge + ' repeated! Overwriting!')
    brctl_dict[bridge] = {'interfaces': interface_list}


def get_bridge_entry(br):
    bridge_dict = info['bridges']
    if not bridge_dict.has_key(br):
        common.error('Bridge ' + br + ' does not exist! Supported bridges: ' +
                     str(bridge_dict.keys()))
        return None
    return bridge_dict.get(br)


# Parser functions (for each command). Each function has the sample input
# as a comment above it.
'''
  <uuid>31b1cfcc-ca85-48a9-a84a-8b222d377080</uuid>
      <nova:name>VM1</nova:name>
      <source bridge='qbrb0f5cfc8-4d'/>
  <uuid>f9743f1c-caeb-4892-af83-9dc0ac757545</uuid>
      <nova:name>VM2</nova:name>
      <source bridge='qbr6ce314cb-a5'/>
'''


def cat_instance_parser(parse_this):
    vm_dict = info['vms']

    uuid = None
    name = None
    src_bridge = None
    for line in parse_this:
        m = re.search('<uuid>(\S+)</uuid>', line)
        if m:
            uuid = m.group(1)
            continue
        m = re.search('<nova:name>(\S+)</nova:name>', line)
        if m:
            name = m.group(1)
            continue
        m = re.search('<source bridge=\'(\S+)\'/>', line)
        if m:
            src_bridge = m.group(1)

            if not vm_dict.has_key(name):
                vm_dict[name] = {}

            vm_entry = vm_dict[name]
            vm_entry['uuid'] = uuid
            if not vm_entry.has_key('src_bridge'):
                vm_entry['src_bridge'] = []
                vm_entry['tap_dev'] = []
            vm_entry['src_bridge'].append(src_bridge)
            vm_entry['tap_dev'].append(src_bridge.replace('qbr', 'tap'))


'''
bridge name	bridge id   STP enabled	interfaces
qbr6ce314cb-a5      8000.9255d5550cf8   no      qvb6ce314cb-a5
                            tap6ce314cb-a5
qbrb0f5cfc8-4d      8000.b2277f2c981b   no      qvbb0f5cfc8-4d
                            tapb0f5cfc8-4d
virbr0      8000.000000000000   yes
'''


def brctl_show_parser(parse_this):
    interfaces = []
    bridge = None
    for line in parse_this:
        m = re.search('(qbr\S+)\s+\S+\s+\S+\s+(\S+)', line)
        if m:
            # We already have a bridge, that means we are now lookign at the
            # next bridge
            if bridge:
                record_linuxbridge(bridge, interfaces)
                interfaces = []
            bridge = m.group(1)
            interfaces.append(m.group(2))
            continue
        m = re.search('^\s+(\S+)', line)
        if m:
            interfaces.append(m.group(1))

    # handle the last bridge
    if bridge:
        record_linuxbridge(bridge, interfaces)

'''
ubuntu@ubuntu-VirtualBox:~/don$ sudo ovs-vsctl show
0fc4d93f-28e0-408a-8edb-21d5ec76b2c3
    Bridge br-tun
        fail_mode: secure
        Port patch-int
            Interface patch-int
                type: patch
                options: {peer=patch-tun}
        Port br-tun
            Interface br-tun
                type: internal
    Bridge br-int
        fail_mode: secure
        Port "tap3b74b285-71"
            tag: 2
            Interface "tap3b74b285-71"
                type: internal
        Port patch-tun
            Interface patch-tun
                type: patch
                options: {peer=patch-int}
        Port "qvob0f5cfc8-4d"
            tag: 2
            Interface "qvob0f5cfc8-4d"
        Port "qr-77ce7d4c-d5"
            tag: 1
            Interface "qr-77ce7d4c-d5"
                type: internal
        Port "qr-56cf8a2d-27"
            tag: 2
            Interface "qr-56cf8a2d-27"
                type: internal
        Port "qvo6ce314cb-a5"
            tag: 2
            Interface "qvo6ce314cb-a5"
        Port br-int
            Interface br-int
                type: internal
        Port "tap9d44135a-45"
            tag: 1
            Interface "tap9d44135a-45"
                type: internal
    Bridge br-ex
        Port "qg-2909632b-b8"
            Interface "qg-2909632b-b8"
                type: internal
        Port br-ex
            Interface br-ex
                type: internal
        Port "qg-e2fb759b-60"
            Interface "qg-e2fb759b-60"
                type: internal
    ovs_version: "2.0.2"
'''


def ovs_vsctl_show_parser(parse_this):
    bridge = None
    bridge_dict = info['bridges']
    for line in parse_this:
        m = re.search('Bridge\s+(br-\S+)', line)
        if m:
            bridge = str(m.group(1))
            if not bridge_dict.has_key(bridge):
                common.error(
                    'Skipping bridge [' + bridge + ']! Supported bridges: ' +
                    str(bridge_dict.keys()))
                bridge = None
                continue
            bridge_entry = bridge_dict.get(bridge)
        if bridge:
            m = re.search('fail_mode: (\S+)', line)
            if m:
                bridge_entry['fail_mode'] = m.group(1)
                continue
            m = re.search('Port (\S+)', line)
            if m:
                # the port names seem to have double quotes around them!
                port = m.group(1).replace('"', '')
                if not bridge_entry['ports'].has_key(port):
                    bridge_entry['ports'][port] = {}
                port_entry = bridge_entry['ports'][port]
                continue
            m = re.search('tag: (\d+)', line)
            if m:
                port_entry['tag'] = m.group(1)
                continue
            m = re.search('Interface (\S+)', line)
            if m:
                # the interface names seem to have double quotes around them!
                interface = m.group(1).replace('"', '')
                if not port_entry.has_key('interfaces'):
                    port_entry['interfaces'] = {}
                port_entry['interfaces'][interface] = {}
                interface_entry = port_entry['interfaces'][interface]
                continue
            m = re.search('type: (\S+)', line)
            if m:
                interface_entry['type'] = m.group(1)
                continue
            m = re.search('options: {(\S+)}', line)
            if m:
                options = m.group(1)
                interface_entry['options'] = options
                continue

'''
OFPT_FEATURES_REPLY (xid=0x2): dpid:00008207ee8eee4d
n_tables:254, n_buffers:256
capabilities: FLOW_STATS TABLE_STATS PORT_STATS QUEUE_STATS ARP_MATCH_IP
actions: OUTPUT SET_VLAN_VID SET_VLAN_PCP STRIP_VLAN SET_DL_SRC SET_DL_DST \
SET_NW_SRC SET_NW_DST SET_NW_TOS SET_TP_SRC SET_TP_DST ENQUEUE
 4(patch-tun): addr:e2:ce:31:60:94:e0
     config:     0
     state:      0
     speed: 0 Mbps now, 0 Mbps max
 5(tap9d44135a-45): addr:00:00:00:00:00:00
     config:     PORT_DOWN
     state:      LINK_DOWN
     speed: 0 Mbps now, 0 Mbps max
 6(qr-77ce7d4c-d5): addr:00:00:00:00:00:00
     config:     PORT_DOWN
     state:      LINK_DOWN
     speed: 0 Mbps now, 0 Mbps max
 7(tap3b74b285-71): addr:00:00:00:00:00:00
     config:     PORT_DOWN
     state:      LINK_DOWN
     speed: 0 Mbps now, 0 Mbps max
 8(qr-56cf8a2d-27): addr:00:00:00:00:00:00
     config:     PORT_DOWN
     state:      LINK_DOWN
     speed: 0 Mbps now, 0 Mbps max
 9(qvob0f5cfc8-4d): addr:7a:82:4f:4e:a0:ab
     config:     0
     state:      0
     current:    10GB-FD COPPER
     speed: 10000 Mbps now, 0 Mbps max
 10(qvo6ce314cb-a5): addr:42:92:2a:95:28:ed
     config:     0
     state:      0
     current:    10GB-FD COPPER
     speed: 10000 Mbps now, 0 Mbps max
 LOCAL(br-int): addr:82:07:ee:8e:ee:4d
     config:     0
     state:      0
     speed: 0 Mbps now, 0 Mbps max
OFPT_GET_CONFIG_REPLY (xid=0x4): frags=normal miss_send_len=0
'''


def ovs_ofctl_show_br_parser(bridge, parse_this):
    bridge_dict = info['bridges']
    if not bridge_dict.has_key(bridge):
        common.error('Skipping bridge [' + bridge + ']! Supported bridges: ' + str(bridge_dict.keys()))
        return
    bridge_entry = bridge_dict.get(bridge)
    pprint.pprint(bridge_entry)

    for line in parse_this:
        m = re.search('(\d+)\((\S+)\):\s+addr:(\S+)', line)
        if m:
            port_id = m.group(1)
            port = m.group(2)
            port_mac = m.group(3)
            if not bridge_entry['ports'].has_key(port):
                bridge_entry['ports'][port] = {}
            port_entry = bridge_entry['ports'][port]
            port_entry['id'] = port_id
            port_entry['mac'] = port_mac
            continue

        m = re.search('(\w+)\((\S+)\):\s+addr:(\S+)', line)
        if m:
            port_id = m.group(1)
            port = m.group(2)
            port_mac = m.group(3)
            if not bridge_entry['ports'].has_key(port):
                bridge_entry['ports'][port] = {}
            port_entry = bridge_entry['ports'][port]
            port_entry['id'] = port_id
            port_entry['mac'] = port_mac

# These three are all wrappers for each of the three bridges


def ovs_ofctl_show_br_int_parser(parse_this):
    ovs_ofctl_show_br_parser('br-int', parse_this)


def ovs_ofctl_show_br_ex_parser(parse_this):
    ovs_ofctl_show_br_parser('br-ex', parse_this)


def ovs_ofctl_show_br_tun_parser(parse_this):
    ovs_ofctl_show_br_parser('br-tun', parse_this)

'''
+--------------------------------------+-------+--------+------------+-------------+--------------------------------------------------------+
| ID                                   | Name  | Status | Task State | Power State | Networks                                               |
+--------------------------------------+-------+--------+------------+-------------+--------------------------------------------------------+
| 31b1cfcc-ca85-48a9-a84a-8b222d377080 | VM1   | ACTIVE | -          | Running     | private=10.0.2.3                                       |
| f9743f1c-caeb-4892-af83-9dc0ac757545 | VM2   | ACTIVE | -          | Running     | private=10.0.2.4                                       |
| 83b547b9-9578-4840-997a-5aa1c4e829b0 | VM3-1 | ACTIVE | -          | Running     | private2=10.0.3.3                                      |
| 17b4685e-5cbe-4dd1-862a-6f89c191e1e7 | VM3-2 | ACTIVE | -          | Running     | private2=10.0.3.4                                      |
| ee4952a3-0700-42ea-aab3-7503bc9d87e2 | VM4   | ACTIVE | -          | Running     | private2=10.0.3.5; public=172.24.4.4; private=10.0.2.5 |
+--------------------------------------+-------+--------+------------+-------------+--------------------------------------------------------+
'''


def nova_list_parser(parse_this):
    vm_dict = info['vms']

    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or \
                re.search('Networks', line):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts]

        vm = parts[2]
        networks = parts[6].split(';')
        networks = [x.strip() for x in networks]

        if not vm_dict.has_key(vm):
            vm_dict[vm] = {'interfaces': {}}

        for entry in networks:
            # excluding ipv6 ip
            if len(entry.split(',')) > 1:
                network = entry.split('=')[0]
                ip = filter(lambda a: re.search("(\d+\.\d+\.\d+\.\d+)", a) is not
                            None, entry.split('=')[1].split(','))[0].strip()
            else:
                (network, ip) = entry.split(',')[0].split('=')
            vm_dict[vm]['interfaces'][ip] = {'network': network}

    pass


'''
+--------------------------------------+------+-------------------+-----------------------------------------------------------------------------------+
| id                                   | name | mac_address       | fixed_ips                                                                         |
+--------------------------------------+------+-------------------+-----------------------------------------------------------------------------------+
| 1dd820b1-98bd-4f39-b1ab-e89ecc67ae43 |      | fa:16:3e:0f:36:26 | {"subnet_id": "75ae4ce8-495d-4f53-93d1-bf98e55d6658", "ip_address": "172.24.4.4"} |
| 1f73af79-fa69-4433-bcab-16d7a0bc2607 |      | fa:16:3e:dc:c8:de | {"subnet_id": "dbc9717f-5a08-48bb-92e2-ed2da443541b", "ip_address": "10.0.3.1"}   |
| 2909632b-b8a3-436b-aabd-9868d0c1051e |      | fa:16:3e:af:95:a9 | {"subnet_id": "75ae4ce8-495d-4f53-93d1-bf98e55d6658", "ip_address": "172.24.4.2"} |
| 3b74b285-71d0-4311-8a69-2b032eebbe13 |      | fa:16:3e:70:09:45 | {"subnet_id": "1083b740-45ce-49be-b603-73cbc26af5d7", "ip_address": "10.0.2.2"}   |
| 56cf8a2d-27b7-4eab-a334-349c70520868 |      | fa:16:3e:8a:ce:cb | {"subnet_id": "1083b740-45ce-49be-b603-73cbc26af5d7", "ip_address": "10.0.2.1"}   |
| 6ce314cb-a599-4af8-8187-bdb0bfa88809 |      | fa:16:3e:83:b1:60 | {"subnet_id": "1083b740-45ce-49be-b603-73cbc26af5d7", "ip_address": "10.0.2.4"}   |
| 77ce7d4c-d5b9-4669-b23c-b0d9ee5f58c8 |      | fa:16:3e:a6:de:15 | {"subnet_id": "531f1674-2b46-4ad7-9d73-4c41d215cc99", "ip_address": "10.0.0.1"}   |
| 9c34adc0-c655-4b00-89ba-ca65def56fe0 |      | fa:16:3e:a1:e7:f5 | {"subnet_id": "dbc9717f-5a08-48bb-92e2-ed2da443541b", "ip_address": "10.0.3.4"}   |
| 9d44135a-4551-4448-9c80-d211b023c3eb |      | fa:16:3e:80:83:c9 | {"subnet_id": "531f1674-2b46-4ad7-9d73-4c41d215cc99", "ip_address": "10.0.0.2"}   |
| b0f5cfc8-4da0-42ad-8c18-6f29870bfb2a |      | fa:16:3e:ae:a2:17 | {"subnet_id": "1083b740-45ce-49be-b603-73cbc26af5d7", "ip_address": "10.0.2.3"}   |
| c03437a8-8a44-4615-b160-e1ef227d63c5 |      | fa:16:3e:7f:b6:a5 | {"subnet_id": "dbc9717f-5a08-48bb-92e2-ed2da443541b", "ip_address": "10.0.3.5"}   |
| cb7d8a29-8140-4ed0-a1c7-03cbf0be0c5b |      | fa:16:3e:33:ee:b1 | {"subnet_id": "1083b740-45ce-49be-b603-73cbc26af5d7", "ip_address": "10.0.2.5"}   |
| e2fb759b-602a-4fcd-8674-e8f5fe297dbc |      | fa:16:3e:ea:47:b5 | {"subnet_id": "75ae4ce8-495d-4f53-93d1-bf98e55d6658", "ip_address": "172.24.4.3"} |
| e4f25d71-5684-4ccc-8114-2465a84ecc58 |      | fa:16:3e:90:c7:d3 | {"subnet_id": "dbc9717f-5a08-48bb-92e2-ed2da443541b", "ip_address": "10.0.3.2"}   |
| f57aa80e-2ef3-4031-a0a4-bc12d2445687 |      | fa:16:3e:2e:6e:91 | {"subnet_id": "dbc9717f-5a08-48bb-92e2-ed2da443541b", "ip_address": "10.0.3.3"}   |
+--------------------------------------+------+-------------------+-----------------------------------------------------------------------------------+
'''


def neutron_port_list_parser(parse_this):
    tap_to_ip = {}

    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or \
                re.search('fixed_ips', line):
            continue

        parts = line.split('|')
        parts = [x.strip() for x in parts]

        tap = parts[1][:11]
        # ip = parts[4].split(':')[-1].replace('}', '')
        m = re.search('"ip_address": "(\S+)"', parts[4])
        if m:
            ip = m.group(1)
        tap_to_ip[tap] = ip

    info['tap_to_ip'] = tap_to_ip
    pass

'''
+--------------------------------------+---------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+-------------+-------+
| id                                   | name    | external_gateway_info                                                                                                                                                                  | distributed | ha    |
+--------------------------------------+---------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+-------------+-------+
| 8c981cdb-c19f-47c1-8149-f85a506c486c | router1 | {"network_id": "640ece56-c6dc-4868-8e7a-12547508098a", "enable_snat": true, "external_fixed_ips": [{"subnet_id": "75ae4ce8-495d-4f53-93d1-bf98e55d6658", "ip_address": "172.24.4.2"}]} | False       | False |
| ac41aab2-f9c3-4a06-8eef-f909ee1e6e50 | router  | {"network_id": "640ece56-c6dc-4868-8e7a-12547508098a", "enable_snat": true, "external_fixed_ips": [{"subnet_id": "75ae4ce8-495d-4f53-93d1-bf98e55d6658", "ip_address": "172.24.4.3"}]} | False       | False |
+--------------------------------------+---------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+-------------+-------+
'''


def neutron_router_list_parser(parse_this):
    routers = {}

    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or \
                re.search('external_gateway_info', line):
            continue

        parts = line.split('|')
        parts = [x.strip() for x in parts]

        router_id = parts[1]
        name = parts[2]

        network_id = 'unknown'
        m = re.search('"network_id":\s+"(\S+)"', parts[3])
        if m:
            network_id = m.group(1)

        ip_address = 'x.x.x.x'
        m = re.search('"ip_address":\s+"(\d+\.\d+\.\d+\.\d+)"', parts[3])
        if m:
            ip_address = m.group(1)

        routers[name] = {'id': router_id,
                         'ip_address': ip_address,
                         'network_id': network_id,
                         }

    info['routers'] = routers

    # now add some more commands to get further information for
    # l3-agents which run in different namespaces
    for router in info['routers'].keys():
        uuid = info['routers'][router]['id']
        namespace = 'qrouter-' + uuid

        cmd_key = 'netns_' + namespace
        cmd = {
            'cmd': 'echo namespace: ' + namespace + '; echo "sudo ip netns exec ' + namespace + ' ip a" > /tmp/don.bash; bash /tmp/don.bash',
            'help': 'Collect namespace info for l3-agent',
            'shell': True,
            'output': None,
            'order': 100,
            'parser': ip_namespace_qrouter_parser,
        }
        add_new_command(commands, cmd_key, cmd)
    pass


def ip_namespace_qrouter_parser(parse_this):
    nm_dict = info['namespaces']

    qr_intf = None
    qg_intf = None
    ip = None
    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line):
            continue
        m = re.search('^namespace: (\S+)', line)
        if m:
            namespace = m.group(1)
            continue

        m = re.search('^\d+: (qr-\S+):', line)
        if m:
            qr_intf = m.group(1)
            continue

        m = re.search('^\d+: (qg-\S+):', line)
        if m:
            qg_intf = m.group(1)
            continue

        m = re.search('inet (\d+\.\d+\.\d+\.\d+/\d+)', line)
        if m:
            ip = m.group(1)

            if not nm_dict[namespace].has_key('interfaces'):
                nm_dict[namespace] = {'interfaces': {}}

            if qg_intf:
                nm_dict[namespace]['interfaces'][qg_intf] = ip
            elif qr_intf:
                nm_dict[namespace]['interfaces'][qr_intf] = ip
            else:
                continue

            qr_intf = None
            qg_intf = None
            ip = None
    pass


def ip_namespace_qdhcp_parser(parse_this):
    nm_dict = info['namespaces']

    tap_intf = None
    ip = None
    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line):
            continue
        m = re.search('^namespace: (\S+)', line)
        if m:
            namespace = m.group(1)
            continue

        m = re.search('^\d+: (tap\S+):', line)
        if m:
            tap_intf = m.group(1)

        m = re.search('inet (\d+\.\d+\.\d+\.\d+/\d+)', line)
        if m:
            ip = m.group(1)

            if not nm_dict[namespace].has_key('interfaces'):
                nm_dict[namespace] = {'interfaces': {}}

            if tap_intf:
                nm_dict[namespace]['interfaces'][tap_intf] = ip

            tap_intf = None
            ip = None
    pass


'''
+--------------------------------------+----------+----------------------------------------------------------+
| id                                   | name     | subnets                                                  |
+--------------------------------------+----------+----------------------------------------------------------+
| 0a355cf0-00d0-45e1-9a3a-9aca436510d5 | private2 | 8393a2da-09dd-46e8-a26f-caf9f12c48f5 10.0.3.0/24         |
| 3b4ddfcb-49b8-46ae-9ecd-cb4f9b1830fc | public   | 2dd78cb6-eb90-44ea-82b0-bbdb7316edb2 172.24.4.0/24       |
|                                      |          | 304ce342-18fe-4b4a-aa49-f5c7e5e31b2a 2001:db8::/64       |
| 4b7a42e8-cc16-411c-b932-989106c2f934 | private1 | cc580da4-0b61-4982-ae7b-d2d5c441b1d7 10.0.2.0/24         |
| bfedebe8-c436-4056-8d12-1d2f7e62e8ec | private  | 4deed2ad-e184-43a9-8cc7-4493aa07f78f fdfd:57f1:b2ba::/64 |
|                                      |          | 8e2c5cfd-fbc1-4fe0-9f5e-f0b0dc070fb8 10.0.0.0/24         |
+--------------------------------------+----------+----------------------------------------------------------+
'''


def neutron_net_list_parser(parse_this):
    networks = {}

    ip = 'unknown'
    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or re.search('subnets', line):
            continue

        # Skip IPv6 for the time being
        m = re.search('^\| (\S+) \| (\S+)\s+\| \S+ (\S+)', line)
        if m:
            network_id = m.group(1)
            name = m.group(2)
            possible_ip = m.group(3)
            if re.search('\.', possible_ip):
                ip = possible_ip
                networks[network_id] = {'name': name,
                                        'ip': ip
                                        }
        m = re.search('^\|\s+\|\s+\| \S+ (\S+)', line)
        if m:
            possible_ip = m.group(1)
            if re.search('\.', possible_ip):
                ip = possible_ip
                networks[network_id] = {'name': name,
                                        'ip': ip
                                        }
        ip = 'Unknown'

    info['networks'] = networks

    # now add some more commands to get further information for
    # dhcp agents which run in different namespaces
    for network_id in networks.keys():
        # There is no dhcp agent run for public network
        if networks[network_id]['name'] == 'public':
            continue

        namespace = 'qdhcp-' + network_id

        cmd_key = 'netns_' + namespace
        cmd = {
            'cmd': 'echo namespace: ' + namespace + '; echo "sudo ip netns exec ' + namespace + ' ip a" > /tmp/don.bash; bash /tmp/don.bash',
            'help': 'Collect namespace info for dhcp-agent',
            'shell': True,
            'output': None,
            'order': 110,
            'parser': ip_namespace_qdhcp_parser,
        }
        add_new_command(commands, cmd_key, cmd)
    pass


'''
qdhcp-d5357ad8-df8b-4f19-8433-9db13304e4b2
qrouter-ac41aab2-f9c3-4a06-8eef-f909ee1e6e50
qdhcp-49be53de-33ed-480a-a06e-6e77c8f887dc
qrouter-8c981cdb-c19f-47c1-8149-f85a506c486c
qdhcp-82b0e328-4530-495e-a43f-238ef7a53d62
'''


def ip_netns_parser(parse_this):
    namespaces = {}

    for line in parse_this:
        if re.search('^q', line):
            namespaces[line] = {}

    info['namespaces'] = namespaces


def dummy_parser(parse_this):
    common.debug('Dummy Parser :-)')
    pass


def floating_ip_list_parser(parse_this):
    floating_ips = {}
    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or re.search('Pool', line):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts]
        floating_ip = parts[2]
        vm_id = parts[3]
        pool = parts[5]
        # ignore floating ips which is not assigned to any vms
        if vm_id != '-':
            floating_ips.update(
                {vm_id: {'floating_ip': floating_ip, 'pool': pool}})
    info['floating_ips'] = floating_ips


# static commands whose output have info that help us diagnose
commands = {
    'nova_list':
    {
        'cmd': ['nova', 'list'],
        'help': 'Collect list of VMs from nova',
                'env': True,
                'output': None,
                'order': 1,
                'parser': nova_list_parser,
    },
        'cat_instance':
            {
                'cmd': 'cat /etc/libvirt/qemu/instance-*.xml | egrep -e "<uuid>" -e "nova:name" -e "source bridge"',
                'help': 'Collect some info from the launched VMs',
                'sudo': True,
                'shell': True,
                'output': None,
                'order': 2,
                'parser': cat_instance_parser,
    },
        'neutron_port_list':
            {
                'cmd': ['neutron', 'port-list'],
                'help': 'Collect neutron configured ports',
                'env': True,
                'output': None,
                'order': 3,
                'parser': neutron_port_list_parser,
    },
        'neutron_router_list':
            {
                'cmd': ['neutron', 'router-list'],
                'help': 'Collect neutron configured routers',
                'env': True,
                'output': None,
                'order': 4,
                'parser': neutron_router_list_parser,
    },
        'neutron_net_list':
            {
                'cmd': ['neutron', 'net-list'],
                'help': 'Collect neutron configured networks',
                'env': True,
                'output': None,
                'order': 5,
                'parser': neutron_net_list_parser,
    },
        'ip_netns':
            {
                'cmd': ['ip', 'netns'],
                'help': 'Collect network namespaces',
                'output': None,
                'order': 6,
                'parser': ip_netns_parser,
    },

        'brctl_show':
            {
                'cmd': ['brctl', 'show'],
                'help': 'Collect information about bridges (linuxbridge) configured',
                'output': None,
                'order': 10,
                'parser': brctl_show_parser,
    },
        'ovs_appctl_fdb_show_br_ex':
            {
                'cmd': ['ovs-appctl', 'fdb/show', 'br-ex'],
                'help': 'Collect mac data base for bridge br-ex',
                'sudo': True,
                'output': None,
                'order': 20,
                'parser': None,
    },
        'ovs_appctl_fdb_show_br_int':
            {
                'cmd': ['ovs-appctl', 'fdb/show', 'br-int'],
                'help': 'Collect mac data base for ovs bridge br-int',
                'sudo': True,
                'output': None,
                'order': 21,
                'parser': None,
    },
        'ovs_appctl_fdb_show_br_tun':
            {
                'cmd': ['ovs-appctl', 'fdb/show', 'br-tun'],
                'help': 'Collect mac data base for ovs bridge br-tun',
                'sudo': True,
                'output': None,
                'order': 22,
                'parser': None,
    },
        'ovs_vsctl_show':
            {
                'cmd': ['ovs-vsctl', 'show'],
                'help': 'Collect ovs bridge info',
                'sudo': True,
                'output': None,
                'order': 30,
                'parser': ovs_vsctl_show_parser,
    },
        'ovs_ofctl_show_br_ex':
            {
                'cmd': ['ovs-ofctl', 'show', 'br-ex'],
                'help': 'Collect openflow information for ovs bridge br-ex',
                'sudo': True,
                'output': None,
                'order': 40,
                'parser': ovs_ofctl_show_br_ex_parser,
    },
        'ovs_ofctl_show_br_int':
            {
                'cmd': ['ovs-ofctl', 'show', 'br-int'],
                'help': 'Collect openflow information for ovs bridge br-int',
                'sudo': True,
                'output': None,
                'order': 41,
                'parser': ovs_ofctl_show_br_int_parser,
    },
        'ovs_ofctl_show_br_tun':
            {
                'cmd': ['ovs-ofctl', 'show', 'br-tun'],
                'help': 'Collect openflow information for ovs bridge br-tun',
                'sudo': True,
                'output': None,
                'order': 42,
                'parser': ovs_ofctl_show_br_tun_parser,
    },
        'ovs_ofctl_dump_flows_br_ex':
            {
                'cmd': ['ovs-ofctl', 'dump-flows', 'br-ex'],
                'help': 'Collect openflow flow table information for ovs bridge br-ex',
                'sudo': True,
                'output': None,
                'order': 50,
                'parser': None,
    },
        'ovs_ofctl_dump_flows_br_int':
            {
                'cmd': ['ovs-ofctl', 'dump-flows', 'br-int'],
                'help': 'Collect openflow flow table information for ovs bridge br-int',
                'sudo': True,
                'output': None,
                'order': 51,
                'parser': None,
    },
        'ovs_ofctl_dump_flows_br_tun':
            {
                'cmd': ['ovs-ofctl', 'dump-flows', 'br-tun'],
                'help': 'Collect openflow flow table information for ovs bridge br-tun',
                'sudo': True,
                'output': None,
                'order': 52,
                'parser': None,
    },
        'instance_floating_ip_list':
            {
                'cmd': ['nova', 'floating-ip-list'],
                'help': 'Collect floating ip information for instances',
                'env': True,
                'output': None,
                'order': 53,
                'parser': floating_ip_list_parser,
    },

}


def check_args():
    parser = argparse.ArgumentParser(description='Runs commands, collects, and parses output',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug', help='Enable debugging',
                        default=True, action='store_true')
    parser.add_argument('--info_file', dest='info_file',
                        help='Info will be stored in JSON format in this file',
                        default="don.json", type=str)
    args = parser.parse_args()

    common.settings['debug'] = args.debug
    common.settings['info_file'] = args.info_file


def all_commands_executed(commands):
    for cmd in commands.keys():
        if commands[cmd]['parser']:
            done = commands[cmd].get('done', False)
            if done is False:
                return False
    return True


def get_vm_info_from_compute(cmd):
    output = common.execute_cmd(['nova', 'hypervisor-list'],
                                sudo=False, shell=False, env=myenv).split('\n')
    compute_list = get_hypervisor(output)
    vm_info = []
    compute_creds = common.get_vm_credentials()
    for node in compute_list:
        creds = compute_creds.get('hypervisor').get(
            node, compute_creds.get('hypervisor')['default'])
        ssh = common.connect_to_box(node, creds['username'], creds['password'])
        (stdin, out, err) = ssh.exec_command('sudo ' + cmd)
        vm_info.extend(out.read().splitlines())
        ssh.close()
    return vm_info


def exec_on_remote(cmd):
    node_details = common.get_vm_credentials()
    creds = node_details.get('network')
    # print "sudo "+cmd
    ssh = common.connect_to_box(creds['hostname'], creds[
        'username'], creds['password'])
    (stdin, out, err) = ssh.exec_command(cmd)
    if len(err.read()):
        return []
    return out.read().splitlines()


def get_hypervisor(parse_this):
    hypervisor = []
    for line in parse_this:
        if re.search('^\+', line) or re.search('^$', line) or re.search('Hypervisor hostname', line):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts]
        name = parts[2]
        hypervisor.append(name)
    return hypervisor


def main():
    check_args()

    iteration = 0
    # Parser of any specific command might add more commands to be executed.
    # Hence continue in a loop.
    while True:
        if (all_commands_executed(commands) or iteration >= 10):
            break
        iteration += 1
        common.status_update('Iteration: ' + str(iteration))

        sorted_keys = sorted(commands.items(), key=lambda (k, v): v['order'])
        for (cmd, dontcare) in sorted_keys:
            # Only collect stuff for which we have written a parser
            if commands[cmd]['parser']:
                if commands[cmd].get('done', False):
                    continue
                if commands[cmd].has_key('help'):
                    common.status_update(commands[cmd]['help'])
                shell = commands[cmd].get('shell', False)
                env = None
                if commands[cmd].get('env', False):
                    env = myenv
                sudo = commands[cmd].get('sudo', False)
                if deployment_type == 'multinode':
                    # handling for network node
                    if cmd.startswith('netns_'):
                        commands[cmd]['output'] = exec_on_remote(
                            commands[cmd]['cmd'])
                    if cmd == 'cat_instance':
                        commands[cmd][
                            'output'] = get_vm_info_from_compute(
                                commands[cmd]['cmd'])
                        print(commands[cmd]['output'])
                    else:
                        commands[cmd]['output'] = common.execute_cmd(
                            commands[cmd]['cmd'], sudo=sudo,
                            shell=shell, env=env).split('\n')
                else:
                    commands[cmd]['output'] = common.execute_cmd(
                        commands[cmd]['cmd'],
                        sudo=sudo, shell=shell, env=env).split('\n')
                commands[cmd]['parser'](commands[cmd]['output'])
                commands[cmd]['done'] = True

    common.debug('============= COMMANDS =============')
    common.status_update(
        'Writing collected info into ' + common.settings['info_file'])
    common.dump_json(info, common.settings['info_file'])

if __name__ == "__main__":
    main()
