from datetime import datetime, time
from functools import partial, reduce
from itertools import groupby

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.db.models import Count, Q, Case, When, Value
from django.db.models.functions import Concat
from django.utils.timezone import now, make_aware
from django.utils.translation import gettext as _

from rest_framework.exceptions import PermissionDenied

from .models import AUDIENCES
from programmes.domain import get_scheduled_course_and_group_memberships_from_cache, course_and_group_memberships_cache_key
from programmes.models import Programme, ProgrammeMasterCourse, MasterCourse, ScheduledCourse, ScheduledCourseGroup
from announcements.models import Announcement, UserAnnouncement

announcement_id_prefix = 'AN-'

announcement_chars_truncate = 80


def fst(list):
    return list[0]


def snd(list):
    return list[1]


def add_announcement(announcement_serializer, user):
    if announcement_serializer.is_valid(raise_exception=True):
        announcement_serializer.save()


def update_announcement(announcement_serializer, user):
    if announcement_serializer.is_valid(raise_exception=True):
        announcement_serializer.save()


def get_announcement(pk):
    try:
        announcement = Announcement.objects.get(pk=pk)
        announcement.display_id = "%s%d" % (announcement_id_prefix, announcement.id)
        return announcement
    except Announcement.DoesNotExist:
        return None


def delete_announcement(announcement, user):
    announcement.delete()


def get_announcement_options(programme_id):
    master_courses = []
    scheduled_courses = []
    scheduled_course_groups = []

    if programme_id:
        master_course_ids = ProgrammeMasterCourse \
            .objects \
            .filter(programme_id=programme_id) \
            .values_list('master_course_id', flat=True) \
            .distinct()

        master_courses = get_master_courses(master_course_ids)

    return {
        'master_courses': master_courses,
        'scheduled_courses': scheduled_courses,
        'scheduled_course_groups': scheduled_course_groups
    }


def get_audiences_and_programmes():
    # get audiences, programmes, programme master courses
    audiences = dict(AUDIENCES)
    programmes = dict(Programme.objects.values_list('id', 'display_name'))
    for k, v in programmes.items():
        programmes[k] = {
            'display_name': programmes[k],
            'master_course_ids': []
        }
    programme_master_courses = ProgrammeMasterCourse \
        .objects \
        .filter(available=True) \
        .order_by('programme_id', 'master_course_id') \
        .values_list('programme_id', 'master_course_id') \
        .distinct()

    # set the list of master course ids on each programme
    for k, g in groupby(programme_master_courses, fst):
        if k in programmes:
            programmes[k]['master_course_ids'] = list(map(snd, g))

    # return dict
    return {
        'audiences': audiences,
        'programmes': programmes,
    }


def get_master_courses(master_course_ids):
    # get master courses, scheduled courses
    master_courses = dict(
        MasterCourse.objects
        .annotate(scheduled_course_count=Count('scheduledcourse'))
        .filter(scheduled_course_count__gt=0)
        .filter(id__in=master_course_ids)
        .values_list('id', 'display_name')
    )
    for k, v in master_courses.items():
        master_courses[k] = {
            'display_name': master_courses[k],
            'scheduled_course_ids': []
        }
    scheduled_courses = ScheduledCourse \
        .objects \
        .filter(master_course_id__in=master_course_ids) \
        .order_by('master_course_id', 'id') \
        .values_list('master_course_id', 'id')

    # set the list of scheduled course ids on each master course
    for k, g in groupby(scheduled_courses, fst):
        if k in master_courses:
            master_courses[k]['scheduled_course_ids'] = list(map(snd, g))

    # return dict
    return master_courses


def get_scheduled_courses(scheduled_course_ids):
    # get scheduled courses, scheduled course groups
    scheduled_courses = dict(
        ScheduledCourse.objects
        .filter(id__in=scheduled_course_ids)
        .values_list('id', 'display_name')
    )
    for k, v in scheduled_courses.items():
        scheduled_courses[k] = {
            'display_name': scheduled_courses[k],
            'scheduled_course_group_ids': []
        }
    scheduled_course_groups = ScheduledCourseGroup \
        .objects \
        .filter(scheduled_course_id__in=scheduled_course_ids) \
        .order_by('scheduled_course_id', 'id') \
        .values_list('scheduled_course_id', 'id')

    # set the list of scheduled course group ids on each scheduled course
    for k, g in groupby(scheduled_course_groups, fst):
        if k in scheduled_courses:
            scheduled_courses[k]['scheduled_course_group_ids'] = list(map(snd, g))

    # return dict
    return scheduled_courses


