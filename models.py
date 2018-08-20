from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.timezone import now

from programmes.models import Programme


AUDIENCES = (
    ('all', 'All'),
    ('students', 'All students'),
    ('tutors', 'All tutors'),
    ('students_and_tutors', 'All students and tutors'),
)


def _plus_one_week():
    return now() + timedelta(weeks=1)


class Announcement(models.Model):
    subject = models.CharField(max_length=100)
    body = models.TextField()
    visible_from = models.DateTimeField(default=now, db_index=True)
    visible_to = models.DateTimeField(default=_plus_one_week, db_index=True)
    is_urgent = models.BooleanField(default=False, db_index=True)
    audience = models.CharField(choices=AUDIENCES, max_length=20)
    programme = models.ForeignKey(Programme, null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject

    class Meta:
        permissions = [
            ('create_announcement', 'Can create announcement'),
        ]


class UserAnnouncement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'announcement',)
