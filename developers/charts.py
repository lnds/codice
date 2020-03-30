import math
from time import mktime

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from commits.models import Commit
from developers.services import get_developer_blame_summary
from files.models import FileChange

def get_devs_blame_data(devs, repos, branches, total_blame):
    blames = []
    for dev in devs:
        blame_stat = get_developer_blame_summary(dev, repos, branches, total_blame)
        if blame_stat:
            blames.append(blame_stat)
    return blames


def get_devs_churn_production_chart(blames):
    xdata = []
    y1data_mbh = []
    y2data_mbh = []
    for blame_stat in blames:
        dev = blame_stat['dev']
        xdata.append(dev.name)
        churn = blame_stat['churn']
        throughput = blame_stat['throughput']
        y1data_mbh.append(-round(abs(churn * 100.0), 2) if churn else 0.0)
        y2data_mbh.append(round(abs(throughput * 100.0), 2) if throughput else 0.0)

    result = dict()
    extra_serie = {"tooltip": {"y_start": "", "y_end": " "}}
    result['data'] = {'x': xdata,
                      'name1': 'Productive', 'y1': y2data_mbh, 'extra2': extra_serie,
                      'name2': 'Churn', 'y2': y1data_mbh, 'extra1': extra_serie,
                      }
    result['extra'] = {'x_is_date': False, 'x_axis_format': '', 'tag_script_js': True, 'jquery_on_ready': False,
                       'show_legend': False, 'show_labels': True, 'stacked': True, 'controls': None,
                       'margin_left': 200, 'color_category': "category10",
                       }
    return result


def get_devs_owner_pie_chart(blames):
    xdata_pie = []
    ydata_pie = []
    for blame_stat in blames:
        dev = blame_stat['dev']
        xdata_pie.append(dev.name)
        ydata_pie.append(blame_stat['ownership'] * 100.0)

    result = dict()
    extra_serie = {"tooltip": {"y_start": "", "y_end": " "}}
    result['data'] = {'x': xdata_pie, 'y1': ydata_pie, 'extra1': extra_serie}
    result['extra'] = {
            'x_is_date': False,
            'x_axis_format': '',
            'tag_script_js': True,
            'jquery_on_ready': False,
            'donut': True,
            'show_legend': False,
            'show_labels': True,
            'margin_left': 10,
            'margin_top': -10,
            'color_category': "category20",
        }
    return result


churn_factor = 0.05
throughput_factor = 0.95


def calc_cx(churn, max_churn):
    r = churn / max_churn if max_churn > 0 else 0.5
    print("impact = {}, max_impact = {}, r = {}".format(churn, max_churn, r))
    return r

def calc_cy(impact, max_impact):
    r = impact / max_impact if max_impact > 0 else 0.5
    print("impact = {}, max_impact = {}, r = {}".format(impact, max_impact, r))
    return r


def get_devs_quadrant_chart(blames):
    quadrant_data = []

    max_impact = max([b["log_impact"] for b in blames])
    max_churn = max([b["churn"] for b in blames])
    for blame_stat in blames:
        dev = blame_stat['dev']
        cx = calc_cx(blame_stat['churn'], (max_churn)*1.05)
        cy = calc_cy(blame_stat['log_impact'], max_impact*1.05)
        size = math.sqrt(blame_stat['impact'])
        weight1 = blame_stat['throughput']
        weight2 = blame_stat['churn']
        print("blame_stat = {}".format(blame_stat))
        quadrant_data.append({'developer': dev,
                              'cx': cx,
                              'cy': cy,
                              'size': size,
                              'impact': blame_stat['impact'],
                              'weight1': weight1,
                              'weight2': weight2,
                              'developer_id': dev.id})
    result = dict()
    result['data'] = quadrant_data
    return result


