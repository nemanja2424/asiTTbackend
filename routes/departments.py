from flask import Blueprint, jsonify, request

from ..auth import authenticated
from ..errors import APIError
from ..services import departments as service
from ..validation import boolean, json_body, query_boolean, text, uuid4


blueprint=Blueprint('departments',__name__,url_prefix='/api/departments')


def validated(body):
    data=dict(body)
    if 'name' in data:
        data['name']=text(data['name'],'name')
    if 'description' in data and data['description'] is not None:
        data['description']=text(data['description'],'description',minimum=0)
    if 'is_active' in data:
        data['is_active']=boolean(data['is_active'],'is_active')
    for field in ('parent_department_id','manager_id'):
        if field in data and data[field] is not None:
            data[field]=uuid4(data[field],field)
    return data


def active_filter():
    value=request.args.get('is_active','true')
    return None if value=='all' else query_boolean(value,'is_active')


@blueprint.get('')
@authenticated()
def list_departments():
    format_=request.args.get('format','flat')
    if format_ not in ('flat','tree'):
        raise APIError('invalid_input','format must be flat or tree')
    return jsonify(service.list_departments(active_filter(),format_=='tree',request.args))


@blueprint.get('/tree')
@authenticated()
def tree():
    return jsonify(service.list_departments(active_filter(),True))


@blueprint.get('/<department_id>')
@authenticated()
def detail(department_id):
    return jsonify(service.detail(uuid4(department_id)))


@blueprint.post('')
@authenticated()
def create():
    data=validated(json_body({'name','description','parent_department_id','manager_id'},{'name'}))
    return jsonify(service.create(data)),201


@blueprint.patch('/<department_id>')
@authenticated()
def update(department_id):
    data=validated(json_body({'name','description','is_active'}))
    if not data:
        raise APIError('invalid_input','At least one field is required')
    return jsonify(service.update(uuid4(department_id),data))


@blueprint.put('/<department_id>/manager')
@authenticated()
def manager(department_id):
    data=validated(json_body({'manager_id'},{'manager_id'}))
    return jsonify(service.update(uuid4(department_id),data))


@blueprint.put('/<department_id>/parent')
@authenticated()
def parent(department_id):
    data=validated(json_body({'parent_department_id'},{'parent_department_id'}))
    return jsonify(service.update(uuid4(department_id),data))


@blueprint.patch('/<department_id>/deactivate')
@authenticated()
def deactivate(department_id):
    return jsonify(service.update(uuid4(department_id),{'is_active':False}))
