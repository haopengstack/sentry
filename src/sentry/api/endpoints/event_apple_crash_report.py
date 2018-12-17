from __future__ import absolute_import

import six

try:
    from django.http import (
        HttpResponse,
        CompatibleStreamingHttpResponse as StreamingHttpResponse)
except ImportError:
    from django.http import HttpResponse, StreamingHttpResponse

from sentry.api.base import Endpoint
from sentry.api.bases.group import GroupPermission
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.models import Event
from sentry.lang.native.applecrashreport import AppleCrashReport
from sentry.utils.safe import get_path


class EventAppleCrashReportEndpoint(Endpoint):
    permission_classes = (GroupPermission, )

    def get(self, request, event_id):
        """
        Retrieve an Apple Crash Report from and event
        `````````````````````````````````````````````

        This endpoint returns the an apple crash report for a specific event.
        The event ID is the event as it appears in the Sentry database
        and not the event ID that is reported by the client upon submission.
        This works only if the event.platform == cocoa
        """
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            raise ResourceDoesNotExist

        self.check_object_permissions(request, event.group)

        Event.objects.bind_nodes([event], 'data')

        if event.platform not in ('cocoa', 'native'):
            return HttpResponse(
                {
                    'message': 'Only cocoa events can return an apple crash report',
                }, status=403
            )

        symbolicated = (request.GET.get('minified') not in ('1', 'true'))

        apple_crash_report_string = six.text_type(
            AppleCrashReport(
                threads=get_path(event.data, 'threads', 'values', filter=True),
                context=event.data.get('contexts'),
                debug_images=get_path(event.data, 'debug_meta', 'images', filter=True),
                exceptions=get_path(event.data, 'exception', 'values', filter=True),
                symbolicated=symbolicated,
            )
        )

        response = HttpResponse(apple_crash_report_string,
                                content_type='text/plain')

        if request.GET.get('download') is not None:
            filename = u"{}{}.crash".format(
                event.event_id, symbolicated and '-symbolicated' or '')
            response = StreamingHttpResponse(
                apple_crash_report_string,
                content_type='text/plain',
            )
            response['Content-Length'] = len(apple_crash_report_string)
            response['Content-Disposition'] = 'attachment; filename="%s"' % filename

        return response
