from datetime import timedelta

from flask import current_app

from ..authorization import transaction_actor
from ..db import run_transaction
from ..repositories import reports as repository
from ..repositories import scope as scope_repository
from . import scope
from .logs import date_bounds


DEFAULT_GROUPS = {'time':'day','projects':'project','users':'user','departments':'department'}


def report_context(connection, actor, filters):
    visible_users = scope.readable_user_ids(connection, actor)
    allowed_departments = scope.visible_departments(connection, actor)
    filter_departments = None
    if 'department_id' in filters:
        department_id = filters['department_id']
        filter_departments = (scope_repository.descendants(connection, department_id)
                              if filters.get('include_subdepartments',True) else {department_id})
        if allowed_departments is not None:
            filter_departments &= allowed_departments
    output_departments = allowed_departments
    if filter_departments is not None:
        output_departments = filter_departments
    elif actor['role'] == 'worker' and not allowed_departments:
        # A worker with no current membership receives the null department bucket.
        output_departments = None
    lower, upper = date_bounds(filters)
    query, params = repository.filtered_query(visible_users, filters, lower, upper, filter_departments)
    return query, params, output_departments, lower, upper


def effective_dates(lower, upper):
    return {'date_from':lower.date() if lower else None,
            'date_to':upper.date()-timedelta(days=1) if upper else None}


def report(filters, report_type, group_by):
    def operation(connection):
        actor = transaction_actor(connection)
        query,params,departments,lower,upper = report_context(connection,actor,filters)
        totals = repository.totals(connection,query,params)
        items = repository.grouped(connection,query,params,group_by,current_app.config['APP_TIMEZONE'],departments)
        return {'type':report_type,'group_by':group_by,**effective_dates(lower,upper),**totals,'items':items}
    return run_transaction(operation)
