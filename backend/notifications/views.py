from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.notifications.all()


class MarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(request.user.notifications, pk=pk)
        notification.unread = False
        notification.save(update_fields=["unread"])
        return redirect(notification.url or "notifications:list")


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(unread=True).update(unread=False)
        return redirect("notifications:list")
