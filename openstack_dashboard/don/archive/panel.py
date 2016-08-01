from django.utils.translation import ugettext_lazy as _
import horizon
from don import dashboard


class archive(horizon.Panel):
    name = _("Archive")
    slug = "archive"

dashboard.DonDashboard.register(archive)
