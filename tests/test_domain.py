from datetime import timedelta

from django.core.cache import caches
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.timezone import now
from django.utils.translation import gettext as _

import pytest
from mock import patch
from rest_framework.exceptions import PermissionDenied

from programmes.models import Programme, UserProgramme, MasterCourse, ProgrammeMasterCourse, ScheduledCourse, ScheduledCourseGroup
from announcements.models import AUDIENCES
from announcements.models import Announcement, UserAnnouncement
from announcements.domain import (get_audiences_and_programmes, get_master_courses, get_scheduled_courses, get_scheduled_course_groups,
                                  get_visible_announcements_for_user, get_announcements_marked_read_for_user, get_announcements,
                                  get_announcement, get_announcement_options, add_announcement, update_announcement,
                                  delete_announcement, get_announcement_recipients)
from announcements.domain import course_and_group_memberships_cache_key
from announcements.serializers import AnnouncementSerializer


def fst(list):
    return list[0]


def snd(list):
    return list[1]


@pytest.fixture
def tnow():
    return now()


@pytest.fixture
def programmes():
    p1 = Programme.objects.create(display_name='Programme 1')
    p2 = Programme.objects.create(display_name='Programme 2')
    p3 = Programme.objects.create(display_name='Programme 3')
    p4 = Programme.objects.create(display_name='Programme 4')
    return [p1, p2, p3, p4]


@pytest.fixture
def master_courses():
    mc1 = MasterCourse.objects.create(display_name='Master A', vle_course_id='A')
    mc2 = MasterCourse.objects.create(display_name='Master B', vle_course_id='B')
    mc3 = MasterCourse.objects.create(display_name='Master C', vle_course_id='C')
    mc4 = MasterCourse.objects.create(display_name='Master D', vle_course_id='D')
    mc5 = MasterCourse.objects.create(display_name='Master E', vle_course_id='E')
    return [mc1, mc2, mc3, mc4, mc5]


@pytest.fixture
def programme_master_courses(programmes, master_courses):
    pmc1a = ProgrammeMasterCourse.objects.create(programme=programmes[0], master_course=master_courses[0], available=True)
    pmc1b = ProgrammeMasterCourse.objects.create(programme=programmes[0], master_course=master_courses[1], available=True)
    pmc1c = ProgrammeMasterCourse.objects.create(programme=programmes[0], master_course=master_courses[2], available=True)
    pmc2b = ProgrammeMasterCourse.objects.create(programme=programmes[1], master_course=master_courses[1], available=True)
    pmc2c = ProgrammeMasterCourse.objects.create(programme=programmes[1], master_course=master_courses[2], available=True)
    pmc2d = ProgrammeMasterCourse.objects.create(programme=programmes[1], master_course=master_courses[3], available=False)
    pmc3e = ProgrammeMasterCourse.objects.create(programme=programmes[2], master_course=master_courses[4], available=True)
    return [pmc1a, pmc1b, pmc1c, pmc2b, pmc2c, pmc2d, pmc3e]


@pytest.fixture
def scheduled_courses(master_courses):
    sc1a = ScheduledCourse.objects.create(master_course=master_courses[0], display_name='A001', vle_course_id='A001')
    sc1b = ScheduledCourse.objects.create(master_course=master_courses[0], display_name='A002', vle_course_id='A002')
    sc1c = ScheduledCourse.objects.create(master_course=master_courses[0], display_name='A003', vle_course_id='A003')
    sc2a = ScheduledCourse.objects.create(master_course=master_courses[1], display_name='B001', vle_course_id='B001')
    sc2b = ScheduledCourse.objects.create(master_course=master_courses[1], display_name='B002', vle_course_id='B002')
    sc3a = ScheduledCourse.objects.create(master_course=master_courses[2], display_name='C001', vle_course_id='C001')
    return [sc1a, sc1b, sc1c, sc2a, sc2b, sc3a]


