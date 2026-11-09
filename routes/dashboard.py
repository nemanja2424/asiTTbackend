from flask import Blueprint,jsonify,request

from ..auth import authenticated
from ..services import dashboard as service
from ..validation import iso_date


blueprint = Blueprint('dashboard',__name__,url_prefix='/api/dashboard')


@blueprint.get('')
@authenticated()
def dashboard():
    filters = {field:iso_date(request.args[field],field) for field in ('date_from','date_to') if field in request.args}
    return jsonify(service.dashboard(filters))
