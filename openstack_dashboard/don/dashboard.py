from django.utils.translation import ugettext_lazy as _

import horizon


class DonDashboard(horizon.Dashboard):
    name = _("DON")
    slug = "don"
    panels = ('ovs', 'archive')  # Add your panels here.
    default_panel = 'ovs'  # Specify the slug of the dashboard's default panel.


horizon.register(DonDashboard)
