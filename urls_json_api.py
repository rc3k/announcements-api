from django.conf.urls import url

from .views_json_api import visible, count_unread, mark_read, mark_unread, master_courses, scheduled_courses
from .views_json_api import scheduled_course_groups, announcements, get, add, update, delete

app_name = 'Announcements API'
urlpatterns = [
    url(r'^$', announcements, name='announcements'),
    url(r'^(?P<pk>[0-9]+)$', get, name='get'),
    url(r'^add/$', add, name='add'),
    url(r'^update/(?P<pk>[0-9]+)$', update, name='update'),
    url(r'^delete/(?P<pk>[0-9]+)$', delete, name='delete'),
    url(r'^visible/$', visible, name='visible'),
    url(r'^count/unread/$', count_unread, name='count_unread'),
    url(r'^mark/read/(?P<pk>[0-9]+)$', mark_read, name='mark_read'),
    url(r'^mark/unread/(?P<pk>[0-9]+)$', mark_unread, name='mark_unread'),
    url(r'^masters/$', master_courses, name='master_courses'),
    url(r'^scheduleds/$', scheduled_courses, name='scheduled_courses'),
    url(r'^groups/$', scheduled_course_groups, name='scheduled_course_groups'),
]
