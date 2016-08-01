from django.utils.translation import ugettext_lazy as _

import horizon
from don import dashboard


class ovs(horizon.Panel):
    name = _("OVS")
    slug = "ovs"


dashboard.DonDashboard.register(ovs)
