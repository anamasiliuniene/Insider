from django.http import HttpResponse

def home(request):
    return HttpResponse("Insider app is running.")