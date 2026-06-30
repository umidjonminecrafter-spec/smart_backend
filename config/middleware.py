from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect

class PreservePostRedirectMiddleware:
    """
    Middleware to preserve request method and payload during redirects (e.g. APPEND_SLASH redirects).
    Converts 301 to 308 (Permanent Redirect) and 302 to 307 (Temporary Redirect)
    for POST, PUT, and PATCH requests so that the browser does not convert them to GET requests.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ('POST', 'PUT', 'PATCH') and response.status_code in (301, 302):
            location = response.get('Location', '')
            if location:
                if response.status_code == 301:
                    return HttpResponsePermanentRedirect(location, status=308)
                else:
                    return HttpResponseRedirect(location, status=307)
        return response
