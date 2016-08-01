#
# ovs.py: Runs ovs-appctl command to check if A -> B flow is working fine.
#
#
import re
import argparse
import json
from common import debug, settings
from common import execute_cmd

params = {}

output_dict = {
    'comment': None,
    'pass': None,
    'command_list': [],
    'errors': [],
    'debugs': [],
}

# Learn a MAC on the dst port and then check if sending from the src port to
# the learned MAC gives correct lookup


def ovs_test(src_port_id, dst_port_id, tag, ovs_bridge):
    smac = 'AA:BB:CC:DD:EE:11'
    dmac = 'AA:BB:CC:DD:EE:22'
    cmd_dict = {}

    # Step 0. Flush the fdb
    cmd = ''
    cmd += 'sudo ovs-appctl fdb/flush br-int'
    output = execute_cmd(cmd, shell=True).split('\n')
    cmd_dict['cmd'] = cmd
    cmd_dict['output'] = output
    output_dict['command_list'].append(cmd_dict)
    cmd_dict = {}

    # Step 1. run command that will learn smac
    cmd = ''
    cmd += 'sudo ovs-appctl ofproto/trace %s in_port=%s' % (
        ovs_bridge, src_port_id)
    cmd += ',dl_src=' + smac + ',dl_dst=' + dmac + ' -generate'
    output = execute_cmd(cmd, shell=True).split('\n')
    cmd_dict['cmd'] = cmd
    cmd_dict['output'] = output
    output_dict['command_list'].append(cmd_dict)
    cmd_dict = {}

    # Step 2. verify that the mac has been learnt
    cmd = ''
    cmd += 'sudo ovs-appctl fdb/show br-int'
    output = execute_cmd(cmd, shell=True).split('\n')
    cmd_dict['cmd'] = cmd
    cmd_dict['output'] = output
    output_dict['command_list'].append(cmd_dict)
    cmd_dict = {}

    port = None
    for line in output:
        m = re.search('(\d)\s+(\d+)\s+(\S+)\s+\d+', line)
        if m:
            mac = m.group(3)
            if mac.lower() == smac.lower():
                port = m.group(1)
                vlan = m.group(2)
                debug(line)
                break
    if not port:
        output_dict['errors'].append(
            '%s not learnt on port %s' % (smac, src_port_id))
        output_dict['pass'] = False
        return False

    if vlan != tag:
        output_dict['errors'].append(
            '%s learnt on vlan %s but should have been learnt on vlan %s on port %s' % (smac, vlan, tag, port))
        output_dict['pass'] = False
        return False
    output_dict['debugs'].append(
        '%s learnt on expected vlan %s on port %s' % (smac, vlan, port))

    # Step 3. now do a lookup using the dst port id and dmac as the smac of
    # step 1.
    cmd = ''
    cmd += 'sudo ovs-appctl ofproto/trace %s in_port=%s' % (
        ovs_bridge, dst_port_id)
    cmd += ',dl_src=' + dmac + ',dl_dst=' + smac + ' -generate'
    output = execute_cmd(cmd, shell=True).split('\n')
    cmd_dict['cmd'] = cmd
    cmd_dict['output'] = output
    output_dict['command_list'].append(cmd_dict)
    cmd_dict = {}

    forwarded = False
    egress_port = None
    for line in output:
        if re.search('forwarding to learned port', line):
            forwarded = True
            continue
        m = re.search('Datapath actions: (.*)', line)
        if m:
            egress_port = m.group(1)
            continue

    result = True
    if not forwarded:
        output_dict['errors'].append('Packet for learnt mac not forwarded!')
        result = False
    else:
        output_dict['debugs'].append(
            'Packet for learnt mac forwarded properly')

    if egress_port:
        if egress_port == src_port_id:
            output_dict['debugs'].append(
                'Packet forwarded to correct port %s' % egress_port)
        else:
            output_dict['errors'].append('Packet forwarded to incorrect port %s, expected %s' %
                                         (egress_port, src_port_id))
            result = False
    else:
        output_dict['errors'].append('No egress port assigned to packet! Expected %s' %
                                     src_port_id)
        result = False

    output_dict['pass'] = result
    return result


def check_args():
    global params

    parser = argparse.ArgumentParser(
        description='OVS test', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging', default=False, action='store_true')
    parser.add_argument('--src_port_id', dest='src_port_id',
                        help='OVS src port id (required)', type=str, required=True)
    parser.add_argument('--dst_port_id', dest='dst_port_id',
                        help='OVS dst port id (required)', type=str, required=True)
    parser.add_argument(
        '--tag', dest='tag', help='VLAN tag of port (required)', type=str, required=True)
    parser.add_argument('--ovs_bridge', dest='ovs_bridge',
                        help='OVS bridge to be tested (required)', type=str, required=True)
    args = parser.parse_args()

    settings['debug'] = args.debug
    params['src_port_id'] = args.src_port_id
    params['dst_port_id'] = args.dst_port_id
    params['tag'] = args.tag
    params['ovs_bridge'] = args.ovs_bridge


def main():
    global output_dict

    check_args()

    src_port_id = params['src_port_id']
    dst_port_id = params['dst_port_id']
    tag = params['tag']
    ovs_bridge = params['ovs_bridge']

    ovs_success = ovs_test(src_port_id, dst_port_id, tag, ovs_bridge)

    output_dict[
        'comment'] = 'ovs %s port %s -->  %s' % (ovs_bridge, src_port_id, dst_port_id)
    output_dict['pass'] = ovs_success

    a = json.dumps(output_dict, sort_keys=True, indent=4)
    print a
    pass

if __name__ == "__main__":
    main()
