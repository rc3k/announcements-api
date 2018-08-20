from announcements.serializers import UserAnnouncementSerializer
from announcements.domain import announcement_chars_truncate


def test_user_announcement_serializer_get_body():
    p1 = 'Hi all, unfortunately I have had to re-schedule the upcoming class tomorrow for reasons unknown.' \
         'Please complete the recommended reading regardless'
    body = '<p>%s</p>' % p1
    tail = '…'

    serialized = UserAnnouncementSerializer.get_body({'body': body})
    assert serialized['body'] == body
    assert serialized['truncated'] == '<p>%s%s</p>' % (
        p1[:(announcement_chars_truncate - 1)],
        tail
    )


def test_user_announcement_serializer_get_body_with_html_entities():
    p1 = 'Hi all, %s unfortunately I have %s had to re-schedule the upcoming class tomorrow for reasons unknown.' \
         'Please complete the recommended reading regardless'
    with_entities = p1 % ('&amp;', '&gt;')
    without_entities = p1 % ('&', '>')
    tail = '…'

    serialized = UserAnnouncementSerializer.get_body({'body': '<p>%s</p>' % with_entities})
    assert serialized['body'] == '<p>%s</p>' % without_entities
    assert serialized['truncated'] == '<p>%s%s</p>' % (
        without_entities[:(announcement_chars_truncate - len(tail))],
        tail
    )


def test_user_announcement_serializer_get_body_too_short():
    p1 = 'Hi all &amp; welcome'

    serialized = UserAnnouncementSerializer.get_body({'body': '<p>%s</p>' % p1})
    assert serialized['body'] == '<p>%s</p>' % 'Hi all & welcome'
    assert serialized['truncated'] == serialized['body']
