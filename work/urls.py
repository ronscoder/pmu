from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views
app_name = 'work'
urlpatterns = [
    path('', views.index, name='index'),
    path('detail', views.detail, name='detail'),
    path('review/<int:pid>/<int:additional>', views.review, name='review'),
    path('resolution', views.resolution, name='resolution'),
    path('update_progress/', views.updateProgress, name="updateProgress"),
    path('undoextra/', views.undoextra, name="undoextra"),
    path('addSite/', views.addSite, name="addSite"),
    path('reloadSurveyData/', views.uploadSurvey, name='uploadSurvey'),
    path('loadDprQty/', views.loadDprQty, name='loadDprQty'),
    # path('loadDprHH/', views.loadDprHH, name='loadDprHH'),
    path('downloadFile/', views.downloadFile, name='downloadFile',),
    path('progress/<int:site_id>', views.progress, name='progress',),
    path('shifted/<int:site_id>', views.shifted, name='shifted',),
    path('resolutionlinkedpage/<int:id>', views.resolutionlinkedpage, name='resolutionlinkedpage',),

    # API's
    path('api_data/', views.api_data, name='api_data',),
    path('api_uploadDoc/', views.api_uploadDoc, name='api_uploadDoc',),
    path('api_deleteDoc/<str:model>/<int:id>', views.api_deleteDoc, name='api_deleteDoc',),
    path('api_validate_progress/', views.api_validate_progress, name='api_validate_progress',),
    path('api_getSite/', views.api_getSite, name='api_getSite',),
    path('api_markVariations', views.api_markVariations, name='api_markVariations',),
    path('api_markSiteOrigin', views.api_markSiteOrigin, name='api_markSiteOrigin',),
    path('api_mergeToSite', views.api_mergeToSite, name='api_mergeToSite',),
    path('api_load_review', views.api_load_review, name='api_load_review',),
    path('api_updateExecQty', views.api_updateExecQty, name='api_updateExecQty',),
    path('api_create_resolution_link', views.api_create_resolution_link, name='api_create_resolution_link',)
] 
# + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


from django.contrib import admin

admin.site.site_header = 'Project Monitoring'                    # default: "Django Administration"
admin.site.index_title = 'PMU Data Admin'                 # default: "Site administration"
admin.site.site_title = 'PMU Data Admin' # default: "Django site admin"