def get_scheduled_course_groups(scheduled_course_group_ids):
    return dict(
        ScheduledCourseGroup.objects
        .filter(id__in=scheduled_course_group_ids)
        .values_list('id', 'display_name')
    )


def get_visible_announcements_for_user(user, current_datetime, urgent_only=False):
    # all announcements within the visible datetime range
    announcements = Announcement \
        .objects \
        .filter(visible_from__lte=current_datetime, visible_to__gte=current_datetime) \
        .select_related('programme') \
        .order_by('-is_urgent', '-visible_from')

    if urgent_only:
        announcements = announcements.filter(is_urgent=True)

    # announcements visible to a specific group
    announcements = filter(
        partial(_audience, user=user),
        announcements
    )

    # announcements visible to a specific programme
    announcements = filter(
        partial(_programme, user=user),
        announcements
    )

    return announcements


def get_announcements_marked_read_for_user(visible_announcements, user, limit=30):
    user_announcements = UserAnnouncement \
        .objects \
        .filter(user=user) \
        .filter(announcement__id__in=list(map(lambda va: va.id, visible_announcements)))

    def to_dict(visible_announcement):
        user_announcement = user_announcements.get(announcement=visible_announcement) \
            if user_announcements.filter(announcement=visible_announcement).exists() \
            else None
        modified = visible_announcement.modified \
            if visible_announcement.modified > visible_announcement.created \
            else None
        return {
            'id': visible_announcement.id,
            'subject': visible_announcement.subject,
            'body': visible_announcement.body,
            'visible_from': visible_announcement.visible_from,
            'is_urgent': visible_announcement.is_urgent,
            'modified': modified,
            'marked_read': None if user_announcement is None else user_announcement.created,
        }

    def always_include(user_announcement):
        return user_announcement['is_urgent'] or user_announcement['marked_read'] is None

    all_announcements = list(map(to_dict, visible_announcements))
    extra_limit = max(0, limit - len(list(filter(always_include, all_announcements))))

    def f(user_announcement):
        always_inc = always_include(user_announcement)
        if not always_inc:
            f.extra_count += 1
        return always_inc or f.extra_count <= extra_limit
    f.extra_count = 0

    return filter(f, all_announcements)


def mark_announcement_read_for_user(announcement_id, user):
    user_announcement, created = UserAnnouncement.objects.get_or_create(
        announcement_id=announcement_id,
        user=user
    )
    user_announcement.created = now()
    user_announcement.save()
    return {
        'id': announcement_id,
        'subject': user_announcement.announcement.subject,
        'body': user_announcement.announcement.body,
        'visible_from': user_announcement.announcement.visible_from,
        'is_urgent': user_announcement.announcement.is_urgent,
        'modified': user_announcement.announcement.modified,
        'marked_read': user_announcement.created
    }


def mark_announcement_unread_for_user(announcement_id, user):
    UserAnnouncement.objects.filter(
        announcement_id=announcement_id,
        user=user
    ).delete()


def get_announcements(column='', order='', q='', limitfrom=None, limitnum=None):
    # ordering
    order_by = _get_order_by(column, order)

    # create a Q object from the query string
    q_object = reduce(lambda acc, _q: acc & _get_q_filter(_q), q.split(' '), Q())

    announcements = Announcement\
        .objects \
        .filter(q_object) \
        .select_related('programme') \
        .annotate(
            recipient=Case(
                *_get_recipient_as_conditional_expressions(),
                default='audience'
            ),
            display_id=Concat(Value(announcement_id_prefix), 'id')
        ) \
        .order_by(*order_by)

    total = announcements.count()

    # apply limit and offset
    if limitfrom is not None or limitnum is not None:
        start = int(limitfrom) if limitfrom else 0
        end = int(limitnum) + start if limitnum else total
        announcements = announcements[start:end]

    return announcements, total


