from functools import partial
from logging import getLogger
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.db.models import signals
from django.template import loader

from .models import Announcement
from .domain import get_announcement_recipients


def send_announcement_emails(sender, **kwargs):
    announcement = kwargs.get('instance')
    if kwargs.get('created') and announcement.is_urgent:
        recipients = get_announcement_recipients(announcement)
        subject = loader.get_template('announcements/email/announcement_email_subject.txt')
        body = loader.get_template('announcements/email/announcement_email.txt')

        # get emails as a data-tuples (subject, message, from_email, recipient_list)
        emails = map(
            partial(_get_email_datatuple, subject=subject, body=body),
            [r for r in recipients if r.email != '']
        )

        for email in emails:
            try:
                send_mail(*email)
            except SMTPException as e:
                logger = getLogger(__name__)
                logger.error(e.args[0])


def _get_email_datatuple(user, subject, body):
    name = ' '.join([user.first_name, user.last_name]).strip()
    return (
        ''.join(subject.render().splitlines()),
        body.render({
            'recipient_name': user.username if name == '' else name,
            'hub_url': settings.WWWROOT + reverse('my_hub')
        }),
        None,
        [user.email]
    )

signals.post_save.connect(send_announcement_emails, sender=Announcement)
