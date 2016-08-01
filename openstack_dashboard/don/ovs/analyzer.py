#
# analyzer.py:
#
# This file implements the following:
# 1. Analysis of the collected info
# 2. Report any problems
# 3. Report what is correct
#
import pprint
import re
import argparse
import subprocess
import json
import os
from itertools import combinations

from common import settings, debug, get_router
from common import load_json, get_subnet, is_network_public
import yaml

tick = '&#10004;'
cross = '&#10008;'


def get_vm_qrouters(info, vm):
    vms = info['vms']
    if not vms.has_key(vm):
        return 'unknown'

    # Get IP of any of the VM's interfaces
    for ip in vms[vm]['interfaces'].keys():
        break

    routers = []
    subnet = get_subnet(ip)
    namespaces = info['namespaces']
    for nms in namespaces.keys():
        if re.search('^qrouter-', nms):
            if not namespaces[nms].has_key('interfaces'):
                continue
            for intf in namespaces[nms]['interfaces'].keys():
                ip = namespaces[nms]['interfaces'][intf]
                if re.search(subnet, ip):
                    routers.append(nms)
    return routers

# Even if there is one qrouter namespace via which all ping tests passed, we
# consider the ping test to be a success.


def did_ping_test_pass(cmds):
    qrouter_result = True
    for qrouter in sorted(cmds.keys()):
        debug('Checking ping status in qrouter %s' % qrouter)
        qrouter_result = True
        for key in cmds[qrouter].keys():
            (src_vm, dst_vm) = key
            for key2 in sorted(cmds[qrouter][key].keys()):
                (src_ip, dst_ip) = key2
                result = cmds[qrouter][key][key2]['pass']
                if not result:
                    qrouter_result = False
                    break  # check the next namsepace, this one failed
        # if all ping passed via this qrouter, return true
        if qrouter_result:
            return qrouter_result

    # There was no qrouter via which all pings passed!
    return qrouter_result


def run_ping_command(cmd, comment=''):
    debug('Running ' + comment + ': ' + cmd)
    return subprocess.check_output(cmd,
                                   shell=True,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True).replace('\t', '    ')


def report_file_open(report_file):
    f = open(report_file, 'w')
    f.write('<html>\n')
    f.write('<head>\n')
    f.write(
        '<script type="text/javascript" src="{{ STATIC_URL }}/don/CollapsibleLists.js"></script>\n')
    f.write(
        '<link rel="stylesheet" type="text/css" href="{{ STATIC_URL }}/don/don.css">\n')
    f.write('<title>DON: Analysis Results</title>\n')
    f.write('</head>\n')
    f.write('<body onload=CollapsibleLists.apply()>\n')

    return f


def report_file_close(file_handle):
    file_handle.write('</body>\n')
    file_handle.write('</html>\n')


def print_ping_result(cmds, overall_result, info, comment=None):
    lines = []
    lines.append('<h2>Ping Test Results</h2>\n')
    if comment:
        lines.append('<h3>%s</h3>\n' % comment)
    lines.append('<ul class="collapsibleList">\n')
    for qrouter in sorted(cmds.keys()):
        router = get_router(qrouter, info)
        lines.append('  <li>%s (Namespace [%s])\n' % (router, qrouter))
        lines.append('  <ul class="collapsibleList">\n')
        for key in sorted(cmds[qrouter].keys()):
            (src_vm, dst_vm) = key
            lines.append('    <li>%s &rarr; %s\n' % (src_vm, dst_vm))
            lines.append('    <ul class="collapsibleList">\n')
            for key2 in sorted(cmds[qrouter][key].keys()):
                (src_ip, dst_ip) = key2
                result = cmds[qrouter][key][key2]['pass']
                result_str = '<font class="fail">%s</font>' % cross
                if result:
                    result_str = '<font class="pass">%s</font>' % tick
                lines.append('      <li>%15s &rarr; %15s    %s\n' %
                             (src_ip, dst_ip, result_str))
                lines.append('      <ul class="collapsibleList">\n')
                if result:
                    lines.append('        <pre class="pass">\n')
                else:
                    lines.append('        <pre class="fail">\n')
                for line in cmds[qrouter][key][key2]['output'].split('\n'):
                    lines.append(line + '\n')
                lines.append('        </pre>\n')
                lines.append('      </ul>\n')
                lines.append('      </li>\n')
            lines.append('    </ul>\n')
            lines.append('    </li>\n')
        lines.append('  </ul>\n')
        lines.append('  </li>\n')
    lines.append('</ul>\n')

    overall_str = '<font class="fail">%s</font>' % cross
    if overall_result:
        overall_str = '<font class="pass">%s</font>' % tick
    lines.append('OVERALL RESULT: %s\n' % overall_str)
    return lines