def get_announcement_recipients(announcement):

    # all active users
    queryset = get_user_model().objects.filter(is_active=True)

    # filter by audience
    queryset = _audience_users(announcement, queryset)

    # filter by programme
    queryset = _programme_users(announcement, queryset)

    return queryset


def _audience(announcement, user):
    if announcement.audience == 'all':
        return True

    group_names = user.groups.values_list('name', flat=True)
    audiences = filter(lambda audience: audience != 'and', announcement.audience.split('_'))
    return any(map(lambda audience: audience in group_names, audiences))


def _programme(announcement, user):
    return True if announcement.programme is None else announcement \
        .programme \
        .userprogramme_set \
        .filter(user=user) \
        .exists()


def _course(announcement, user, memberships):
    if announcement.scheduled_course is None:
        return True

    c = announcement.scheduled_course.vle_course_id
    cache = caches['default']
    data = cache.get(course_and_group_memberships_cache_key)
    return False if data is None or c not in data or 'members' not in data[c] or user.username not in data[c]['members'] else True


def _group(announcement, user, memberships):
    if announcement.group is None:
        return True

    c = announcement.scheduled_course.vle_course_id
    v = announcement.group.vle_group_id
    cache = caches['default']
    data = cache.get(course_and_group_memberships_cache_key)
    return False if data is None or c not in data or 'groups' not in data[c] or v not in data[c]['groups'] or user.username not in data[c]['groups'][v] else True


def _get_order_by(column, order=None):
    orderable = {
        'announcement_id': 'id',
        'recipient': 'recipient',
        'visible_from': 'visible_from'
    }
    column = column if column in orderable else 'announcement_id'
    order = '-' if order == 'desc' else ''
    order_by = ['%s%s' % (order, orderable[column])]
    if column != 'announcement_id':
        order_by.append('id')
    return order_by


def _get_q_filter(q):
    query = Q()

    # visible from date
    dt = _parse_q_date(q)
    if dt:
        query |= Q(visible_from__range=(
            make_aware(datetime.combine(dt.date(), time.min)),
            make_aware(datetime.combine(dt.date(), time.max))
        ))

    # announcement id
    if q.lower().startswith(announcement_id_prefix.lower()):
        query |= Q(id__istartswith=q[len(announcement_id_prefix):])

    # subject and body
    query |= Q(subject__icontains=q) | Q(body__icontains=q)

    return query


def _parse_q_date(q):
    try:
        return datetime.strptime(q, '%d/%m/%Y')
    except ValueError:
        return ''


def _get_recipient_as_conditional_expressions():
    exp = [
        When(programme__isnull=False, then=Concat(
            Value(_('Programme')), 'programme__display_name',
        )),
    ]
    exp += map(lambda a: When(audience=fst(a), then=Value(snd(a))), AUDIENCES)
    return exp


def _concat_recipient_value(rs):
    rs = (lambda rs, i: rs[:i] + [Value('\n')] + rs[i:], range(1, (len(rs) * 2) - 1, 2), rs)
    return Concat(*rs)


def _audience_users(announcement, queryset):
    if announcement.audience == 'all':
        return queryset

    groups = filter(lambda audience: audience != 'and', announcement.audience.split('_'))
    return queryset.filter(groups__name__in=groups, is_active=True)


def _programme_users(announcement, queryset):
    if announcement.programme is None:
        return queryset

    return queryset.filter(userprogramme__programme_id=announcement.programme)


def _course_users(announcement, queryset, memberships):
    if announcement.scheduled_course is None:
        return queryset

    c = announcement.scheduled_course.vle_course_id
    members = [] if c not in memberships or 'members' not in memberships[c] else memberships[c]['members']
    return queryset.filter(username__in=members)


def _group_users(announcement, queryset, memberships):
    if announcement.group is None:
        return queryset

    c = announcement.scheduled_course.vle_course_id
    v = announcement.group.vle_group_id
    members = [] if c not in memberships or 'groups' not in memberships[c] or v not in memberships[c]['groups'] else memberships[c]['groups'][v]
    return queryset.filter(username__in=members)
