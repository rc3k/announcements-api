import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from rest_framework.settings import api_settings

from .domain import get_audiences_and_programmes


@login_required
def announcements(request):
    if not request.user.has_perm('announcements.add_announcement'):
        return HttpResponseForbidden()
    return render(request, 'announcements/announcements.html', {
        'audiences_and_programmes': json.dumps(get_audiences_and_programmes()),
        'api_settings': json.dumps({
            'nonFieldErrorsKey': api_settings.NON_FIELD_ERRORS_KEY,
        })
    })
