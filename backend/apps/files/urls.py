from django.urls import path

from apps.files import views

urlpatterns = [
    path("list", views.ListView.as_view(), name="files-list"),
    path("content", views.ContentView.as_view(), name="files-content"),
    path("mkdir", views.MkdirView.as_view(), name="files-mkdir"),
    path("move", views.MoveView.as_view(), name="files-move"),
    path("delete", views.DeleteView.as_view(), name="files-delete"),
    path("chmod", views.ChmodView.as_view(), name="files-chmod"),
    path("chown", views.ChownView.as_view(), name="files-chown"),
    path("symlink", views.SymlinkView.as_view(), name="files-symlink"),
    path("download", views.DownloadView.as_view(), name="files-download"),
    path("recycle", views.RecycleView.as_view(), name="files-recycle"),
    path("recycle/restore", views.RecycleRestoreView.as_view(), name="files-recycle-restore"),
    path("recycle/purge", views.RecyclePurgeView.as_view(), name="files-recycle-purge"),
    path("tasks/<str:action>", views.TaskOpView.as_view(), name="files-task"),
    path("uploads", views.UploadCreateView.as_view(), name="files-uploads"),
    path("uploads/<uuid:upload_id>", views.UploadDetailView.as_view(), name="files-upload"),
    path(
        "uploads/<uuid:upload_id>/chunks/<int:index>",
        views.UploadChunkView.as_view(),
        name="files-upload-chunk",
    ),
    path(
        "uploads/<uuid:upload_id>/complete",
        views.UploadCompleteView.as_view(),
        name="files-upload-complete",
    ),
]
