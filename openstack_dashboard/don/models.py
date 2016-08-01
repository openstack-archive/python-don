"""
Stub file to work around django bug: https://code.djangoproject.com/ticket/7198
"""

from django.db import models


class collector(models.Model):
        # collector table fields
    timestamp = models.CharField(max_length=50)
    data = models.TextField()
