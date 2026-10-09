from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.po_list, name="po_list"),
    path("table/", views.po_table_partial, name="po_table_partial"),
    path("export.xlsx", views.po_export, name="po_export"),
    # Multi-segment PO routes before the catch-all detail route.
    path("<str:po_no>/ta/", views.po_ta_partial, name="po_ta_partial"),
    path("<str:po_no>/curves.json", views.po_curves_json, name="po_curves_json"),
    path("<str:po_no>/whatif/", views.po_whatif_partial, name="po_whatif_partial"),
    path("<str:po_no>/comments/", views.po_comment_create, name="po_comment_create"),
    # Catch-all detail MUST stay last.
    path("<str:po_no>/", views.po_detail, name="po_detail"),
]
