from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

from flask import current_app

from ..authorization import transaction_actor
from ..db import run_transaction
from ..repositories import dashboard as repository
from ..repositories import reports as reports_repository
from . import projects,scope
from .reports import effective_dates,report_context


def dashboard(filters):
    def operation(connection):
        actor = transaction_actor(connection)
        zone = ZoneInfo(current_app.config['APP_TIMEZONE'])
        today = datetime.now(zone).date()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28)+timedelta(days=4)).replace(day=1)
        selected = dict(filters)
        if 'date_from' not in selected and 'date_to' not in selected:
            selected = {'date_from':month_start,'date_to':next_month-timedelta(days=1)}
        query,params,departments,lower,upper = report_context(connection,actor,selected)
        totals = reports_repository.totals(connection,query,params)
        result = {'role':actor['role'],**effective_dates(lower,upper),**totals}

        def period_total(start,end):
            period_query,period_params,_,_,_ = report_context(connection,actor,{'date_from':start,'date_to':end})
            return reports_repository.totals(connection,period_query,period_params)['spent_time']

        def groups(group_by,limit=None,ranked=False):
            return reports_repository.grouped(connection,query,params,group_by,zone.key,departments,limit,ranked)

        result['today_spent_time'] = period_total(today,today)
        result['month_spent_time'] = period_total(month_start,next_month-timedelta(days=1))
        if actor['role']=='admin':
            result['active_users'] = repository.active_user_count(connection,None)
            result['active_projects'] = repository.active_project_count(connection)
            result['top_projects'] = groups('project',10,True)
            result['top_users'] = groups('user',10,True)
            result['by_department'] = groups('department')
        elif actor['role']=='manager':
            visible_projects,_ = projects.permissions(connection,actor)
            active = repository.active_projects(connection,actor,visible_projects)
            result['employee_count'] = repository.active_user_count(connection,scope.readable_user_ids(connection,actor))
            result['active_projects'] = active
            result['active_project_count'] = len(active)
            result['top_projects'] = groups('project',10,True)
            result['by_user'] = groups('user')
            result['by_department'] = groups('department')
        else:
            week_start = today-timedelta(days=today.weekday())
            result['week_spent_time'] = period_total(week_start,week_start+timedelta(days=6))
            result['active_projects'] = repository.active_projects(connection,actor)
            result['recent_logs'] = repository.recent_logs(connection,actor['id'])
            result['by_project'] = groups('project')
        return result
    return run_transaction(operation)
