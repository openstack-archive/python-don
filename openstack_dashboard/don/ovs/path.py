#
# path.py: Figures out a path between two IP addresses and then traces it
#
# HOWTO:
#
import re
import pprint
import subprocess
import argparse
import os.path
import signal
import json
import time
from common import error, settings, debug, status_update
from common import load_json, execute_cmd, dump_json
from common import ip_to_intf, intf_to_namespace, router_to_namespace

COUNT = 10  # how many packets to be captured by tcpdump


def get_port_info(info, port_ip):
    port_info = None
    for tap, ip in info['tap_to_ip'].iteritems():
        if ip == port_ip:
            port_info = {}
            port_info['ip'] = ip
            port_info['ports'] = {}
            port_info['ports']['tap'] = 'tap' + tap
            port_info['ports']['brctl'] = 'qbr' + tap
            port_info['ports']['qvb'] = 'qvb' + tap
            port_info['ports']['qvo'] = 'qvo' + tap

            # also get the tag (used later to figure out where to run tcpdump)
            br_int = info['bridges'].get('br-int', None)
            if not br_int:
                error('No OVS integration bridge (br-int)! Cannot proceed')
                return None

            tag = br_int['ports'][port_info['ports']['qvo']]['tag']
            port_info['tag'] = tag

            break
    return port_info


def qrouter_usable(qrouter, src_ip, dst_ip, username, passwd):
    status_update('Testing whether %s is reachable via qrouter %s (dst %s)' % (
        src_ip, qrouter, dst_ip))
    outfile = 'path.testping.txt'
    ping_process = launch_ping(
        src_ip, dst_ip, username, passwd, 2, 2, qrouter, outfile)
    status_update("Ping process %s" % (ping_process))
    time.sleep(5)

    ping_pass = process_ping(outfile, src_ip, check_ssh_connectivity_only=True)

    if ping_pass:
        status_update('IP %s is reachable via qrouter: %s' % (src_ip, qrouter))
        return True
    else:
        error('IP %s is reachable via qrouter: %s' % (src_ip, qrouter))

    return False


def launch_ping(src_ip, dst_ip, username, passwd, count, timeout, qrouter, filename):
    cmd = 'sudo ip netns exec ' + str(qrouter)
    cmd += ' python ping.py --src_ip %s --dst_ip %s --username "%s" --passwd "%s" --count %d --timeout %d' % \
        (src_ip, dst_ip, username, passwd, count, timeout)
    cmd += ' > %s 2>&1' % filename

    p = subprocess.Popen(cmd, shell=True)

    return p


def capture_network_packets(params, hop_list):
    global net_info

    net_info = {
        'pids': [],
        'hops': hop_list,
    }

    for hop in net_info['hops']:
        dev = hop['dev']
        nms = hop['nms']
        filename = 'net.tcpdump.%s.txt' % (dev)
        if os.path.isfile(filename):
            os.remove(filename)
        cmd = 'sudo ip netns exec %s ' % nms
        cmd += 'tcpdump -v icmp -i %s -c %d -l > %s 2>&1' % (
            dev, params['count'], filename)
        pid = subprocess.Popen(cmd, shell=True).pid
        net_info['pids'].append(pid)
        status_update(
            'net: tcpdump launched with pid %d for interface %s' % (pid, dev))
    pass


def capture_packets(params, tag='src', src_tag=None):
    if tag == 'src':
        port_info = src_info
    elif tag == 'dst':
        port_info = dst_info
    else:
        error('tag has to be one of [src, dst]!')
        return

    # XXX TODO
    # If src_tag and dst_tag are the same, then we need to monitor on just
    # br-int. Else, we will need to monitor on qr- ports (router ports)

    port_info['pids'] = []
    for port in port_info['ports'].keys():
        intf = port_info['ports'][port]
        filename = '%s.tcpdump.%s.txt' % (tag, intf)
        if os.path.isfile(filename):
            os.remove(filename)
        cmd = 'sudo tcpdump -v icmp -i %s -c %d -l > %s 2>&1' % (
            intf, params['count'], filename)
        pid = subprocess.Popen(cmd, shell=True).pid
        port_info['pids'].append(pid)
        status_update(
            '%s: tcpdump launched with pid %d for interface %s' % (tag, pid, intf))


def process_ping(filename, ip=None, check_ssh_connectivity_only=False):
    if not os.path.isfile(filename):
        return False

    status_update('Trying to read ' + filename)
    with open(filename) as f:
        lines = f.readlines()
    pprint.pprint(lines)

    info = load_json(filename)
    if not check_ssh_connectivity_only:
        return info.get('pass', False)

    cmd_list = info['command_list']
    for cmd in cmd_list:
        m = re.search(
            'ssh (\S+) with provided username and passwd', cmd['cmd'])
        if m:
            if ip == m.group(1):
                return cmd['pass']
    return False


