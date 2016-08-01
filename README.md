# DON: Diagnosing OpenStack Networking

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

As an example, given the following Neutron network topology:
![Neutron: Network Topology](/openstack_dashboard/don/ovs/static/net_topology.png "Neutron: Network Topology")

DON generates the following view of the networking internals,
![DON: Internal View](/openstack_dashboard/don/ovs/static/don_internal.png "DON: Internal View")

does OVS tests and ping tests,
![DON: Analysis](/openstack_dashboard/don/ovs/static/don_analysis.png "DON: Analysis")

and also allows the user to do ping tracing
![DON: Ping Tracer](/openstack_dashboard/don/ovs/static/don_ping_notworking.png "DON: Ping Tracer")

The project is in beta status and we are in the process of moving it to [stackforge](https://github.com/stackforge).

## How to Run:

### Prerequisites:

* Django version must be 1.7 or later. However, since OpenStack Horizon uses
  Django, there is no need to separately install Django.

* The [Graphviz dot](http://www.graphviz.org/) utility. This is used for
  drawing the visualization.

### Steps for DevStack:

0. You must have a [devstack setup running on a single VM](http://docs.openstack.org/developer/devstack/guides/single-vm.html).
1. [Download and source the project specific rc file](http://docs.openstack.org/user-guide/common/cli_set_environment_variables_using_openstack_rc.html).
2. Copy the DON source to Horizon directory.(/opt/stack/horizon/)
3. Restart Horizon by executing `sudo service apache2 restart`

### Steps for Multinode Openstack:

0. You must have Ansible (version 2.0 or later) installed in execution server
1. Clone DON source to execution server
2. Open shell promt and execute the below command from DON directory 
3. `ansible-playbook don_playbook.yaml -i <inventory file path> --ask-pass`

## TODO/Known Issues:
Please look at issues in the github repo. If you have questions, bugs, or feature requests, file an issue or send email
to:

* Amit Saha (amisaha+don@cisco.com)
