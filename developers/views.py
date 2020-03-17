from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from developers.models import Developer


class DeveloperMixin(LoginRequiredMixin):
    model = Developer
    variable = 'commit'
    label = 'Commits'
    throughput_lower_threshold = 0.5
    throughput_higher_threshold = 0.5
    churn_lower_threshold = 0.5
    churn_higher_threshold = 0.5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['throughput_lower_threshold'] = self.throughput_lower_threshold
        context['throughput_higher_threshold'] = self.throughput_higher_threshold
        context['churn_lower_threshold'] = self.churn_lower_threshold
        context['churn_higher_threshold'] = self.churn_higher_threshold
        return context

class DeveloperList(DeveloperMixin, ListView):
    context_object_name = 'developer_list'
    paginate_by = 10