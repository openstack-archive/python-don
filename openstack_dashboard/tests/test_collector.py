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
import os
import tempfile

import openstack_dashboard.don.ovs.collector as collector
from openstack_dashboard.tests import base


class TestOvsCollector(base.TestCase):
    """Tests openvswitch collector module."""
    def setUp(self):
        super(TestOvsCollector, self).setUp()

        # Create a temporary file
        self.tmp_fd, self.tmp_fp = tempfile.mkstemp(dir=os.getcwd())

    def tearDown(self):
        super(TestOvsCollector, self).tearDown()

        # Remove the file
        os.remove(self.tmp_fp)

    def test_get_env(self):
        lines = ["export x=2", "export y=3", "z=4"]
        with open(self.tmp_fp, 'w') as f:
            f.write("\n".join(lines))
        env = collector.get_env(os.path.basename(self.tmp_fp))
        self.assertEqual(env, dict(x='2', y='3'))

    def test_add_new_command(self):
        commands = {}
        cmd_key = 'netns_test'
        cmd = {'cmd': 'echo netns test'}

        collector.add_new_command(commands, cmd_key, cmd)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[cmd_key], cmd)

        # Try to add the same command again
        collector.add_new_command(commands, cmd_key, cmd)
        self.assertEqual(len(commands), 1)

    def test_record_linuxbridge(self):

        bridges = {}
        bridge = 'test_bridge'
        interfaces_list = 'eth0'

        collector.record_linuxbridge(bridges, bridge, interfaces_list)

        self.assertEqual(len(bridges), 1)
        self.assertEqual(bridges[bridge], dict(interfaces=interfaces_list))

    def test_get_bridge_entry(self):

        supported_bridge = 'br-ex'
        false_bridge = 'br-test'

        self.assertIsNone(collector.get_bridge_entry(false_bridge))
        self.assertEqual(dict(ports={}),
                         collector.get_bridge_entry(supported_bridge))
