from django.http import FileResponse, Http404
import os
from django.conf import settings

def serve_pdf(request, filename):
    file_path = os.path.join(settings.MEDIA_ROOT, filename)
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['X-Frame-Options'] = 'ALLOWALL'
        return response
    else:
        raise Http404("PDF not found.")