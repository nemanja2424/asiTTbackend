from flask import Blueprint,jsonify,request

from ..auth import authenticated
from ..errors import APIError
from ..services import logs as service
from ..validation import integer,iso_date,json_body,text,timestamp,uuid4


blueprint = Blueprint('logs',__name__,url_prefix='/api/logs')
BIGINT_MAX = 9223372036854775807


@blueprint.post('')
@authenticated()
def create():
    data = json_body({'project_id','task_id','start_time','end_time','spent_time','note'},
                     {'project_id','start_time','end_time','spent_time'})
    data['project_id'] = uuid4(data['project_id'],'project_id')
    if data.get('task_id') is not None:
        data['task_id'] = uuid4(data['task_id'], 'task_id')
    data['start_time'] = timestamp(data['start_time'],'start_time')
    data['end_time'] = timestamp(data['end_time'],'end_time')
    data['spent_time'] = integer(data['spent_time'],'spent_time',maximum=BIGINT_MAX)
    if 'note' in data and data['note'] is not None:
        data['note'] = text(data['note'],'note',minimum=0,maximum=1000,strip=False)
    return jsonify(service.create(data)),201


@blueprint.get('')
@authenticated()
def list_logs():
    filters = {}
    for field in ('project_id','user_id','department_id'):
        if field in request.args:
            filters[field] = uuid4(request.args[field],field)
    for field in ('date_from','date_to'):
        if field in request.args:
            filters[field] = iso_date(request.args[field],field)
    for field in ('min_spent_time','max_spent_time'):
        if field in request.args:
            try:
                value = int(request.args[field])
            except ValueError:
                raise APIError('invalid_input',f'{field} must be an integer') from None
            filters[field] = integer(value,field,maximum=BIGINT_MAX)
    if 'min_spent_time' in filters and 'max_spent_time' in filters and filters['min_spent_time'] > filters['max_spent_time']:
        raise APIError('invalid_input','min_spent_time must not exceed max_spent_time')
    return jsonify(service.list_logs(filters,request.args))


@blueprint.get('/<log_id>')
@authenticated()
def detail(log_id):
    return jsonify(service.detail(uuid4(log_id)))


@blueprint.delete('/<log_id>')
@authenticated()
def delete(log_id):
    return jsonify(service.delete(uuid4(log_id)))