def get_dev_activity_chart(dev, repos):

    result = dict()

    stats = Commit.objects.filter(repository__in=repos, author=dev).annotate(d=TruncDate('date')) \
        .values('d').annotate(lines=Sum('lines'), insertions=Sum('insertions'),
                              deletions=Sum('deletions'), net=Sum('net'))\
        .order_by('d')

    xdata = []
    ydata1 = []
    ydata2 = []
    ydata3 = []
    acum_ydata1 = []
    acum_ydata2 = []
    acum_ydata3 = []
    acum_net = 0
    acum_ins = 0
    acum_del = 0
    for stat in stats:
        dd = stat['d'].timetuple()
        d = int(mktime(dd) * 1000)
        xdata.append(d)
        ins = stat['insertions']
        acum_ins += ins
        dls = stat['deletions']
        acum_del += dls
        net = stat['net']
        acum_net += net
        ydata1.append(ins)
        ydata2.append(-dls)
        ydata3.append(net)
        acum_ydata1.append(acum_ins)
        acum_ydata2.append(acum_del)
        acum_ydata3.append(acum_net)

    tooltip_date = "%Y/%m/%d"
    extra_serie1 = {
        "tooltip": {"y_start": "", "y_end": " ins"},
        "date_format": tooltip_date,
        'interpolate': 'basis',
    }
    extra_serie2 = {
        "tooltip": {"y_start": "", "y_end": " del"},
        "date_format": tooltip_date,
        'interpolate': 'basis',
    }
    extra_serie3 = {
        "tooltip": {"y_start": "", "y_end": " net"},
        "date_format": tooltip_date,
        'interpolate': 'basis',
    }
    series_data = {
        'x': xdata,
        'name1': 'insertions', 'y1': ydata1, 'extra1': extra_serie1,
        'name2': 'deletions', 'y2': ydata2, 'extra2': extra_serie2,
        'name3': 'net', 'y3': ydata3, 'extra3': extra_serie3,
    }
    result['data1'] = series_data
    result['extra1'] = {
        'x_is_date': True,
        'x_axis_format': '%Y/%m/%d',
        'tag_script_js': True,
        'jquery_on_ready': False,
        'interpolate': 'basis',
        'color_category': "category10",
    }

    series_data = {
        'x': xdata,
        'name1': 'acum ins', 'y1': acum_ydata1, 'extra1': extra_serie1,
        'name2': 'acum del', 'y2': acum_ydata2, 'extra2': extra_serie2,
        'name3': 'acum net', 'y3': acum_ydata3, 'extra3': extra_serie3,
    }
    result['data3'] = series_data
    result['extra3'] = {
        'x_is_date': True,
        'x_axis_format': '%Y/%m/%d',
        'tag_script_js': True,
        'jquery_on_ready': False,
        'interpolate': 'basis',
        'color_category': "category10",

    }

    stats = FileChange.objects.filter(repository__in=repos, commit__author=dev)\
        .annotate(d=TruncDate('commit__date')) \
        .values('d').annotate(changes=Count('id', distinct=True), commits=Count('commit__id', distinct=True))\
        .order_by('d')

    xdata = []
    ydata4 = []
    ydata5 = []
    acum_ydata4 = []
    acum_ydata5 = []
    acum_commits = 0
    acum_changes = 0
    for stat in stats:
        dd = stat['d'].timetuple()
        d = int(mktime(dd) * 1000)
        xdata.append(d)
        commits = stat['commits']
        acum_commits += commits
        changes = stat['changes']
        acum_changes += changes
        ydata4.append(commits)
        acum_ydata4.append(acum_commits)
        ydata5.append(changes)
        acum_ydata5.append(acum_changes)

    extra_serie4 = {
        "tooltip": {"y_start": "", "y_end": " commits"},
        "date_format": tooltip_date,
        'interpolate': 'basis',
    }
    extra_serie5 = {
        "tooltip": {"y_start": "", "y_end": " filechanges"},
        "date_format": tooltip_date,
        'interpolate': 'basis',
    }
    series_data = {
        'x': xdata,
        'name1': 'commits', 'y1': ydata4, 'extra1': extra_serie4,
        'name2': 'filechanges', 'y2': ydata5, 'extra2': extra_serie5,
    }
    result['data2'] = series_data
    result['extra2'] = {
        'x_is_date': True,
        'x_axis_format': '%Y/%m/%d',
        'tag_script_js': True,
        'jquery_on_ready': False,
        'interpolate': 'basis',
        'color_category': "category10",
    }

    series_data = {
        'x': xdata,
        'name1': 'acum commits', 'y1': acum_ydata4, 'extra1': extra_serie4,
        'name2': 'acum filechanges', 'y2': acum_ydata5, 'extra2': extra_serie5,
    }
    result['data4'] = series_data
    result['extra4'] = {
        'x_is_date': True,
        'x_axis_format': '%Y/%m/%d',
        'tag_script_js': True,
        'jquery_on_ready': False,
        'interpolate': 'basis',
        'color_category': "category10",
    }
    return result


def dev_commits_graph_data(dev, repos):
    stats = Commit.objects.filter(repository__in=repos, author=dev)\
                .annotate(d=TruncDate('date')) \
                .values('d').annotate(total=Count('id', distinct=True))\
                .order_by('d')
    count = stats.count()
    stats = stats[max(count-dev.limit_graph, 0):]
    result = list()
    for s in stats:
        result.append({'period': '{}'.format(s['d']), 'value': s['total']})
    return result


def dev_changes_graph_data(dev, repos):
    limit_graph = 300
    stats = FileChange.objects.filter(repository__in=repos, commit__author=dev)\
        .annotate(d=TruncDate('commit__date')) \
        .values('d').annotate(total=Count('id', distinct=True)).order_by('d')
    stats = stats[max(limit_graph, 0):]
    result = list()
    for s in stats:
        result.append({'period': '{}'.format(s['d']), 'value': s['total']})
    return result
