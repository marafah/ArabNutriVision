from django.conf import settings
from django.urls import path

from . import views

app_name = "nutrition"

urlpatterns = [
    path("", views.home, name="home"),
    path("research/", views.research, name="research"),
    path("analyze/", views.analyze, name="analyze"),
    path("dishes/", views.dish_list, name="dishes"),
    path("dishes/new/", views.recipe_builder, name="recipe_builder"),
    path("dishes/<slug:code>/", views.dish_detail, name="dish_detail"),
    path("workspace/", views.dashboard, name="dashboard"),
    path("participants/", views.participant_list, name="participants"),
    path("participants/<int:pk>/", views.participant_detail, name="participant_detail"),
    path("records/<int:pk>/", views.record_detail, name="record_detail"),
    path("records/<int:pk>/delete/", views.record_delete, name="record_delete"),
    path("records/<int:pk>/export.csv", views.record_csv, name="record_csv"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),
    path("supplements/<int:pk>/delete/", views.supplement_delete, name="supplement_delete"),
    path("ffq/", views.ffq_import, name="ffq"),
    path("ffq/template.csv", views.ffq_template, name="ffq_template"),
    path("validation/", views.validation_lab, name="validation"),
    path("validation/annotations.csv", views.validation_csv, name="validation_csv"),
    path("validation/<int:pk>/delete/", views.validation_delete, name="validation_delete"),
    path("api/add-item/", views.api_add_item, name="api_add_item"),
]

if settings.STATIC_SITE:   # static edition: researcher pages are client-side (Supabase)
    from . import static_views as sv
    _swap = {"dashboard": sv.dashboard, "participants": sv.participants, "ffq": sv.ffq, "validation": sv.validation, "recipe_builder": sv.recipe_builder}
    for _u in urlpatterns:
        if _u.name in _swap:
            _u.callback = _swap[_u.name]
    urlpatterns += [path("participants/view/", sv.participant_view, name="participant_view"),
                    path("records/view/", sv.record_view, name="record_view"),
                    path("inbody/", sv.inbody, name="inbody")]
