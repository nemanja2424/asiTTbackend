from flask import Blueprint,jsonify,request

from ..auth import authenticated
from ..errors import APIError
from ..services import reports as service
from ..validation import iso_date,query_boolean,uuid4


blueprint = Blueprint('reports',__name__,url_prefix='/api/reports')


@blueprint.get('')
@authenticated()
def report():
    report_type = request.args.get('type','time')
    if report_type not in service.DEFAULT_GROUPS:
        raise APIError('invalid_input','type must be time, projects, users or departments')
    group_by = request.args.get('group_by',service.DEFAULT_GROUPS[report_type])
    if group_by not in ('day','week','month','project','user','department'):
        raise APIError('invalid_input','group_by is invalid')
    filters = {}
    for field in ('date_from','date_to'):
        if field in request.args:
            filters[field] = iso_date(request.args[field],field)
    for field in ('project_id','user_id','department_id'):
        if field in request.args:
            filters[field] = uuid4(request.args[field],field)
    for field,values in (('project_status',('pending','active','paused','finished')),('user_role',('admin','manager','worker'))):
        if field in request.args:
            if request.args[field] not in values:
                raise APIError('invalid_input',f'{field} is invalid')
            filters[field] = request.args[field]
    if 'include_subdepartments' in request.args:
        filters['include_subdepartments'] = query_boolean(request.args['include_subdepartments'],'include_subdepartments')
    return jsonify(service.report(filters,report_type,group_by))