def get_vm_credentials(config_file='credentials.yaml'):
    try:
        with open(config_file, 'r') as s:
            return yaml.safe_load(s)
    except IOError, e:
        print '%s :%s' % (e.args[1], config_file)
        raise


def test_ping(info):
    debug('Running ping test')
    vms = info['vms']
    vm_credentials = get_vm_credentials()
    for vm in sorted(vms.keys()):
        vms[vm]['qrouter'] = get_vm_qrouters(info, vm)

    vm_pairs = list(combinations(sorted(vms.keys()), 2))
    pprint.pprint(vm_pairs)
    cmds = {}
    for (src_vm, dst_vm) in vm_pairs:
        for qrouter in vms[src_vm]['qrouter']:
            debug(qrouter)
            if not cmds.has_key(qrouter):
                cmds[qrouter] = {}
            cmds[qrouter][(src_vm, dst_vm)] = {}
            for src_ip in vms[src_vm]['interfaces'].keys():
                if is_network_public(src_ip, src_vm, info):
                    continue
                for dst_ip in vms[dst_vm]['interfaces'].keys():
                    if is_network_public(dst_ip, dst_vm, info):
                        continue
                    username = vm_credentials.get(
                        src_vm, vm_credentials['default'])['username']
                    passwd = vm_credentials.get(src_vm, vm_credentials[
                                                'default'])['password']
                    cmd = 'sudo ip netns exec ' + qrouter
                    cmd += ' python ping.py --src_ip %s --dst_ip %s --username "%s" --passwd "%s" --count %d --timeout %d' % \
                        (src_ip, dst_ip, username, passwd, 1, 2)

                    comment = 'Ping [%s (%s) => %s (%s)]' % (
                        src_vm, src_ip, dst_vm, dst_ip)
                    output = run_ping_command(cmd, comment=comment)
                    a = json.loads(output)
                    success = a['pass']
                    cmds[qrouter][(src_vm, dst_vm)][(src_ip, dst_ip)] = {
                        'cmd': cmd,
                        'output': output,
                        'pass': success
                    }

    debug(pprint.pformat(cmds))
    ping_test_passed = did_ping_test_pass(cmds)

    return (ping_test_passed, cmds)


def run_ovs_command(cmd, comment=''):
    debug('Running ' + comment + ': ' + cmd)
    return subprocess.check_output(cmd,
                                   shell=True,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True).replace('\t', '    ')


def process_ovs_output(output):
    for line in output:
        if re.search('PASS', line):
            return True
    return False


def print_ovs_result(cmds, overall_result, info, comment=None):
    lines = []
    lines.append('<h2>OVS Test Results</h2>\n')
    if comment:
        lines.append('<h3>%s</h3>\n' % comment)
    lines.append('<ul class="collapsibleList">\n')
    lines.append('  <li>OVS bridge br-int\n')
    lines.append('  <ul class="collapsibleList">\n')
    for tag in sorted(cmds.keys()):
        lines.append('    <li>tag %s\n' % (tag))
        lines.append('    <ul class="collapsibleList">\n')
        for key in sorted(cmds[tag].keys()):
            (src_port, dst_port) = key
            result = cmds[tag][key]['pass']
            result_str = '<font class="fail">%s</font>' % cross
            if result:
                result_str = '<font class="pass">%s</font>' % tick
            lines.append('      <li>%3s &rarr; %3s    %s\n' %
                         (src_port, dst_port, result_str))
            lines.append('      <ul class="collapsibleList">\n')
            if result:
                lines.append('        <pre class="pass">\n')
            else:
                lines.append('        <pre class="fail">\n')
            for line in cmds[tag][key]['output'].split('\n'):
                lines.append(line + '\n')
            lines.append('      </ul>\n')
            lines.append('      </li>\n')
        lines.append('    </ul>\n')
        lines.append('    </li>\n')

    lines.append('  </ul>\n')
    lines.append('  </li>\n')
    lines.append('</ul>\n')

    overall_str = '<font class="fail">%s</font>' % cross
    if overall_result:
        overall_str = '<font class="pass">%s</font>' % tick
    lines.append('OVERALL RESULT: %s\n' % overall_str)
    return lines