@pytest.fixture
def scheduled_course_groups(scheduled_courses):
    scg1aa = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[0], display_name='A001/A', vle_group_id='A001/A')
    scg1ab = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[0], display_name='A001/B', vle_group_id='A001/B')
    scg1ac = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[0], display_name='A001/C', vle_group_id='A001/C')
    scg1ba = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[1], display_name='A002/A', vle_group_id='A002/A')
    scg1bb = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[1], display_name='A002/B', vle_group_id='A002/B')
    scg1bc = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[1], display_name='A002/C', vle_group_id='A002/C')
    scg1ca = ScheduledCourseGroup.objects.create(scheduled_course=scheduled_courses[2], display_name='A003/A', vle_group_id='A003/A')
    return [scg1aa, scg1ab, scg1ac, scg1ba, scg1bb, scg1bc, scg1ca]


@pytest.fixture
def groups():
    students = Group.objects.create(name='students')
    tutors = Group.objects.create(name='tutors')
    return [students, tutors]


@pytest.fixture
def users(groups, programmes):
    students = groups[0]
    tutors = groups[1]

    admin = get_user_model().objects.create(
        username='admin',
        first_name='The',
        last_name='Boss',
        is_superuser=True,
        is_staff=True
    )

    tyrion = get_user_model().objects.create(
        username='tyrion.lannister',
        first_name='Tyrion',
        last_name='Lannister',
    )

    sansa = get_user_model().objects.create(
        username='sansa.stark',
        first_name='Sansa',
        last_name='Stark',
    )

    arya = get_user_model().objects.create(
        username='arya.stark',
        first_name='Arya',
        last_name='Stark',
    )

    student_a = get_user_model().objects.create(
        username='student.a',
        first_name='Student',
        last_name='A',
    )
    student_a.groups.add(students)

    student_b = get_user_model().objects.create(
        username='student.b',
        first_name='Student',
        last_name='B',
    )
    student_b.groups.add(students)
    UserProgramme.objects.create(programme=programmes[0], user=student_b)
    UserProgramme.objects.create(programme=programmes[2], user=student_b)

    student_c = get_user_model().objects.create(
        username='student.c',
        first_name='Student',
        last_name='C',
    )
    student_c.groups.add(students)
    UserProgramme.objects.create(programme=programmes[0], user=student_c)

    student_d = get_user_model().objects.create(
        username='student.d',
        first_name='Student',
        last_name='D',
    )
    student_d.groups.add(students)
    UserProgramme.objects.create(programme=programmes[0], user=student_d)

    tutor_a = get_user_model().objects.create(
        username='tutor.a',
        first_name='Tutor',
        last_name='A',
    )
    tutor_a.groups.add(tutors)

    tutor_b = get_user_model().objects.create(
        username='tutor.b',
        first_name='Tutor',
        last_name='B',
    )
    tutor_b.groups.add(tutors)
    UserProgramme.objects.create(programme=programmes[1], user=tutor_b)
    UserProgramme.objects.create(programme=programmes[2], user=tutor_b)

    inactive = get_user_model().objects.create(
        username='inactive',
        first_name='In',
        last_name='Active',
        is_active=False
    )

    return [admin, tyrion, sansa, arya, student_a, tutor_a, student_b, tutor_b, student_c, student_d, inactive]


