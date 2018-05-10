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

# ping.py: Runs a ping test from src_ip to dst_ip. Also provides analysis if
# things are not okay (TBD).
#
# HOWTO:
#
# For OpenStack, this program must be run from inside the correct namespace
# sudo ip netns exec qrouter-ac41aab2-f9c3-4a06-8eef-f909ee1e6e50 python ping.py 10.0.3.3 10.0.2.4 cirros "gocubsgo"

import argparse
import json
import re

from openstack_dashboard.don.ovs.common import connect_to_box
from openstack_dashboard.don.ovs.common import settings
from openstack_dashboard.don.ovs.common import ssh_cmd

params = {}

output_dict = {
    'comment': None,
    'pass': None,
    'command_list': [],
    'errors': [],
}


def ping_test(src_ip, dst_ip, username, passwd, count, timeout):
    global output_dict
    result = False
    cmd_dict = {}
    try:
        ssh = connect_to_box(src_ip, username, passwd)
        cmd_dict['cmd'] = 'ssh %s with provided username and passwd' % src_ip
        if not ssh:
            cmd_dict['output'] = 'Could not ssh to ' + src_ip
            cmd_dict['pass'] = False
            output_dict['command_list'].append(cmd_dict)
            return False
        else:
            cmd_dict['pass'] = True
        output_dict['command_list'].append(cmd_dict)
        cmd_dict = {}
        cmd = 'ping -c %s -W %s %s' % (count, timeout, dst_ip)
        output = ssh_cmd(ssh, cmd).split('\n')
        cmd_dict['cmd'] = cmd
        cmd_dict['output'] = output
        for line in output:
            m = re.search('(\d+) packets transmitted, (\d+) packets received', line) or \
                re.search('(\d+) packets transmitted, (\d+) received',
                          line)  # also handles cirros vm ping response
            if m:
                tx_pkts = float(m.group(1))
                rx_pkts = float(m.group(2))
                if rx_pkts / tx_pkts >= 0.75:
                    result = True
                break
    except (KeyboardInterrupt, SystemExit):
        print('\nkeyboardinterrupt caught (again)')
        print('\n...Program Stopped Manually!')
        raise
    cmd_dict['pass'] = result
    output_dict['command_list'].append(cmd_dict)
    return result


def check_args():
    global params

    parser = argparse.ArgumentParser(
        description='Ping test',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging',
                        default=False, action='store_true')
    parser.add_argument('--src_ip', dest='src_ip',
                        help='IP from where ping will be run (required)',
                        type=str, required=True)
    parser.add_argument('--dst_ip', dest='dst_ip',
                        help='IP to which ping will be run (required)',
                        type=str, required=True)
    parser.add_argument('--username', dest='username',
                        help='SSH login username (required)', type=str,
                        required=True)
    parser.add_argument('--passwd', dest='passwd',
                        help='SSH login passwd (required)',
                        type=str, required=True)
    parser.add_argument('--count', dest='count',
                        help='ping count', type=str, default='2')
    parser.add_argument('--timeout', dest='timeout',
                        help='ping timeout (-W option of ping) in seconds',
                        type=str, default='4')
    args = parser.parse_args()

    settings['debug'] = args.debug
    params['src_ip'] = args.src_ip
    params['dst_ip'] = args.dst_ip
    params['username'] = args.username
    params['passwd'] = args.passwd
    params['count'] = args.count
    params['timeout'] = args.timeout


def main():
    global output_dict

    check_args()

    src_ip = params['src_ip']
    dst_ip = params['dst_ip']
    ping_success = ping_test(src_ip, dst_ip,
                             params['username'], params['passwd'],
                             params['count'], params['timeout'])

    output_dict['comment'] = 'PING %s to %s' % (src_ip, dst_ip)
    output_dict['pass'] = ping_success

    print(json.dumps(output_dict, sort_keys=True, indent=4))

if __name__ == "__main__":
    main()