def test_ovs(info):
    debug('Running OVS test')
    ovs_test_passed = True
    cmds = {}

    # first construct a dictionary of tag to br-int ports
    br_int_ports = info['bridges']['br-int']['ports']

    tag_to_port = {}
    for port in br_int_ports.keys():
        if not re.search('^qvo', port):
            continue
        tag = br_int_ports[port]['tag']
        port_id = br_int_ports[port]['id']
        if not tag_to_port.has_key(tag):
            tag_to_port[tag] = []
        tag_to_port[tag].append((port_id, port))

    debug(pprint.pformat(tag_to_port))
    for tag in sorted(tag_to_port.keys(), key=lambda x: int(x)):
        cmds[tag] = {}
        port_count = len(tag_to_port[tag])
        if port_count < 2:
            debug('tag %s is used by single port %s. Skipping test!' %
                  (tag, tag_to_port[tag][0]))
            continue

        port_list = list(map(lambda (x, y): x, tag_to_port[tag]))
        sorted_port_list = sorted(port_list, key=lambda x: int(x))
        port_pairs = list(combinations(sorted_port_list, 2))

        for (src_port, dst_port) in port_pairs:
            cmds[tag][(src_port, dst_port)] = {}

            cmd = ''
            cmd += 'python ovs.py --src_port_id %s --dst_port_id %s --tag %s --ovs_bridge br-int' % \
                (src_port, dst_port, tag)
            comment = 'ovs [tag: %s port %s => %s' % (tag, src_port, dst_port)
            output = run_ovs_command(cmd, comment=comment)
            success = process_ovs_output(output)
            if not success:
                ovs_test_passed = False

            cmds[tag][(src_port, dst_port)] = {
                'cmd': cmd,
                'output': output,
                'pass': success
            }

    return (ovs_test_passed, cmds)


# Dictionary of tests
test_suite = {
    'ping': {
        'help': 'Ping test between all pairs of VMs',
        'func': test_ping,
        'result': 'not run',
        'formatter': print_ping_result,
        'html': None,
    },
    'ovs': {
        'help': 'OVS test between all pairs of ports using the same tag in br-int',
        'func': test_ovs,
        'result': 'not run',
        'formatter': print_ovs_result,
        'html': None,
    },
}


def analyze(json_filename, params):
    settings['debug'] = True
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    CUR_DIR = os.getcwd()
    os.chdir(BASE_DIR + '/ovs')
    # NEW_DIR = os.getcwd()
    # return BASE_DIR + ':' + CUR_DIR + ':' + NEW_DIR
    debug('This is what I am going to analyze')
    my_info = load_json(json_filename)

    for test in test_suite.keys():
        flag = 'test:' + test
        if params[flag] or params['test:all']:
            (result, cmds) = test_suite[test]['func'](my_info)
            if result:
                test_suite[test]['result'] = 'PASS'
            else:
                test_suite[test]['result'] = 'FAIL'
            lines = test_suite[test]['formatter'](cmds,
                                                  result,
                                                  my_info,
                                                  test_suite[test]['help'])
            test_suite[test]['html'] = lines

    debug(params['test:report_file'])
    f = report_file_open(params['test:report_file'])
    for test in test_suite.keys():
        if test_suite[test]['html']:
            for line in test_suite[test]['html']:
                f.write(line)
    report_file_close(f)
    os.chdir(CUR_DIR)


def check_args():
    parser = argparse.ArgumentParser(description='Static analysis of output of commands',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', dest='debug',
                        help='Enable debugging',
                        default=True, action='store_true')
    parser.add_argument('--info_file', dest='info_file',
                        help='Info is read  in JSON format in this file',
                        default="don.json", type=str)
    parser.add_argument('--ping', dest='ping',
                        help='ping test between all VMs', default=False,
                        action='store_true')
    parser.add_argument('--ping_count', dest='ping_count',
                        help='how many ping packets to send',
                        default=2, type=int)
    parser.add_argument('--ping_timeout', dest='ping_timeout',
                        help='ping timeout period in seconds',
                        default=2, type=int)
    parser.add_argument('--ovs', dest='ovs',
                        help='ovs test between ports using same tag in br-int',
                        default=False, action='store_true')
    parser.add_argument('--test_all', dest='test_all',
                        help='Perform all tests in test suite',
                        default=False, action='store_true')
    parser.add_argument('--error_file', dest='error_file',
                        help='All errors will be reported to this file',
                        type=str, default='don.error.txt')
    parser.add_argument('--report_file', dest='report_file',
                        help='Report will be written in this file in HTML format',
                        type=str, default='don.report.html')
    args = parser.parse_args()

    settings['debug'] = args.debug
    settings['info_file'] = args.info_file
    settings['error_file'] = args.error_file
    settings['test:all'] = args.test_all
    settings['test:ping'] = args.test_all or args.ping
    settings['test:ping_count'] = args.ping_count
    settings['test:ping_timeout'] = args.ping_timeout
    settings['test:ovs'] = args.test_all or args.ovs
    settings['test:report_file'] = args.report_file


def main():
    check_args()
    analyze(settings['info_file'], settings)
    pprint.pprint(test_suite)

if __name__ == "__main__":
    main()
