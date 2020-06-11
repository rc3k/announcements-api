from django.contrib import admin

from .models import Announcement


class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('subject', 'visible_from', 'visible_to', 'is_urgent', 'audience', 'programme', 'created', 'modified')
    list_filter = ('visible_from', 'visible_to', 'is_urgent', 'audience', 'programme', 'created', 'modified')
    search_fields = ('subject', 'body', 'user__first_name', 'user__last_name', 'user__username')


admin.site.register(Announcement, AnnouncementAdmin)