def process_network_captures():
    global net_info

    net_info['counts'] = {}
    net_info['pass'] = []
    net_info['fail'] = []

    for hop in net_info['hops']:
        dev = hop['dev']

        # Assume tcpdump did not capture anything
        net_info['counts'][dev] = 0
        net_info['fail'].append(dev)

        filename = 'net.tcpdump.%s.txt' % (dev)
        if not os.path.isfile(filename):
            continue

        with open(filename) as f:
            lines = f.readlines()
        for line in lines:
            m = re.search('(\d+)\s+packets captured', line)
            if m:
                net_info['counts'][dev] = int(m.group(1))
                net_info['pass'].append(dev)
                break
'''
        cmd = 'grep captured ' + filename
        output = execute_cmd(cmd, shell=True).split('\n')[0]

        m = re.search('(\d+)\s+packets captured', output)
        if m:
            net_info['counts'][dev] = int(m.group(1))
            net_info['pass'].append(dev)
        else:
            net_info['counts'][dev] = 0
            net_info['fail'].append(dev)
'''


def process_captures(tag='src'):
    if tag == 'src':
        port_info = src_info
    elif tag == 'dst':
        port_info = dst_info
    else:
        error('tag has to be one of [src, dst]!')
        return

    port_info['counts'] = {}
    port_info['pass'] = []
    port_info['fail'] = []
    for key in port_info['ports'].keys():
        intf = port_info['ports'][key]

        # Assume tcpdump did not capture anything
        port_info['counts'][key] = 0
        port_info['fail'].append(intf)
        filename = '%s.tcpdump.%s.txt' % (tag, intf)

        if not os.path.isfile(filename):
            continue

        with open(filename) as f:
            lines = f.readlines()
        for line in lines:
            m = re.search('(\d+)\s+packets captured', line)
            if m:
                port_info['counts'][key] = int(m.group(1))
                port_info['pass'].append(intf)
                break

'''
        cmd = 'grep captured ' + filename
        output = execute_cmd(cmd, shell=True).split('\n')[0]

        m = re.search('(\d+)\s+packets captured', output)
        if m:
            port_info['counts'][key] = int(m.group(1))
            port_info['pass'].append(intf)
        else:
            port_info['counts'][key] = 0
            port_info['fail'].append(intf)
'''


def cleanup_processes(pid_list):
    pprint.pprint(pid_list)
    for pid in pid_list:
        try:
            os.kill(pid, signal.SIGKILL)
            status_update('Successfully killed pid: %d' % pid)
        except OSError:
            status_update('Process with pid: %d no longer exists' % pid)
            continue
    pass


def check_args(params):

    parser = argparse.ArgumentParser(description='Does ping test and captures packets along the expected path',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging', default=True,
                        action='store_true')
    parser.add_argument('--src_ip', dest='src_ip',
                        help='IP from where ping will be run (required)',
                        type=str, required=True)
    parser.add_argument('--dst_ip', dest='dst_ip',
                        help='IP to which ping will be run (required)',
                        type=str, required=True)
    parser.add_argument('--username', dest='username',
                        help='SSH login username (required)',
                        type=str, required=True)
    parser.add_argument('--passwd', dest='passwd',
                        help='SSH login passwd (required)',
                        type=str, required=True)
    parser.add_argument('--json_file', dest='json_file',
                        help='JSON file having info of installation (required)',
                        type=str, required=True)
    parser.add_argument('--count', dest='count',
                        help='ping count', type=int, default=COUNT)
    parser.add_argument('--timeout', dest='timeout',
                        help='ping timeout (-W option of ping) in seconds',
                        type=int, default=2)
    parser.add_argument('--router', dest='router',
                        help='router to be used for the test', type=str,
                        required=True)
    parser.add_argument('--path_file', dest='path_file',
                        help="Test results are printed in this file in JSON format",
                        type=str, default='path.json')
    args = parser.parse_args()

    params['debug'] = args.debug
    params['src_ip'] = args.src_ip
    params['dst_ip'] = args.dst_ip
    params['username'] = args.username
    params['passwd'] = args.passwd
    params['count'] = args.count
    params['timeout'] = args.timeout
    params['json_file'] = args.json_file
    params['router'] = args.router
    params['path_file'] = args.path_file


