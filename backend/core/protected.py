"""Serving files that are not public.

Uploaded files must not sit under a URL the web server hands out on request. The
register holds expert reports, letters to owners and photographs that were never
released, all in the same media root as a released photo, so a public
``/media/`` location would publish them by accident.

Every download therefore goes through a view that authorises the caller first.
The file itself is then handed to the web server to send, so authorisation costs
a request but the transfer does not go through Python.
"""

from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from urllib.parse import quote


def serve_protected_file(file_field, as_attachment=False, filename=None):
    """Return a response delivering ``file_field`` to an authorised caller.

    The caller is responsible for having checked that this person may have this
    file. Three delivery paths, in order of preference:

    1. object storage: redirect to a signed URL, which requires
       ``AWS_QUERYSTRING_AUTH`` to be on, or the bucket would be public anyway;
    2. behind a web server: hand the path over via ``X-Accel-Redirect`` so NGINX
       sends the bytes from its internal location;
    3. development: stream it from Django.
    """
    if getattr(settings, "USE_S3", False):
        # Signed and short-lived, so the URL cannot be passed around.
        return HttpResponseRedirect(file_field.url)

    if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
        response = HttpResponse(status=200)
        location = f"{settings.PROTECTED_MEDIA_LOCATION}{quote(file_field.name)}"
        response["X-Accel-Redirect"] = location
        # Let the web server work out the type and length.
        del response["Content-Type"]
        if as_attachment:
            name = filename or file_field.name.rsplit("/", 1)[-1]
            response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response

    return FileResponse(
        file_field.open("rb"),
        as_attachment=as_attachment,
        filename=filename or file_field.name.rsplit("/", 1)[-1],
    )
