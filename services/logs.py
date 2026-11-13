from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app

from ..authorization import require_role, transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import logs as repository
from ..repositories import projects as project_repository
from ..validation import uuid4
from . import scope, tasks


def date_bounds(filters):
    """Calendar dates in Belgrade; inclusive to date becomes exclusive next day.

    Both omitted: current Monday-Sunday. One omitted: open opposite bound.
    """
    zone = ZoneInfo(current_app.config['APP_TIMEZONE'])
    start, end = filters.get('date_from'), filters.get('date_to')
    if start is None and end is None:
        today = datetime.now(zone).date()
        start = today-timedelta(days=today.weekday())
        end = start+timedelta(days=6)
    if start is not None and end is not None and start > end:
        raise APIError('invalid_input','date_from must not exceed date_to')
    try:
        lower = datetime.combine(start,time.min,zone) if start is not None else None
        upper = datetime.combine(end+timedelta(days=1),time.min,zone) if end is not None else None
    except OverflowError:
        raise APIError('invalid_input','date_to is outside the supported calendar range') from None
    return lower,upper


def create(data):
    def operation(connection):
        actor = transaction_actor(connection)
        now = datetime.now(timezone.utc)
        start,end = data['start_time'],data['end_time']
        if end <= start or start > now or end > now:
            raise APIError('invalid_interval','Interval must end after its start and cannot be in the future')
        if data['spent_time'] > (end-start)//timedelta(seconds=1):
            raise APIError('invalid_spent_time','spent_time cannot exceed the interval duration')
        project = project_repository.find(connection,data['project_id'])
        if project is None:
            raise APIError('not_found','Project not found',404)
        if project['status']!='active' or project['archived_at'] is not None:
            raise APIError('project_unavailable','Project must be active and not archived',409)
        if not project_repository.is_effective_participant(connection,data['project_id'],actor['id']):
            raise APIError('forbidden','You are not a participant of this project',403)
        if data.get('task_id') is not None:
            task, _, _ = tasks.task_access(connection, actor, data['task_id'], lock=True)
            if task['project_id'] != data['project_id']:
                raise APIError('invalid_input', 'Task does not belong to the selected project')
        return repository.create(connection,actor['id'],data)
    return run_transaction(operation)


def list_logs(filters,args):
    def operation(connection):
        actor = transaction_actor(connection)
        visible_users = scope.readable_user_ids(connection,actor)
        lower,upper = date_bounds(filters)
        binding = {**filters,'endpoint':'logs','actor':str(actor['id']),'role':actor['role'],
                   'lower':lower,'upper':upper}
        limit,after = page_request(args,binding)
        if after is not None:
            after = uuid4(after,'cursor position')
        rows = repository.list_logs(connection,visible_users,filters,lower,upper,after,limit)
        return page_response(rows,limit,binding,lambda row:str(row['id']))
    return run_transaction(operation)


def detail(log_id):
    def operation(connection):
        actor = transaction_actor(connection)
        log = repository.find(connection,log_id,scope.readable_user_ids(connection,actor))
        if log is None:
            raise APIError('not_found','Log not found',404)
        return log
    return run_transaction(operation)


def delete(log_id):
    def operation(connection):
        actor = transaction_actor(connection)
        require_role(actor,'admin')
        if repository.find(connection,log_id,None) is None:
            raise APIError('not_found','Log not found',404)
        repository.delete(connection,log_id)
        return {'message':'Log deleted'}
    return run_transaction(operation)