def path_same_network(params, nms_hops=None):
    src_ip = params['src_ip']
    dst_ip = params['dst_ip']
    json_file = params['json_file']
    username = params['username']
    passwd = params['passwd']
    count = params['count']
    timeout = params['timeout']
    qrouter = params['qrouter']
    router = params['router']

    if qrouter_usable(qrouter, src_ip, dst_ip, username, passwd):
        outfile = 'path.ping.txt'
        ping_process = launch_ping(src_ip, dst_ip, username, passwd, count,
                                   timeout, qrouter, outfile)
        debug('Ping started with pid: %d' % ping_process.pid)

        capture_packets(params, 'src')
        capture_packets(params, 'dst', src_tag=src_info['tag'])
        if src_info['tag'] != dst_info['tag']:
            capture_network_packets(params, nms_hops)

        status_update('Waiting %s sec for tcpdump and ping processes to complete' % (
            params['count'] + 2))
        time.sleep(params['count'] + 4)

        status_update('if processes have not stopped, lets kill them')
        cleanup_processes([ping_process.pid] +
                          src_info['pids'] + dst_info['pids'])
        if net_info:
            cleanup_processes(net_info['pids'])

        process_captures('src')
        process_captures('dst')
        if src_info['tag'] != dst_info['tag']:
            process_network_captures()
        ping_pass = process_ping(outfile)

        debug(pprint.pformat(src_info))
        debug(pprint.pformat(dst_info))
        debug(pprint.pformat(net_info))
        info = {
            'src': src_ip,
            'dst': dst_ip,
            'src_info': src_info,
            'dst_info': dst_info,
            'net_info': net_info,
            'ping_pass': ping_pass,
            'error': '',
        }

        status_update('Dumping results into %s in JSON format' %
                      params['path_file'])
        dump_json(info, params['path_file'])

        if params['plot']:
            cmd = 'python plot.py --info_file %s --highlight_file %s --combined_file static/ping' % (
                json_file, params['path_file'])
            status_update('Running ' + cmd)
            output = execute_cmd(cmd, shell=True).split('\n')
            debug(pprint.pformat(output))
        status_update('Done')
    else:
        err_msg = 'Cannot reach %s via router %s' % (src_ip, router)
        info = {
            'src': src_ip,
            'dst': dst_ip,
            'src_info': src_info,
            'dst_info': dst_info,
            'ping_pass': False,
            'error': err_msg
        }
        error(err_msg)
        status_update('Dumping results into %s in JSON format' %
                      params['path_file'])
        dump_json(info, params['path_file'])
        status_update('Done')


def run_remote_cmd(cmd):
    debug('Running: ' + cmd)
    return subprocess.check_output(cmd,
                                   shell=True,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True).replace('\t', '    ')


def get_next_hop(src_info, dst_info, qrouter, params):
    next_hop_list = []
    next_hop = None

    username = params['username']
    passwd = params['passwd']
    src_ip = src_info['ip']
    dst_ip = dst_info['ip']

    remote_cmd = ' ip route get %s' % dst_ip

    cmd = 'sudo ip netns exec ' + qrouter
    cmd += ' python run_nms_cmd.py --host_ip %s --username "%s" --passwd "%s" --cmd "%s" ' % \
        (src_ip, username, passwd, remote_cmd)

    output = run_remote_cmd(cmd)
    a = json.loads(output)

    if not a['pass']:
        return []

    json_file = params['json_file']
    info = load_json(json_file)

    next_hop = {}
    for cmd in a['command_list']:
        if re.search('ip route get', cmd['cmd']):
            m = re.search('\S+\s+via\s+(\S+)', cmd['output'][0])
            if m:
                next_hop['ip'] = m.group(1)
                next_hop['dev'] = 'qr-' + ip_to_intf(info, next_hop['ip'])
                next_hop['nms'] = intf_to_namespace(info, next_hop['dev'])
                break

    next_hop_list.append(next_hop)

    cmd = 'sudo ip netns exec ' + next_hop['nms']
    cmd += remote_cmd

    output = run_remote_cmd(cmd).split('\n')

    prev_nms = next_hop['nms']
    next_hop = {}
    m = re.search('\S+\s+dev\s+(\S+)', output[0])
    if m:
        next_hop['dev'] = m.group(1)
        next_hop['nms'] = prev_nms

    next_hop_list.append(next_hop)
    return next_hop_list


def path(params):
    global src_info
    global dst_info
    global net_info

    src_info = None
    dst_info = None
    net_info = None

    settings['debug'] = True
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    CUR_DIR = os.getcwd()
    if not re.search('/openstack_dashboard/don/', CUR_DIR):
        os.chdir(BASE_DIR + '/ovs')
    NEW_DIR = os.getcwd()
    debug(BASE_DIR + ':' + CUR_DIR + ':' + NEW_DIR)

    src_ip = params['src_ip']
    dst_ip = params['dst_ip']
    json_file = params['json_file']
    router = params['router']

    debug('Json_file: ' + json_file)

    info = load_json(json_file)
    qrouter = router_to_namespace(info, router)
    params['qrouter'] = qrouter

    src_info = get_port_info(info, src_ip)
    dst_info = get_port_info(info, dst_ip)

    if src_info is None:
        return "Source ip not found on the network"
    if dst_info is None:
        return "Destination ip not found on the network"
    if qrouter is None:
        return "No such router information found on the network"

    # src and dst are in the same network
    if src_info['tag'] == dst_info['tag']:
        path_same_network(params)
    else:
        status_update('The source and destination are in different networks')
        next_hop_list = get_next_hop(src_info, dst_info, qrouter, params)
        if len(next_hop_list) == 0:
            error('Could not find next hop list from %s to %s' %
                  (src_ip, dst_ip))
        path_same_network(params, next_hop_list)

    pass


def main():

    params = {}
    check_args(params)

    settings['debug'] = params['debug']
    path(params)

if __name__ == "__main__":
    main()
