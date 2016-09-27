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
import pprint
import random
import re
import subprocess
import sys

from common import debug
from common import get_intf_ip
from common import get_ip_network
from common import get_subnet
from common import get_vlan_tag
from common import load_json
from common import settings
from common import warning


class DotGenerator(object):
    """Generates an SVG file showing the network internals of

       a compute node.
    """

    def __init__(self, in_json_filename,
                 compute_dot_file, compute_svg_file,
                 network_dot_file, network_svg_file,
                 combined_dot_file, combined_svg_file,
                 highlight_file):
        self.json_filename = in_json_filename

        self.compute_dot_file = compute_dot_file
        self.compute_svg_file = compute_svg_file
        self.network_dot_file = network_dot_file
        self.network_svg_file = network_svg_file
        self.combined_dot_file = combined_dot_file
        self.combined_svg_file = combined_svg_file
        self.highlight_file = highlight_file

        settings['debug'] = True

        self.highlight_info = None
        if highlight_file:
            self.highlight_info = load_json(self.highlight_file)
            if not self.highlight_info.get('net_info'):
                self.highlight_info['net_info'] = {'pass': [],
                                                   'fail': []
                                                   }

        self.info = load_json(self.json_filename)
        self.outfile = None

        self.colors = {
            'vms': '#ff9933',
            'tap': '#99ffff',
            'qbr': '#9966ff',
            'br-int': '#ff6666',
            'br-tun': '#ff6666',
            'qvb': '#ffcc00',
            'qvo': '#ffcc00',
            'tun': '#ffcc00',
            'int': '#ffcc00',
            'routers': '#ff9933',
            'vlan': [],
            'error': '#f00000',
            'edge': '#0066cc',
            'dontcare': '#909090',
            'pass': '#b2f379',
            'fail': '#f00000',
            'edge_pass': '#009900',
            'floating_ip': '#b3ffb3',
        }
        self.__set_vlan_color_table()
        pprint.pprint(self.info)

    def __port_pass(self, port):
        if self.highlight_file:
            if port.replace('.', '') == self.highlight_info['src_info']['ip'].replace('.', '') or \
               port.replace('.', '') == self.highlight_info['dst_info']['ip'].replace('.', ''):
                return self.highlight_info['ping_pass']
            if self.highlight_info['src_info'].has_key('pass') and port in self.highlight_info['src_info']['pass'] or \
               self.highlight_info['dst_info'].has_key('pass') and port in self.highlight_info['dst_info']['pass'] or \
               self.highlight_info['net_info'].has_key('pass') and port in self.highlight_info['net_info']['pass']:
                return True
        return False

    def __port_fail(self, port):
        if self.highlight_file:
            if port.replace('.', '') == self.highlight_info['src_info']['ip'].replace('.', '') or \
               port.replace('.', '') == self.highlight_info['dst_info']['ip'].replace('.', ''):
                return not self.highlight_info['ping_pass']
            if self.highlight_info['src_info'].has_key('fail') and port in self.highlight_info['src_info']['fail'] or \
               self.highlight_info['dst_info'].has_key('fail') and port in self.highlight_info['dst_info']['fail'] or \
               self.highlight_info['net_info'].has_key('fail') and port in self.highlight_info['net_info']['fail']:
                return True
        return False

    def __get_edge_color(self, src_tag, dst_tag):
        if not self.highlight_file:
            return self.__get_color('edge')

        sport = src_tag
        dport = dst_tag
        m = re.search('\S+:(\S+)', src_tag)
        if m:
            sport = m.group(1)

        m = re.search('\S+:(\S+)', dst_tag)
        if m:
            dport = m.group(1)

        spass = self.__port_pass(sport)
        dpass = self.__port_pass(dport)

        sfail = self.__port_fail(sport)
        dfail = self.__port_fail(dport)

        debug('%s (p%d f%d) -> %s (p%d f%d)' % (sport, spass, sfail, dport,
                                                dpass, dfail))

        if spass or dpass:
            return self.colors['edge_pass']
        if sfail and dfail:
            return self.colors['fail']

        return self.colors['dontcare']

    def __get_color(self, tag):
        if self.highlight_file:
            return self.colors['dontcare']
        else:
            return self.colors[tag]

    def __hsv_to_rgb(self, h, s, v):
        h_i = int((h * 6))
        f = h * 6 - h_i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        if h_i == 0:
            r, g, b = v, t, p
        if h_i == 1:
            r, g, b = q, v, p
        if h_i == 2:
            r, g, b = p, v, t
        if h_i == 3:
            r, g, b = p, q, v
        if h_i == 4:
            r, g, b = t, p, v
        if h_i == 5:
            r, g, b = v, p, q

        return [r * 256, g * 256, b * 256]

    def __set_vlan_color_table(self):
        i = 20
        random.seed(1)
        while i > 0:
            colors = self.__hsv_to_rgb(random.random(), 0.5, 0.95)
            colors = [hex(int(x)).split('x')[1] for x in colors]
            colors = ''.join(x for x in colors)
            self.colors['vlan'].append('#' + colors)
            i -= 1
        debug(pprint.pformat(self.colors['vlan']))

    # port becomes relevant only if highlight_file is specified.
    def __get_vlan_color(self, tag, port='dummy'):
        if self.highlight_file:
            if self.__port_pass(port):
                return self.colors['pass']
            elif self.__port_fail(port):
                return self.colors['fail']
            else:
                return self.colors['dontcare']
        else:
            total_colors = len(self.colors['vlan'])
            return self.colors['vlan'][int(tag) % total_colors]

    def __get_total_vm_port_count(self):
        port_count = 0
        for vm in self.info['vms'].keys():
            port_count += len(self.info['vms'][vm]['src_bridge'])
        return port_count

    # TODO XXX needs some work to handle different subnet mask length. LPM needs
    # to be implemented!
    def __get_network_id(self, ip):
        networks = self.info['networks']
        subnet = get_subnet(ip)

        for net in networks.keys():
            if re.search(subnet, networks[net]['ip']):
                return net
        return None

    def __get_network_name(self, ip):
        network_id = self.__get_network_id(ip)
        return self.info['networks'][network_id]['name']

    def __get_tap_interface(self, namespace, qr_intf):
        namespaces = self.info['namespaces']
        ip = namespaces[namespace]['interfaces'][qr_intf]
        network_id = self.__get_network_id(ip)
        if not network_id:
            return 'No TAP! 1'
        qdhcp = 'qdhcp-' + network_id
        if not namespaces.has_key(qdhcp):
            return 'No TAP! 2'
        for intf in namespaces[qdhcp]['interfaces'].keys():
            return (qdhcp, intf)
        pass

    def __get_router_port_count(self, router, port_type='qr'):
        port_count = 0
        router_id = self.info['routers'][router]['id']
        qrouter = 'qrouter-' + router_id

        namespaces = self.info['namespaces']
        for nms in namespaces.keys():
            if re.search('^' + qrouter, nms):
                for intf in namespaces[nms]['interfaces'].keys():
                    if re.search('^' + port_type, intf):
                        port_count += 1
        return port_count

    def __get_total_port_count(self, port_type='qr'):
        port_count = 0
        for router in self.info['routers'].keys():
            port_count += self.__get_router_port_count(router, port_type)

        return port_count

    def __get_total_dhcp_port_count(self):
        port_count = 0
        namespaces = self.info['namespaces']

        for nms in namespaces.keys():
            if re.search('^qdhcp-', nms):
                for intf in namespaces[nms]['interfaces'].keys():
                    if re.search('^tap', intf):
                        port_count += 1
        return port_count

    def __html_row_open(self):
        print('<TR>')

    def __html_row_close(self):
        print('</TR>')

    def __html_row(self, name, rspan, cspan, color, tag=None):
        # tags do not allow "-" (dash) in DOT language. Convert to "_"
        # (underscore)
        if tag:
            print('<TD ROWSPAN="%d" COLSPAN="%d" BGCOLOR="%s" PORT="%s">%s</TD>' % (rspan, cspan, color, tag.replace('-', '_'), name))
        else:
            print('<TD ROWSPAN="%d" COLSPAN="%d" BGCOLOR="%s">%s</TD>' % (rspan, cspan, color, name))
        pass

    def __html_edge(selft, src_tag, dst_tag, color, penwidth="4", style=None):
        src_tag = src_tag.replace('-', '_')
        dst_tag = dst_tag.replace('-', '_')
        if not style:
            print('%s:s -> %s:n [color = "%s", penwidth = "%s"]' % (src_tag,
                                                                    dst_tag,
                                                                    color,
                                                                    penwidth))
        else:
            print('%s:s -> %s:n [color = "%s", penwidth = "%s", style="%s"]' % (src_tag,
                                                                                dst_tag,
                                                                                color,
                                                                                penwidth,
                                                                                style))

    def __digraph_open(self, tag):
        msg = 'digraph DON_' + tag + ' {' + \
            '''
graph [fontsize=10 fontname="Helvetica"];
node [fontsize=10 fontname="Helvetica"];
rankdir = TB;
ranksep = 1;
concentrate = true;
compound = true;
edge [dir=none]
'''
        print(msg)

    def __digraph_close(self):
        msg = '\n}\n'
        print(msg)

    def __cluster_name(self, tag, col_span, color="white"):
        self.__html_row_open()
        port = tag.replace(' ', '').replace('-', '_')
        print('<TD COLSPAN="%d" BORDER="0" BGCOLOR="%s" PORT="%s">%s</TD>' % (col_span, color, port, tag))
        self.__html_row_close()

    def __cluster_open_plain(self, tag, label=None):
        print('subgraph cluster_%s {' % (tag))
        print('style=filled')
        if label:
            print('label="%s"' % (label))

    def __cluster_close_plain(self):
        print('}\n')

    def __cluster_open(self, tag, color="white"):
        print('subgraph cluster_%s {' % (tag))
        print('%s [ shape = plaintext, label = <' % (tag))
        print('<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="5" CELLPADDING="5" BGCOLOR="%s">' % (color))
        pass

    def __cluster_close(self):
        print('</TABLE>>];\n')
        print('}\n')
        pass

    def __plot_title_edges(self, tag):
        if tag == 'compute':
            src_tag = 'ComputeNode'
            dst_tag = 'VMs'
        else:
            src_tag = 'NetworkNode'
            dst_tag = 'br_ex'
        self.__html_edge(src_tag, dst_tag,
                         self.__get_color('edge'), style="invis")

    def __plot_vms(self):
        col_span = self.__get_total_vm_port_count()
        row_span = 1
        self.__cluster_open('VMs')
        self.__cluster_name('VMs', col_span)

        # Plot each VM at a time
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            col_span = len(self.info['vms'][vm]['src_bridge'])
            if self.info['floating_ips'].get(self.info['vms'][vm]['uuid']):
                col_span = col_span + 1
            self.__html_row(vm, row_span, col_span, self.__get_color('vms'))
        self.__html_row_close()

        # Plot the networks for each port
        self.__html_row_open()
        col_span = 1
        for vm in sorted(self.info['vms'].keys()):
            floating_ip_info = self.info['floating_ips'].get(
                self.info['vms'][vm]['uuid'])
            if floating_ip_info:
                network = floating_ip_info.get('pool')
                self.__html_row('Floating -' + network, row_span,
                                col_span, self.colors['floating_ip'])
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                tag = get_vlan_tag(self.info, bridge)
                ip = get_intf_ip(self.info, bridge)
                network = get_ip_network(self.info, vm, ip)
                color = self.__get_vlan_color(tag)
                if re.search('unknown', network):
                    color = self.__get_color('error')
                self.__html_row(network, row_span, col_span, color)
        self.__html_row_close()

        # Plot the IPs for each port
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            floating_ip_info = self.info['floating_ips'].get(
                self.info['vms'][vm]['uuid'])
            if floating_ip_info:
                ip = floating_ip_info.get('floating_ip')
                self.__html_row(ip, row_span, col_span, self.colors[
                                'floating_ip'], ip.replace('.', ''))
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                tag = get_vlan_tag(self.info, bridge)
                ip = get_intf_ip(self.info, bridge)
                color = self.__get_vlan_color(tag, ip)
                if re.search('x.x.x.x', ip):
                    color = self.__get_color('error')
                self.__html_row(ip, row_span, col_span,
                                color, ip.replace('.', ''))
        self.__html_row_close()

        self.__cluster_close()
        pass

    def __plot_linux_bridge(self):
        row_span = 1
        col_span = self.__get_total_vm_port_count()
        self.__cluster_open('LinuxBridge')
        self.__cluster_name('Linux Bridge', col_span)

        # There must be one linuxbridge entity per VM port.
        col_span = 1
        # First, the tap devices
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                if self.info['brctl'].has_key(bridge):
                    for dev in self.info['brctl'][bridge]['interfaces']:
                        if re.search('^tap', dev):
                            tag = get_vlan_tag(self.info, bridge)
                            self.__html_row(dev, row_span, col_span,
                                            self.__get_vlan_color(tag, dev), dev)
                            break
        self.__html_row_close()

        # Second, the linuxbridges
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                if self.info['brctl'].has_key(bridge):
                    tag = get_vlan_tag(self.info, bridge)
                    self.__html_row(bridge, row_span, col_span,
                                    self.__get_vlan_color(tag, bridge), bridge)
        self.__html_row_close()

        # Third, the qvb (one part of eth-pair) devices
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                if self.info['brctl'].has_key(bridge):
                    for dev in self.info['brctl'][bridge]['interfaces']:
                        if re.search('^qvb', dev):
                            tag = get_vlan_tag(self.info, bridge)
                            self.__html_row(dev, row_span, col_span,
                                            self.__get_vlan_color(tag, dev), dev)
                            break
        self.__html_row_close()
        self.__cluster_close()
        pass

    def __plot_br_int_compute(self):
        br_int = self.info['bridges']['br-int']
        row_span = 1
        col_span = self.__get_total_vm_port_count()

        self.__cluster_open('compute_br_int')
        self.__cluster_name('OVS br_int', col_span)

        # The qvo (pairs with qvb part in linuxbridge) devices
        col_span = 1
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                qvo_port = bridge.replace('qbr', 'qvo')
                if br_int['ports'].has_key(qvo_port):
                    port_id = '[' + br_int['ports'][qvo_port]['id'] + '] '
                    tag = br_int['ports'][qvo_port]['tag']
                    self.__html_row(port_id + qvo_port, row_span, col_span,
                                    self.__get_vlan_color(tag, qvo_port), qvo_port)
        self.__html_row_close()

        # The vlan tags for each of the devices
        col_span = 1
        self.__html_row_open()
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                qvo_port = bridge.replace('qbr', 'qvo')
                if br_int['ports'].has_key(qvo_port):
                    tag = br_int['ports'][qvo_port]['tag']
                    self.__html_row('VLAN tag:' + tag, row_span, col_span,
                                    self.__get_vlan_color(tag),
                                    qvo_port + 'tag_' + tag)
        self.__html_row_close()

        col_span = self.__get_total_vm_port_count()
        # Display the patch-tun port
        self.__html_row_open()
        tun_port = 'patch-tun'
        if br_int['ports'].has_key(tun_port):
            port_id = '[' + br_int['ports'][tun_port]['id'] + '] '
            self.__html_row(port_id + tun_port, row_span, col_span,
                            self.__get_color('tun'), tun_port)
        else:
            self.__html_row(tun_port, row_span, col_span,
                            self.__get_color('error'), tun_port)
        self.__html_row_close()

        self.__cluster_close()

    def __plot_br_ex_to_br_int(self):
        namespaces = self.info['namespaces']

        for nms in namespaces.keys():
            if not re.search('^qrouter-', nms):
                continue
            if not namespaces[nms].has_key('interfaces'):
                warning('namespace %s does not have any interface' % nms)
                continue
            qg_intf = None
            for intf in namespaces[nms]['interfaces'].keys():
                if re.search('^qg-', intf):
                    qg_intf = intf
                    break

            for intf in namespaces[nms]['interfaces'].keys():
                if re.search('^qr-', intf):
                    src_tag = 'br_ex:' + qg_intf
                    dst_tag = 'network_br_int:' + intf
                    self.__html_edge(src_tag, dst_tag,
                                     self.__get_color('edge'))

    def __plot_br_ex_network(self):
        routers = self.info['routers']
        namespaces = self.info['namespaces']
        br_ex = self.info['bridges']['br-ex']

        row_span = 1
        max_col_span = self.__get_total_port_count(port_type='qg')

        self.__cluster_open('br_ex')
        self.__cluster_name('OVS br_ex', max_col_span)

        # Display the router name associated with each qg port
        self.__html_row_open()
        for router in sorted(routers.keys()):
            col_span = self.__get_router_port_count(router, port_type='qg')
            self.__html_row(router, row_span, col_span,
                            self.__get_color('routers'), router)
        self.__html_row_close()

        # Display the ips for each qg port
        self.__html_row_open()
        for router in sorted(routers.keys()):
            col_span = self.__get_router_port_count(router, port_type='qg')
            qrouter = 'qrouter-' + routers[router]['id']
            for nms in namespaces.keys():
                if re.search('^' + qrouter, nms):
                    for intf in namespaces[nms]['interfaces'].keys():
                        if re.search('^qg-', intf):
                            ip = namespaces[nms]['interfaces'][intf]
                            self.__html_row(ip, row_span, col_span,
                                            self.__get_color('routers'), ip)
        self.__html_row_close()

        # For each router, print the qg- interfaces
        self.__html_row_open()
        for router in sorted(routers.keys()):
            col_span = self.__get_router_port_count(router, port_type='qg')
            qrouter = 'qrouter-' + routers[router]['id']
            for nms in namespaces.keys():
                if re.search('^' + qrouter, nms):
                    for intf in namespaces[nms]['interfaces'].keys():
                        if re.search('^qg-', intf):
                            port_id = '[' + br_ex['ports'][intf]['id'] + '] '
                            self.__html_row(port_id + intf, row_span, col_span,
                                            self.__get_color('routers'), intf)
        self.__html_row_close()

        self.__cluster_close()

    def __plot_br_int_network(self):
        routers = self.info['routers']
        namespaces = self.info['namespaces']
        br_int = self.info['bridges']['br-int']

        row_span = 1
        # max_col_span = self.__get_total_port_count(port_type='qr') + \
        #           self.__get_total_dhcp_port_count()
        max_col_span = self.__get_total_port_count(port_type='qr') * 2
        col_span = max_col_span

        self.__cluster_open('network_br_int')
        self.__cluster_name('OVS br_int', col_span)

        # For each router, print the qr- and tap (dhcp) interfaces
        temp_info = []
        col_span = 1
        self.__html_row_open()
        for router in sorted(routers.keys()):
            qrouter = 'qrouter-' + routers[router]['id']
            for nms in namespaces.keys():
                if re.search('^' + qrouter, nms):
                    for intf in namespaces[nms]['interfaces'].keys():
                        if re.search('^qr-', intf):
                            tag = br_int['ports'][intf]['tag']
                            port_id = '[' + br_int['ports'][intf]['id'] + '] '
                            color = self.__get_vlan_color(tag, intf)
                            self.__html_row(
                                port_id + intf, row_span,
                                col_span, color, intf)
                            # now plot the corresponding tap interface
                            (tap_nms, tap) = self.__get_tap_interface(nms,
                                                                      intf)
                            tag = br_int['ports'][tap]['tag']
                            color = self.__get_vlan_color(tag, tap)
                            port_id = '[' + br_int['ports'][tap]['id'] + '] '
                            self.__html_row(
                                port_id + tap, row_span, col_span, color, tap)

                            a = {
                                'qr_intf': intf,
                                'tap_intf': tap,
                                'qr_ip': namespaces[nms]['interfaces'][intf],
                                'tap_ip': namespaces[tap_nms]['interfaces'][tap],
                            }
                            temp_info.append(a)
        self.__html_row_close()

        # The vlan tags for each of the qr- and tap ports
        col_span = 1
        self.__html_row_open()
        for entry in temp_info:
            qr_intf = entry['qr_intf']
            tap_intf = entry['tap_intf']

            tag = br_int['ports'][qr_intf]['tag']
            self.__html_row('VLAN tag:' + tag, row_span, col_span,
                            self.__get_vlan_color(tag), qr_intf + 'tag_' + tag)

            tag = br_int['ports'][tap_intf]['tag']
            self.__html_row('VLAN tag:' + tag, row_span, col_span,
                            self.__get_vlan_color(tag),
                            tap_intf + 'tag_' + tag)

        self.__html_row_close()

        # Display the ips with each of the qr- and tap ports
        self.__html_row_open()
        for entry in temp_info:
            qr_intf = entry['qr_intf']
            qr_ip = entry['qr_ip']
            tap_intf = entry['tap_intf']
            tap_ip = entry['tap_ip']

            tag = br_int['ports'][qr_intf]['tag']
            self.__html_row(qr_ip, row_span, col_span,
                            self.__get_vlan_color(tag),
                            qr_intf + qr_ip)

            tag = br_int['ports'][tap_intf]['tag']
            self.__html_row(tap_ip, row_span, col_span,
                            self.__get_vlan_color(tag),
                            tap_intf + tap_ip)

        self.__html_row_close()

        # The network names (private1, private2, etc.)
        col_span = 2
        self.__html_row_open()
        for entry in temp_info:
            network_name = self.__get_network_name(entry['qr_ip'])
            tag = br_int['ports'][entry['qr_intf']]['tag']
            self.__html_row(network_name, row_span, col_span,
                            self.__get_vlan_color(tag), network_name)
        self.__html_row_close()

        # The routers in the system
        self.__html_row_open()
        for router in sorted(self.info['routers'].keys()):
            # For each qr port that is also a tap port (for dhcp)
            col_span = self.__get_router_port_count(router, port_type='qr') * 2
            self.__html_row(router, row_span, col_span,
                            self.__get_color('routers'), router)
        self.__html_row_close()

        # Display the patch-tun port
        self.__html_row_open()
        tun_port = 'patch-tun'
        debug('max_col_span 2: ' + str(max_col_span))
        if br_int['ports'].has_key(tun_port):
            port_id = '[' + br_int['ports'][tun_port]['id'] + '] '
            self.__html_row(port_id + tun_port, row_span, max_col_span,
                            self.__get_color('tun'), tun_port)
        else:
            self.__html_row(tun_port, row_span, max_col_span,
                            self.__get_color('error'), tun_port)
        self.__html_row_close()

        self.__cluster_close()

    def __plot_br_tun(self, tag):
        br_tun = self.info['bridges']['br-tun']
        row_span = 1
        col_span = self.__get_total_vm_port_count()
        self.__cluster_open(tag + '_br_tun')
        self.__cluster_name('OVS br_tun', col_span)

        # Display the patch-int port
        col_span = self.__get_total_vm_port_count()
        self.__html_row_open()
        int_port = 'patch-int'
        if br_tun['ports'].has_key(int_port):
            port_id = '[' + br_tun['ports'][int_port]['id'] + '] '
            self.__html_row(port_id + int_port, row_span,
                            col_span, self.__get_color('int'), int_port)
        else:
            self.__html_row(int_port, row_span, col_span,
                            self.__get_color('error'), int_port)
        self.__html_row_close()

        self.__cluster_close()

    def __plot_vms_to_linuxbridge(self):
        brctl = self.info['brctl']
        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                ip = get_intf_ip(self.info, bridge)
                if brctl.has_key(bridge):
                    for dev in brctl[bridge]['interfaces']:
                        if re.search('^tap', dev):
                            src_tag = 'VMs:' + ip.replace('.', '')
                            dst_tag = 'LinuxBridge:' + dev
                            color = self.__get_edge_color(src_tag, dst_tag)
                            self.__html_edge(src_tag, dst_tag, color)
                            break

    def __plot_linuxbridge_to_br_int(self):
        brctl = self.info['brctl']
        br_int = self.info['bridges']['br-int']

        for vm in sorted(self.info['vms'].keys()):
            for bridge in sorted(self.info['vms'][vm]['src_bridge']):
                if brctl.has_key(bridge):
                    for dev in brctl[bridge]['interfaces']:
                        if re.search('^qvb', dev):
                            qvo_port = bridge.replace('qbr', 'qvo')
                            if br_int['ports'].has_key(qvo_port):
                                src_tag = 'LinuxBridge:' + dev
                                dst_tag = 'compute_br_int:' + qvo_port
                                color = self.__get_edge_color(src_tag, dst_tag)
                                self.__html_edge(src_tag, dst_tag, color)
                            break

    def __plot_br_int_to_br_tun(self, tag):
        br_int = self.info['bridges']['br-int']['ports']
        br_tun = self.info['bridges']['br-tun']['ports']

        tun_port = 'patch-tun'
        int_port = 'patch-int'
        if br_int.has_key(tun_port) and br_tun.has_key(int_port):
            tun_peer = br_int[tun_port]['interfaces'][
                tun_port].get('options', None)
            int_peer = br_tun[int_port]['interfaces'][
                int_port].get('options', None)
            if tun_peer and int_peer:
                if re.search('peer=' + int_port, tun_peer) and \
                   re.search('peer=' + tun_port, int_peer):
                    src_tag = tag + '_br_int:' + tun_port
                    dst_tag = tag + '_br_tun:' + int_port
                    self.__html_edge(src_tag, dst_tag,
                                     self.__get_color('edge'))
                    return

    def plot_combined(self):
        self.outfile = open(self.combined_dot_file, 'w')
        sys.stdout = self.outfile

        tag = 'DON'
        self.__digraph_open(tag)

        self.__cluster_open_plain('DONComputeNode')
        self.plot_compute_node()
        self.__cluster_close_plain()

        self.__cluster_open_plain('DONNetworkNode')
        self.plot_network_node()
        self.__cluster_close_plain()

        self.__digraph_close()

        self.outfile.close()
        sys.stdout = sys.__stdout__

    def plot_compute_node(self):
        tag = 'compute'
        redirected = False
        if sys.stdout == sys.__stdout__:
            self.outfile = open(self.compute_dot_file, "w")
            sys.stdout = self.outfile
            redirected = True
            self.__digraph_open(tag)

        # Title
        self.__cluster_open('ComputeNode', 'red')
        self.__cluster_name('Compute Node', 1, 'yellow')
        self.__cluster_close()

        # Plot nodes
        self.__cluster_open_plain('Nova')
        self.__plot_vms()
        self.__plot_linux_bridge()
        self.__cluster_close_plain()

        self.__cluster_open_plain('OVS')
        self.__plot_br_int_compute()
        self.__plot_br_tun(tag)
        self.__cluster_close_plain()

        # Plot edges
        self.__plot_title_edges(tag)
        self.__plot_vms_to_linuxbridge()
        self.__plot_linuxbridge_to_br_int()
        self.__plot_br_int_to_br_tun(tag)

        if redirected:
            self.__digraph_close()
            self.outfile.close()
            sys.stdout = sys.__stdout__

    def generate_compute_svg(self):
        cmd = ['/usr/bin/dot', '-Tsvg', self.compute_dot_file,
               '-o', self.compute_svg_file]
        debug(pprint.pformat(cmd))
        subprocess.call(cmd)
        debug('Done generating compute SVG')

    def plot_network_node(self):
        tag = 'network'
        redirected = False
        if sys.stdout == sys.__stdout__:
            self.outfile = open(self.network_dot_file, "w")
            sys.stdout = self.outfile
            redirected = True
            self.__digraph_open(tag)

        self.__cluster_open('NetworkNode', 'red')
        self.__cluster_name('Network Node', 1, 'yellow')
        self.__cluster_close()

        # Plot nodes
        self.__cluster_open_plain('OVS')
        self.__plot_br_ex_network()
        self.__plot_br_int_network()
        self.__plot_br_tun(tag)
        self.__cluster_close_plain()

        # Plot edges
        self.__plot_title_edges(tag)
        self.__plot_br_int_to_br_tun(tag)
        self.__plot_br_ex_to_br_int()

        if redirected:
            self.__digraph_close()
            self.outfile.close()
            sys.stdout = sys.__stdout__

    def generate_network_svg(self):
        cmd = ['/usr/bin/dot', '-Tsvg', self.network_dot_file,
               '-o', self.network_svg_file]
        debug(pprint.pformat(cmd))
        subprocess.call(cmd)
        debug('Done generating network SVG')

    def generate_combined_svg(self):
        cmd = ['/usr/bin/dot', '-Tsvg', self.combined_dot_file,
               '-o', self.combined_svg_file]
        debug(pprint.pformat(cmd))
        subprocess.call(cmd)
        debug('Done generating network SVG')