@pytest.fixture
def announcements(users, programmes, scheduled_courses, scheduled_course_groups, tnow):
    admin = users[0]
    a1 = Announcement.objects.create(
        subject='subject 01 (to all)',
        body='body 1',
        audience='all',
        visible_from=tnow - timedelta(seconds=1),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a2 = Announcement.objects.create(
        subject='subject 02 (Urgent! - to all)',
        body='body 2',
        audience='all',
        is_urgent=True,
        visible_from=tnow - timedelta(seconds=3),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a3 = Announcement.objects.create(
        subject='subject 03 (to students)',
        body='body 3',
        audience='students',
        visible_from=tnow - timedelta(seconds=2),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a4 = Announcement.objects.create(
        subject='subject 04 (to students and tutors)',
        body='body 4',
        audience='students_and_tutors',
        visible_from=tnow - timedelta(seconds=5),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a5 = Announcement.objects.create(
        subject='subject 05 (to tutors)',
        body='body 5',
        audience='tutors',
        visible_from=tnow - timedelta(seconds=4),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a6 = Announcement.objects.create(
        subject='subject 06 (to students on programme 1)',
        body='body 6',
        audience='students',
        programme=programmes[0],
        visible_from=tnow - timedelta(seconds=7),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a7 = Announcement.objects.create(
        subject='subject 07 (to tutors on programme 2)',
        body='body 7',
        audience='tutors',
        programme=programmes[1],
        visible_from=tnow - timedelta(seconds=6),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a8 = Announcement.objects.create(
        subject='subject 08 (to students and tutors on programme 3)',
        body='body 8',
        audience='students_and_tutors',
        programme=programmes[2],
        visible_from=tnow - timedelta(seconds=9),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a9 = Announcement.objects.create(
        subject='subject 09 (visible from yesterday)',
        body='body 9',
        audience='students',
        visible_from=tnow - timedelta(days=1),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    a10 = Announcement.objects.create(
        subject='subject 10 (visible from yesterday)',
        body='body 10',
        audience='students',
        visible_from=tnow - timedelta(days=1, seconds=1),
        visible_to=tnow + timedelta(days=1),
        user=admin
    )
    return [a1, a2, a3, a4, a5, a6, a7, a8, a9, a10]


@pytest.fixture
def user_announcements(users, announcements):
    tyrion = users[1]
    sansa = users[2]
    ua1a = UserAnnouncement.objects.create(
        announcement=announcements[0],
        user=tyrion
    )
    ua1b = UserAnnouncement.objects.create(
        announcement=announcements[1],
        user=tyrion
    )
    ua1c = UserAnnouncement.objects.create(
        announcement=announcements[2],
        user=tyrion
    )
    ua2a = UserAnnouncement.objects.create(
        announcement=announcements[0],
        user=sansa
    )
    return [ua1a, ua1b, ua1c, ua2a]


@pytest.fixture
def announcements_with_recipients(announcements):
    def recipient(a):
        if a.programme is not None:
            return '\n'.join([_('Programme'), a.programme.display_name])
        return dict(AUDIENCES).get(a.audience, None)

    return map(lambda a: (a, recipient(a)), announcements)


@pytest.mark.django_db
def test_get_announcement(announcements):
    pk = announcements[3].pk
    announcement = get_announcement(pk)
    assert announcement.subject == 'subject 04 (to students and tutors)'


@pytest.mark.django_db
def test_get_announcement_does_not_exist(announcements):
    assert not get_announcement(99999)


@pytest.mark.django_db
def test_get_announcement_options(programmes, programme_master_courses, master_courses, scheduled_courses, scheduled_course_groups):
    options = get_announcement_options(programmes[0].pk)

    # master courses
    mc = [master_courses[0].pk, master_courses[1].pk, master_courses[2].pk]
    assert sorted(mc) == sorted(options['master_courses'].keys())


@pytest.mark.django_db
def test_get_audiences_and_programmes_returns_audiences(programmes, master_courses, programme_master_courses):
    result = get_audiences_and_programmes()
    assert 'audiences' in result
    assert result['audiences'] == dict(AUDIENCES)


@pytest.mark.django_db
def test_get_audiences_and_programmes_returns_programmes(programmes, master_courses, programme_master_courses):
    result = get_audiences_and_programmes()
    assert 'programmes' in result
    assert sorted(list(result['programmes'].keys())) == sorted(map(lambda p: p.id, programmes))


@pytest.mark.django_db
def test_get_audiences_and_programmes_returns_programme_display_names(programmes, master_courses, programme_master_courses):
    result = get_audiences_and_programmes()
    assert 'programmes' in result

    assert programmes[0].id in result['programmes']
    assert result['programmes'][programmes[0].id].get('display_name') == 'Programme 1'

    assert programmes[1].id in result['programmes']
    assert result['programmes'][programmes[1].id].get('display_name') == 'Programme 2'

    assert programmes[2].id in result['programmes']
    assert result['programmes'][programmes[2].id].get('display_name') == 'Programme 3'

    assert programmes[3].id in result['programmes']
    assert result['programmes'][programmes[3].id].get('display_name') == 'Programme 4'


@pytest.mark.django_db
def test_get_audiences_and_programmes_returns_programme_master_courses(programmes, master_courses, programme_master_courses):
    result = get_audiences_and_programmes()
    assert 'programmes' in result

    assert programmes[0].id in result['programmes']
    assert result['programmes'][programmes[0].id].get('master_course_ids') == [
        programme_master_courses[0].master_course.id,
        programme_master_courses[1].master_course.id,
        programme_master_courses[2].master_course.id,
    ]

    assert programmes[1].id in result['programmes']
    assert result['programmes'][programmes[1].id].get('master_course_ids') == [
        programme_master_courses[3].master_course.id,
        programme_master_courses[4].master_course.id,
    ]

    assert programmes[2].id in result['programmes']
    assert result['programmes'][programmes[2].id].get('master_course_ids') == [
        programme_master_courses[6].master_course.id,
    ]

    assert programmes[3].id in result['programmes']
    assert result['programmes'][programmes[3].id].get('master_course_ids') == []


@pytest.mark.django_db
def test_get_master_courses(master_courses, scheduled_courses):
    result = get_master_courses(list(map(lambda mc: mc.id, master_courses)))
    assert len(result) == 3

    assert master_courses[0].id in result
    assert result[master_courses[0].id] == {
        'display_name': 'Master A',
        'scheduled_course_ids': [scheduled_courses[0].id, scheduled_courses[1].id, scheduled_courses[2].id]
    }

    assert master_courses[1].id in result
    assert result[master_courses[1].id] == {
        'display_name': 'Master B',
        'scheduled_course_ids': [scheduled_courses[3].id, scheduled_courses[4].id]
    }

    assert master_courses[2].id in result
    assert result[master_courses[2].id] == {
        'display_name': 'Master C',
        'scheduled_course_ids': [scheduled_courses[5].id]
    }

    assert master_courses[3].id not in result
    assert master_courses[4].id not in result


@pytest.mark.django_db
def test_get_scheduled_courses(scheduled_courses, scheduled_course_groups):
    result = get_scheduled_courses(list(map(lambda sc: sc.id, scheduled_courses)))
    assert len(result) == 6

    assert scheduled_courses[0].id in result
    assert result[scheduled_courses[0].id] == {
        'display_name': 'A001',
        'scheduled_course_group_ids': [scheduled_course_groups[0].id, scheduled_course_groups[1].id, scheduled_course_groups[2].id]
    }

    assert scheduled_courses[1].id in result
    assert result[scheduled_courses[1].id] == {
        'display_name': 'A002',
        'scheduled_course_group_ids': [scheduled_course_groups[3].id, scheduled_course_groups[4].id, scheduled_course_groups[5].id]
    }

    assert scheduled_courses[2].id in result
    assert result[scheduled_courses[2].id] == {
        'display_name': 'A003',
        'scheduled_course_group_ids': [scheduled_course_groups[6].id]
    }

    assert scheduled_courses[3].id in result
    assert result[scheduled_courses[3].id] == {
        'display_name': 'B001',
        'scheduled_course_group_ids': []
    }

    assert scheduled_courses[4].id in result
    assert result[scheduled_courses[4].id] == {
        'display_name': 'B002',
        'scheduled_course_group_ids': []
    }

    assert scheduled_courses[5].id in result
    assert result[scheduled_courses[5].id] == {
        'display_name': 'C001',
        'scheduled_course_group_ids': []
    }


@pytest.mark.django_db
def test_get_scheduled_course_groups(scheduled_course_groups):
    result = get_scheduled_course_groups(map(lambda sc: sc.id, scheduled_course_groups))
    assert len(result) == len(scheduled_course_groups)
    assert all(map(lambda scg: scg.id in result, scheduled_course_groups))
    assert sorted(map(lambda scg: scg.display_name, scheduled_course_groups)) == sorted([
        'A001/A',
        'A001/B',
        'A001/C',
        'A002/A',
        'A002/B',
        'A002/C',
        'A003/A',
    ])


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_user_with_multiple_read_announcements(mock_requests, users, user_announcements):
    tyrion = users[1]
    assert tyrion.first_name == 'Tyrion'
    visible_announcements = list(get_visible_announcements_for_user(tyrion, now()))
    assert len(visible_announcements) == 2
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_out_of_visible_datetime_range(mock_requests, users, user_announcements):
    tyrion = users[1]
    assert tyrion.first_name == 'Tyrion'

    visible_announcements = list(get_visible_announcements_for_user(tyrion, now() - timedelta(hours=1)))
    assert len(visible_announcements) == 0

    visible_announcements = list(get_visible_announcements_for_user(tyrion, now() + timedelta(hours=1)))
    assert len(visible_announcements) == 2
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
    ]

    visible_announcements = list(get_visible_announcements_for_user(tyrion, now() + timedelta(days=1, minutes=1)))
    assert len(visible_announcements) == 0


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_user_with_one_read_announcements(mock_requests, users, user_announcements):
    sansa = users[2]
    assert sansa.first_name == 'Sansa'
    visible_announcements = list(get_visible_announcements_for_user(sansa, now()))
    assert len(visible_announcements) == 2
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_user_with_no_read_announcements(mock_requests, users, user_announcements):
    arya = users[3]
    assert arya.first_name == 'Arya'
    visible_announcements = list(get_visible_announcements_for_user(arya, now()))
    assert len(visible_announcements) == 2
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_student(mock_requests, users, user_announcements):
    student_a = users[4]
    assert student_a.username == 'student.a'
    visible_announcements = list(get_visible_announcements_for_user(student_a, now()))
    assert len(visible_announcements) == 6
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
        'subject 03 (to students)',
        'subject 04 (to students and tutors)',
        'subject 09 (visible from yesterday)',
        'subject 10 (visible from yesterday)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_urgent_visible_announcements_for_student(mock_requests, users, user_announcements):
    student_a = users[4]
    assert student_a.username == 'student.a'
    visible_announcements = list(get_visible_announcements_for_user(student_a, now(), urgent_only=True))
    assert len(visible_announcements) == 1
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 02 (Urgent! - to all)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_tutor(mock_requests, users, user_announcements):
    tutor_a = users[5]
    assert tutor_a.username == 'tutor.a'
    visible_announcements = list(get_visible_announcements_for_user(tutor_a, now()))
    assert len(visible_announcements) == 4
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
        'subject 04 (to students and tutors)',
        'subject 05 (to tutors)',
    ]


@patch('programmes.domain.requests')
@pytest.mark.django_db
def test_get_visible_announcements_for_student_on_programme(mock_requests, users, user_announcements):
    student_b = users[6]
    assert student_b.username == 'student.b'
    visible_announcements = list(get_visible_announcements_for_user(student_b, now()))
    assert len(visible_announcements) == 8
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
        'subject 03 (to students)',
        'subject 04 (to students and tutors)',
        'subject 06 (to students on programme 1)',
        'subject 08 (to students and tutors on programme 3)',
        'subject 09 (visible from yesterday)',
        'subject 10 (visible from yesterday)',
    ]


@pytest.mark.django_db
def test_get_visible_announcements_for_tutor_on_programme(users, user_announcements):
    tutor_b = users[7]
    assert tutor_b.username == 'tutor.b'
    visible_announcements = list(get_visible_announcements_for_user(tutor_b, now()))
    assert len(visible_announcements) == 6
    assert sorted(map(lambda announcement: announcement.subject, visible_announcements)) == [
        'subject 01 (to all)',
        'subject 02 (Urgent! - to all)',
        'subject 04 (to students and tutors)',
        'subject 05 (to tutors)',
        'subject 07 (to tutors on programme 2)',
        'subject 08 (to students and tutors on programme 3)',
    ]


@pytest.mark.django_db
def test_get_announcements_marked_read_for_user_with_no_read_announcements(users, announcements, user_announcements):
    student_a = users[4]
    assert student_a.username == 'student.a'

    all_announcements = list(announcements)
    assert len(all_announcements) > 0

    marked_read = get_announcements_marked_read_for_user(all_announcements, student_a)
    filtered_list = list(filter(lambda d: d['marked_read'] is not None, marked_read))
    assert len(filtered_list) == 0


@pytest.mark.django_db
def test_get_announcements_marked_read_for_user_with_one_read_announcement(users, announcements, user_announcements):
    sansa = users[2]
    assert sansa.first_name == 'Sansa'

    all_announcements = list(announcements)
    assert len(all_announcements) > 1

    marked_read = get_announcements_marked_read_for_user(all_announcements, sansa)
    filtered_list = list(filter(lambda d: d['marked_read'] is not None, marked_read))
    assert len(filtered_list) == 1

    assert list(map(lambda d: d['id'], filtered_list)) == [
        user_announcements[3].announcement.id,
    ]


@pytest.mark.django_db
def test_get_announcements_marked_read_for_user_with_three_read_announcements(users, announcements, user_announcements):
    tyrion = users[1]
    assert tyrion.first_name == 'Tyrion'

    all_announcements = list(announcements)
    assert len(all_announcements) > 2

    marked_read = get_announcements_marked_read_for_user(all_announcements, tyrion, limit=999)
    filtered_list = list(filter(lambda d: d['marked_read'] is not None, marked_read))
    assert len(filtered_list) == 3

    assert list(map(lambda d: d['id'], filtered_list)) == [
        user_announcements[0].announcement.id,
        user_announcements[1].announcement.id,
        user_announcements[2].announcement.id,
    ]


@pytest.mark.django_db
def test_get_announcements_marked_read_for_user_when_exceeds_limit_1(users, announcements, user_announcements):
    tyrion = users[1]
    assert tyrion.first_name == 'Tyrion'

    all_announcements = list(announcements)
    assert len(all_announcements) == 10

    limit = 9
    list_items = list(get_announcements_marked_read_for_user(all_announcements, tyrion, limit=limit))
    assert len(list_items) == limit

    assert list(map(lambda d: d['id'], list_items)) == [
        announcements[0].id,  # read and not urgent
        announcements[1].id,  # read, but urgent so always included
                              # [2] is omitted as it is read, but not urgent
        announcements[3].id,  # unread, so always included
        announcements[4].id,  # unread, so always included
        announcements[5].id,  # unread, so always included
        announcements[6].id,  # unread, so always included
        announcements[7].id,  # unread, so always included
        announcements[8].id,  # unread, so always included
        announcements[9].id,  # unread, so always included
    ]


@pytest.mark.django_db
def test_get_announcements_marked_read_for_user_when_exceeds_limit_2(users, announcements, user_announcements):
    tyrion = users[1]
    assert tyrion.first_name == 'Tyrion'

    all_announcements = list(announcements)
    assert len(all_announcements) == 10

    limit = 1
    list_items = list(get_announcements_marked_read_for_user(all_announcements, tyrion, limit=limit))
    assert len(list_items) == 8  # because seven are unread and one is urgent

    assert list(map(lambda d: d['id'], list_items)) == [
        announcements[1].id,  # read, but urgent so always included
        announcements[3].id,  # unread, so always included
        announcements[4].id,  # unread, so always included
        announcements[5].id,  # unread, so always included
        announcements[6].id,  # unread, so always included
        announcements[7].id,  # unread, so always included
        announcements[8].id,  # unread, so always included
        announcements[9].id,  # unread, so always included
    ]


@pytest.mark.django_db
def test_get_announcements(announcements):
    all_announcements, total = get_announcements()
    assert total == len(announcements)
    assert [a.id for a in all_announcements] == sorted([a.id for a in announcements])


@pytest.mark.django_db
def test_get_announcements_ordered_by_visible_from_descending(announcements):
    o_announcements, total = get_announcements(order='desc', column='visible_from')
    assert total == len(announcements)
    assert [a.id for a in o_announcements] == [a.id for a in sorted(announcements, key=lambda a: a.visible_from, reverse=True)]


@pytest.mark.django_db
def test_get_announcements_ordered_by_visible_from_ascending(announcements):
    o_announcements, total = get_announcements(order='asc', column='visible_from')
    assert total == len(announcements)
    assert [a.id for a in o_announcements] == [a.id for a in sorted(announcements, key=lambda a: a.visible_from)]


@pytest.mark.django_db
def test_get_announcements_ordered_by_announcement_id_descending(announcements):
    o_announcements, total = get_announcements(order='desc', column='announcement_id')
    assert total == len(announcements)
    assert [a.id for a in o_announcements] == [a.id for a in sorted(announcements, key=lambda a: a.id, reverse=True)]


@pytest.mark.django_db
def test_get_announcements_ordered_by_announcement_id_ascending(announcements):
    o_announcements, total = get_announcements(order='asc', column='announcement_id')
    assert total == len(announcements)
    assert [a.id for a in o_announcements] == [a.id for a in sorted(announcements, key=lambda a: a.id)]


@pytest.mark.django_db
def test_get_announcements_ordered_by_recipient_descending(announcements_with_recipients):
    o_announcements, total = get_announcements(order='desc', column='recipient')
    announcements = sorted(announcements_with_recipients, key=lambda a: (snd(a), -fst(a).id), reverse=True)
    assert total == len(announcements)
    assert [a[0].id for a in announcements] == [a.id for a in o_announcements]


@pytest.mark.django_db
def test_get_announcements_ordered_by_recipient_ascending(announcements_with_recipients):
    o_announcements, total = get_announcements(order='asc', column='recipient')
    announcements = sorted(announcements_with_recipients, key=lambda a: (snd(a), fst(a).id))
    assert total == len(announcements)
    assert [a[0].id for a in announcements] == [a.id for a in o_announcements]


@pytest.mark.django_db
def test_get_announcements_with_visible_from_query(announcements, tnow):
    q = (tnow - timedelta(days=1)).strftime('%d/%m/%Y')
    q_announcements, total = get_announcements(q=q)
    assert total == 2
    assert sorted(map(lambda announcement: announcement.subject, q_announcements)) == [
        'subject 09 (visible from yesterday)',
        'subject 10 (visible from yesterday)',
    ]


@pytest.mark.django_db
def test_get_announcements_with_visible_from_query_no_results(announcements, tnow):
    q = (tnow - timedelta(days=2)).strftime('%d/%m/%Y')
    q_announcements, total = get_announcements(q=q)
    assert total == 0
    assert len(q_announcements) == 0


@pytest.mark.django_db
def test_get_announcements_with_subject_query(announcements):
    q = 'tutors'
    q_announcements, total = get_announcements(q=q)
    assert total == 4
    assert sorted(map(lambda announcement: announcement.subject, q_announcements)) == [
        'subject 04 (to students and tutors)',
        'subject 05 (to tutors)',
        'subject 07 (to tutors on programme 2)',
        'subject 08 (to students and tutors on programme 3)',
    ]


@pytest.mark.django_db
def test_get_announcements_with_subject_query_no_results(announcements):
    q = 'Zorb'
    q_announcements, total = get_announcements(q=q)
    assert total == 0
    assert len(q_announcements) == 0


@pytest.mark.django_db
def test_get_announcements_with_body_query(announcements):
    q = 'body 08'
    q_announcements, total = get_announcements(q=q)
    assert total == 1
    assert sorted(map(lambda announcement: announcement.subject, q_announcements)) == [
        'subject 08 (to students and tutors on programme 3)',
    ]


@pytest.mark.django_db
def test_get_announcements_with_body_query_no_results(announcements):
    q = 'body 11'
    q_announcements, total = get_announcements(q=q)
    assert total == 0
    assert len(q_announcements) == 0


@pytest.mark.django_db
def test_get_announcements_with_id_query(announcements, tnow):
    q = 'AN-%d' % announcements[-3].id
    q_announcements, total = get_announcements(q=q)
    assert total == 1
    assert sorted(map(lambda announcement: announcement.subject, q_announcements)) == [
        'subject 08 (to students and tutors on programme 3)',
    ]


@pytest.mark.django_db
def test_get_announcements_with_id_query_no_results(announcements, tnow):
    q = 'AN-%d' % (announcements[-1].id + 1)
    q_announcements, total = get_announcements(q=q)
    assert total == 0
    assert len(q_announcements) == 0


@pytest.mark.django_db
def test_get_announcements_with_combined_query(announcements, tnow):
    q = (tnow - timedelta(seconds=6)).strftime('%d/%m/%Y')
    q += ' body 7 subject 07'
    q_announcements, total = get_announcements(q=q)
    assert total == 1
    assert sorted(map(lambda announcement: announcement.subject, q_announcements)) == [
        'subject 07 (to tutors on programme 2)'
    ]


@pytest.mark.django_db
def test_get_announcements_limited(announcements):
    l_announcements, total = get_announcements(limitfrom=3, limitnum=4)
    assert len(l_announcements) == 4
    assert total == len(announcements)
    assert [a.id for a in l_announcements] == sorted([a.id for a in announcements])[3:7]


@pytest.mark.django_db
def test_get_announcement_recipients_all(announcements, users):
    all = announcements[0]
    assert all.subject == 'subject 01 (to all)'

    recipients = get_announcement_recipients(all)
    usernames = sorted([u.username for u in users if u.username != 'inactive'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_students(announcements, users):
    students = announcements[2]
    assert students.subject == 'subject 03 (to students)'

    recipients = get_announcement_recipients(students)
    usernames = sorted(['student.a', 'student.b', 'student.c', 'student.d'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_tutors_and_students(announcements, users):
    students_and_tutors = announcements[3]
    assert students_and_tutors.subject == 'subject 04 (to students and tutors)'

    recipients = get_announcement_recipients(students_and_tutors)
    usernames = sorted(['student.a', 'student.b', 'student.c', 'student.d', 'tutor.a', 'tutor.b'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_tutors(announcements, users):
    tutors = announcements[4]
    assert tutors.subject == 'subject 05 (to tutors)'

    recipients = get_announcement_recipients(tutors)
    usernames = sorted(['tutor.a', 'tutor.b'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_students_on_programme_1(announcements, users):
    students_p1 = announcements[5]
    assert students_p1.subject == 'subject 06 (to students on programme 1)'

    recipients = get_announcement_recipients(students_p1)
    usernames = sorted(['student.b', 'student.c', 'student.d'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_tutors_on_programme_2(announcements, users):
    tutors_p2 = announcements[6]
    assert tutors_p2.subject == 'subject 07 (to tutors on programme 2)'

    recipients = get_announcement_recipients(tutors_p2)
    usernames = sorted(['tutor.b'])
    assert usernames == sorted([r.username for r in recipients])


@pytest.mark.django_db
def test_get_announcement_recipients_students_and_tutors_on_programme_3(announcements, users):
    students_and_tutors_p3 = announcements[7]
    assert students_and_tutors_p3.subject == 'subject 08 (to students and tutors on programme 3)'

    recipients = get_announcement_recipients(students_and_tutors_p3)
    usernames = sorted(['student.b', 'tutor.b'])
    assert usernames == sorted([r.username for r in recipients])
