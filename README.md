# DON: Diagnosing OpenStack Networking

An OpenStack Horizon dashboard to diagnose OpenStack networking issues.

* Free software: Apache license
* Source: https://git.openstack.org/openstack/python-don
* Bugs: https://bugs.launchpad.net/python-don

## Overview
> [Presented in the OpenStack Liberty Summit, Vancouver, May, 2015]
(https://www.openstack.org/summit/vancouver-2015/summit-videos/presentation/don-diagnosing-ovs-in-neutron "DON Presentation at OpenStack Liberty Summit, Vancouver, May 2015").

A lot has changed since Vancouver! _Support for multi-node OpenStack
installations and complete integrated with Horizon, Liberty release are among
the things to look forward to._

Neutron provides Networking-as-a-service in the OpenStack ecosystem. Networking
functionalities are provided by plugins that implement well-defined Neutron
APIs. Among many, the Open vSwitch plugin (OVS) is possibly the most widely
used. Any practical OpenStack installation has complicated networking
configuration and verifying it manually is time consuming and error prone.
DON, written primarily in Python, and **available as a dashboard in OpenStack
Horizon, Libery release**, is a network analysis and diagnostic system and provides a
completely automated service for verifying and diagnosing the
networking functionality provided by OVS. This service verifies (or points out
deviations) that the user configuration is indeed reflected in the underlying
infrastructure and presents the results in an intuitive graphical display.
## Feature Lists:

0. Visualize networking internals
1. Perform OVS and Ping tests between all pairs of VMs
2. Perform Ping tracing between any two VMs
3. Allows storing collected data so that it can be retrieved later and displayed

As an example, given the following Neutron network topology:
![Neutron: Network Topology](/openstack_dashboard/don/ovs/static/net_topology.png "Neutron: Network Topology")

DON generates the following view of the networking internals,
![DON: Internal View](/openstack_dashboard/don/ovs/static/don_internal.png "DON: Internal View")

does OVS tests and ping tests,
![DON: Analysis](/openstack_dashboard/don/ovs/static/don_analysis.png "DON: Analysis")

and also allows the user to do ping tracing
![DON: Ping Tracer](/openstack_dashboard/don/ovs/static/don_ping_notworking.png "DON: Ping Tracer")

## DON Schematic
DON first collects the output of several commands, parses the output, and
creates a JSON database. This database is then used by the analyzer module, the
visualizer module, and the test module.
<img src="/images/don_schematic.png" width="51%" align="middle" alt="DON Schematic">


## How to Run:

### Prerequisites:

* Django version must be 1.7 or later. However, since OpenStack Horizon uses
  Django, there is no need to separately install Django.

* The [Graphviz dot](http://www.graphviz.org/) utility. This is used for
  drawing the visualization.

### Steps for DevStack:

0. You must have a [devstack setup running on a single VM](http://docs.openstack.org/developer/devstack/guides/single-vm.html).
1. [Download and source the project specific rc file](http://docs.openstack.org/user-guide/common/cli_set_environment_variables_using_openstack_rc.html).
.. code-block:: shell
    $ git clone https://github.com/openstack/python-don.git
2. Copy openstack_dashboard/, static/ directories from DON source to Horizon directory.(/opt/stack/horizon/)
.. code-block:: shell
    $ cp -R python-don/openstack_dashboard/don /opt/stack/horizon/openstack_dashboard/
3. Copy etc/don/ from DON source to /etc 
.. code-block:: shell
    # mkdir /etc/don
    # chown stack:root /etc/don
    # cp etc/don/don.conf /etc/don/
    # chown -R stack:stack /etc/don/don.conf
4. Edit /etc/don/don.conf and change `deployment_type=devstack` under [DEFAULT] section.
.. code-block:: shell
    # sed -i "s/deployment_type=multinode/deployment_type=devstack/" /etc/don/don.conf 
5. To allow DON to do Ping tests between all pairs of VMs, configure VM credentials manually into /opt/stack/horizon/openstack_dashboard/don/ovs/credentials.yaml
6. Compress django javascript libraries
.. code-block:: shell
    $ DJANGO_SETTINGS_MODULE=openstack_dashboard.settings django-admin compress --force
7. Restart Horizon by executing `sudo service apache2 restart`

### Steps for Multinode Openstack:

0. You must have Ansible (version 2.0 or later) installed in execution server
1. Clone DON source to execution server
2. Open shell prompt and execute the below command from DON directory
3. `ansible-playbook don_playbook.yaml -i <inventory file path> --ask-pass`

