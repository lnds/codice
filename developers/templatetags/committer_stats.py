# coding=utf-8
import numpy
from django import template

from developers.charts import calc_cx, calc_cy
from developers.services import get_developer_blame_summary

register = template.Library()


@register.simple_tag
def get_blame_stats(commiter, repos, total_blame):
    return get_developer_blame_summary(commiter, repos, total_blame)


R2 = numpy.ma.sqrt(2.0)
RA = 0.75 * R2
RB = 0.50 * R2
RC = 0.25 * R2
RD = 0.0


@register.simple_tag
def get_badge_data(log_impact, churn, self_churn, throughput, work_others, max_churn, max_log_impact):
    context = dict()
    cx = calc_cx(churn, max_churn)
    cy = calc_cy(log_impact, max_log_impact)
    context['cx'] = cx
    context['cy'] = cy
    if not self_churn:
        context['self_churn_color'] = 'text-success'
    elif 0 <= self_churn <= 0.10:
        context['self_churn_color'] = 'text-success'
    elif 0.10 < self_churn <= 0.25:
        context['self_churn_color'] = 'text-warning'
    else:
        context['self_churn_color'] = 'text-danger'

    if not work_others:
        context['work_others_color'] = 'text-info'
    elif work_others <= 0.50:
        context['work_others_color'] = 'text-info'
    else:
        context['work_others_color'] = 'text-warning'

    if throughput < 0.25:
        context['throughput_color'] = 'text-danger'
    elif throughput <= 0.5:
        context['throughput_color'] = 'text-warning'
    else:
        context['throughput_color'] = 'text-success'

    if churn < 0.25:
        context['churn_color'] = 'text-success'
    elif churn <= 0.5:
        context['churn_color'] = 'text-warning'
    else:
        context['churn_color'] = 'text-danger'

    r = numpy.ma.sqrt((1.0-cx)**2+(cy)**2)
    context['r'] = r

    if r > RA:
        context['level'] = 'A'
        context['ratio'] = (r - RA)/(R2-RA)
    elif r > RB:
        context['level'] = 'B'
        context['ratio'] = (r - RB)/(RA-RB)
    elif r > RC:
        context['level'] = 'C'
        context['ratio'] = (r - RC)/(RB-RC)
    else:
        context['level'] = 'D'
        context['ratio'] = (r - RD)/(RC-RD)

    print("cx = {}, cy = {}".format(cx, cy))
    if cx < 0.5:
        if cy < 0.5:
            context['badge'] = 'fa fa-wrench text-info'
            context['badge_2x'] = 'fa fa-2x fa-wrench text-info'
            context['badge_description'] = 'perfectionist'
        else:
            context['badge'] = 'fas fa-fire text-success'
            context['badge_2x'] = 'fas fa-2x fa-fire text-success'
            context['badge_description'] = 'prolific'
    else:
        if cy >= 0.5:
            context['badge'] = 'fa fa-xs fa-bug text-warning'
            context['badge_2x'] = 'fa fa-sm fa-2x fa-bug text-warning'
            context['badge_stack'] = 'fa fa-ban text-danger'
            context['badge_stack_2x'] = 'fa fa-2x fa-ban text-danger'
            context['badge_description'] = 'bug buster'
        else:
            context['badge'] = 'fas fa-flag ' + ('text-danger' if cy < 0.25 and churn > 0.75 else 'text-warning')
            context['badge_2x'] = 'fas fa-2x fa-flag ' + ('text-danger' if cy < 0.25 and churn > 0.75 else 'text-warning')
            context['badge_description'] = 'mantainer'

    return context
