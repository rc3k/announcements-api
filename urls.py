from django.conf.urls import url

from .views import announcements

app_name = 'Announcements'
urlpatterns = [
    url(r'^', announcements, name='announcements'),
]