def check_args():
    parser = argparse.ArgumentParser(
        description='Plot the compute node network internals',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging',
                        default=True, action='store_true')
    parser.add_argument('--info_file', dest='info_file',
                        help='Info is read  in JSON format in this file',
                        default="don.json", type=str)
    parser.add_argument('--compute_file', dest='compute_file',
                        help='[compute_file].dot and [compute_file].svg will be generated for compute node', default="compute", type=str)
    parser.add_argument('--network_file', dest='network_file',
                        help='[network_file].dot and [network_file].svg will be generated for network node', default="network", type=str)
    parser.add_argument('--combined_file', dest='combined_file',
                        help='[combined_file].dot and [combined_file].svg will be generated', default="don", type=str)
    parser.add_argument('--highlight_file', dest='highlight_file',
                        help='pass and fail node are specified in this file',
                        default=None, type=str)

    args = parser.parse_args()

    settings['debug'] = args.debug
    settings['info_file'] = args.info_file
    settings['compute_dot_file'] = args.compute_file + '.dot'
    settings['compute_svg_file'] = args.compute_file + '.svg'
    settings['network_dot_file'] = args.network_file + '.dot'
    settings['network_svg_file'] = args.network_file + '.svg'
    settings['combined_dot_file'] = args.combined_file + '.dot'
    settings['combined_svg_file'] = args.combined_file + '.svg'
    settings['highlight_file'] = args.highlight_file


def main():
    check_args()
    plotter = DotGenerator(settings['info_file'],
                           settings['compute_dot_file'],
                           settings['compute_svg_file'],
                           settings['network_dot_file'],
                           settings['network_svg_file'],
                           settings['combined_dot_file'],
                           settings['combined_svg_file'],
                           settings['highlight_file'],
                           )
    if not settings['highlight_file']:
        plotter.plot_compute_node()
        plotter.generate_compute_svg()

        plotter.plot_network_node()
        plotter.generate_network_svg()

    plotter.plot_combined()
    plotter.generate_combined_svg()

if __name__ == "__main__":
    main()
