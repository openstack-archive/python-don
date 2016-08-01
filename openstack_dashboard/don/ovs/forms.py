from django import forms


class PingForm(forms.Form):
    src_ip = forms.CharField(label='Source IP', widget=forms.Select(
        attrs={'class': 'form-control switchable'}, choices=[('', "")]))
    dst_ip = forms.CharField(label='Destination IP', widget=forms.Select(
        attrs={'class': 'form-control switchable'}, choices=[('', "")]))
    router = forms.CharField(label='Router', widget=forms.Select(
        attrs={'class': 'form-control switchable'}, choices=[('', "")]))
