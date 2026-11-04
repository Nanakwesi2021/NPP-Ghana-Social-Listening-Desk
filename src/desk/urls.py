from django.urls import path

from . import views

app_name = "desk"

urlpatterns = [
    path("desk/", views.overview, name="overview"),
    path("desk/part/trends/", views.overview_trends_part, name="overview_trends_part"),
    path("desk/part/queue/", views.overview_queue_part, name="overview_queue_part"),
    path("trends/", views.trend_list, name="trend_list"),
    path("trends/<slug:slug>/", views.trend_detail, name="trend_detail"),
    path("issues/", views.issue_list, name="issue_list"),
    path("issues/new/", views.issue_new, name="issue_new"),
    path("issues/<str:ref>/", views.issue_detail, name="issue_detail"),
    path("issues/<str:ref>/take/", views.issue_take, name="issue_take"),
    path("issues/<str:ref>/release/", views.issue_release, name="issue_release"),
    path("issues/<str:ref>/evidence/", views.issue_evidence, name="issue_evidence"),
    path("issues/<str:ref>/translation/", views.issue_translation, name="issue_translation"),
    path("issues/<str:ref>/finding/", views.issue_finding, name="issue_finding"),
    path("issues/<str:ref>/decision/", views.issue_decision, name="issue_decision"),
    path("issues/<str:ref>/retry-notification/", views.issue_retry_notification, name="issue_retry_notification"),
    path("sources/", views.sources, name="sources"),
    path("sources/submit/", views.source_submit, name="source_submit"),
    path("search/", views.search, name="search"),
    path("sample/role/", views.sample_role, name="sample_role"),
]
