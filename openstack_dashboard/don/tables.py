from horizon import tables
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from don import api
from django.utils.http import urlencode


class ViewCollection(tables.LinkAction):
    name = 'view'
    verbose_name = _('View')

    def get_link_url(self, datum):
        base_url = reverse('horizon:don:archive:dbview')
        params = urlencode({"id": self.table.get_object_id(datum)})
        return "?".join([base_url, params])


class DeleteCollection(tables.DeleteAction):
    name = 'delete'
    verbose_name = _('Delete')
    data_type_singular = _('Collection')

    def delete(self, request, obj_id):
        return api.remove_collection(request, obj_id)


class CollectionTable(tables.DataTable):
    name = tables.Column('timestamp', verbose_name=_('Generated Time'))

    def get_object_id(self, datum):
        return datum['id']

    class Meta:
        # table_actions = (,)
        row_actions = (ViewCollection, DeleteCollection,)
        name = 'collection'
