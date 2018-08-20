from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import AnnouncementSerializer, UserAnnouncementSerializer
from .domain import (add_announcement, update_announcement, get_master_courses, get_scheduled_courses,
                     get_scheduled_course_groups, get_visible_announcements_for_user,
                     get_announcements_marked_read_for_user, mark_announcement_read_for_user,
                     mark_announcement_unread_for_user, get_announcements,
                     get_announcement, get_announcement_options, delete_announcement)


@api_view(['POST'])
@csrf_exempt
def add(request):
    announcement_serializer = AnnouncementSerializer(
        data=request.data,
        context={'request': request}
    )
    add_announcement(
        announcement_serializer,
        request.user
    )
    return Response(
        announcement_serializer.data,
        status=HTTP_201_CREATED
    )


@api_view(['PUT'])
def update(request, pk):
    announcement = get_announcement(pk)
    if announcement is None:
        return Response(
            _('Announcement with id %d does not exist') % pk,
            status=HTTP_404_NOT_FOUND
        )
    announcement_serializer = AnnouncementSerializer(
        instance=announcement,
        data=request.data,
        context={'request': request}
    )
    update_announcement(
        announcement_serializer,
        request.user
    )
    return Response(
        announcement.modified,
        status=HTTP_200_OK
    )


@api_view(['DELETE'])
def delete(request, pk):
    announcement = get_announcement(pk)
    if announcement is None:
        return Response(
            _('Announcement with id %d does not exist') % pk,
            status=HTTP_404_NOT_FOUND
        )
    delete_announcement(announcement, request.user)
    return Response(
        None,
        status=HTTP_200_OK
    )


@api_view(['GET'])
def get(request, pk):
    announcement = get_announcement(pk)
    if announcement is None:
        return Response(
            _('Announcement with id %d does not exist') % pk,
            status=HTTP_404_NOT_FOUND
        )

    data = AnnouncementSerializer(announcement).data
    data['options'] = get_announcement_options(
        announcement.programme_id
    )
    return Response(data)


@api_view(['POST'])
def master_courses(request):
    return Response(
        get_master_courses(request.data),
        status=HTTP_200_OK
    )


@api_view(['POST'])
def scheduled_courses(request):
    return Response(
        get_scheduled_courses(request.data),
        status=HTTP_200_OK
    )


@api_view(['POST'])
def scheduled_course_groups(request):
    return Response(
        get_scheduled_course_groups(request.data),
        status=HTTP_200_OK
    )


@api_view(['GET'])
def visible(request):
    visible_announcements = list(get_visible_announcements_for_user(request.user, now()))
    user_announcements = list(get_announcements_marked_read_for_user(
        visible_announcements,
        request.user
    ))
    serializer = UserAnnouncementSerializer(
        user_announcements,
        many=True
    )
    return Response(serializer.data)


@api_view(['GET'])
def count_unread(request):
    visible_announcements = list(get_visible_announcements_for_user(request.user, now()))
    user_announcements = list(get_announcements_marked_read_for_user(
        visible_announcements,
        request.user
    ))
    return Response({
        'announcements': len(list(filter(lambda ua: ua['marked_read'] is None, user_announcements)))
    })


@api_view(['POST'])
def mark_read(request, pk):
    announcement = mark_announcement_read_for_user(pk, request.user)
    serializer = UserAnnouncementSerializer(announcement)
    return Response(
        serializer.data,
        status=HTTP_201_CREATED
    )


@api_view(['DELETE'])
def mark_unread(request, pk):
    mark_announcement_unread_for_user(pk, request.user)
    return Response(
        status=HTTP_204_NO_CONTENT
    )


@api_view(['GET'])
def announcements(request):
    params = request.query_params
    q = params.get('q', '')
    column = params.get('column', '')
    order = params.get('order', '')
    per_page = params.get('per_page', None)
    page = params.get('page', None)

    limitnum = int(per_page) if per_page else None
    limitfrom = (int(page) - 1) * limitnum if page and limitnum else None

    announcements, total = get_announcements(column, order, q, limitfrom, limitnum)
    return Response({
        'announcements': AnnouncementSerializer(many=True, instance=announcements).data,
        'total': total
    })
