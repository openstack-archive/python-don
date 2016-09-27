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

# run_nms_cmd.py: This needs to be run from inside appropriate namespace
# sudo ip netns exec qrouter-ac41aab2-f9c3-4a06-8eef-f909ee1e6e50 python # run_nms_cmd.py "command"
import argparse
import json

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


def run_nms_cmd(args):
    global output_dict
    host_ip = args['host_ip']
    username = args['username']
    passwd = args['passwd']
    cmd_to_run = args['cmd']

    result = True
    cmd_dict = {}
    try:
        ssh = connect_to_box(host_ip, username, passwd)
        cmd_dict['cmd'] = 'ssh %s with provided username and passwd' % host_ip
        if not ssh:
            cmd_dict['output'] = 'Could not ssh to ' + host_ip
            cmd_dict['pass'] = False
            output_dict['command_list'].append(cmd_dict)
            return False
        else:
            cmd_dict['pass'] = True
        output_dict['command_list'].append(cmd_dict)
        cmd_dict = {}
        cmd = cmd_to_run
        output = ssh_cmd(ssh, cmd).split('\n')
        cmd_dict['cmd'] = cmd
        cmd_dict['output'] = output
    except (KeyboardInterrupt, SystemExit):
        print('\nkeyboardinterrupt caught (again)')
        print('\n...Program Stopped Manually!')
        result = False
        raise
    cmd_dict['pass'] = result
    output_dict['command_list'].append(cmd_dict)
    return result


def check_args():
    global params

    parser = argparse.ArgumentParser(
        description='Run command from inside nms',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging',
                        default=False, action='store_true')
    parser.add_argument('--host_ip', dest='host_ip',
                        help='IP where the command will be run',
                        type=str, required=True)
    parser.add_argument('--username', dest='username',
                        help='SSH login username (required)',
                        type=str, required=True)
    parser.add_argument('--passwd', dest='passwd',
                        help='SSH login passwd (required)',
                        type=str, required=True)
    parser.add_argument('--cmd', dest='cmd',
                        help='cmd to be run',
                        type=str, required=True)
    args = parser.parse_args()

    settings['debug'] = args.debug
    params['host_ip'] = args.host_ip
    params['username'] = args.username
    params['passwd'] = args.passwd
    params['cmd'] = args.cmd


def main():
    global output_dict

    check_args()

    output_dict['pass'] = run_nms_cmd(params)

    print(json.dumps(output_dict, sort_keys=True, indent=4))

if __name__ == "__main__":
    main()
