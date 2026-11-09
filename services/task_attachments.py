"""Links to files owned by the task's project; the library remains authoritative."""
from ..authorization import transaction_actor
from ..db import run_transaction
from ..errors import APIError
from ..pagination import page_request, page_response
from ..repositories import task_extras as repo, tasks as task_repo
from ..validation import uuid4
from . import resources, tasks


def context(connection, task_id, write=False):
    actor = transaction_actor(connection)
    row, manage, visible = tasks.task_access(connection, actor, task_id, write=write)
    if not visible:
        raise APIError('not_found', 'Project library not found', 404)
    resources._authorize(connection, 'projects', row['project_id'])
    if write:
        tasks.editable({'archived_at':row['project_archived_at'], 'status':row['project_status']})
    return actor, row, manage


def listing(task_id, args):
    def operation(connection):
        actor, row, manage = context(connection, task_id)
        binding = {'endpoint':'task_attachments','task_id':str(task_id),'actor':str(actor['id']),'role':actor['role']}
        limit, after = page_request(args, binding)
        if after is not None: after = uuid4(after, 'cursor position')
        rows = repo.attachments(connection, task_id, row['project_id'], after, limit)
        writable = row['project_archived_at'] is None and row['project_status'] != 'finished'
        values = [{**item, 'can_remove':bool(writable and (manage or (actor['role']=='worker' and row['assigned_to']==actor['id'] and item['added_by']==actor['id'])))} for item in rows]
        return page_response(values, limit, binding, lambda item:str(item['id']))
    return run_transaction(operation)


def link(task_id, resource_id):
    def operation(connection):
        actor, task, _ = context(connection, task_id, write=True)
        file = repo.resource(connection, task['project_id'], resource_id)
        if file is None: raise APIError('not_found', 'File not found in project library', 404)
        attachment_id = repo.link(connection, task_id, resource_id, actor['id'])
        task_repo.activity(connection, task_id, actor['id'], 'attachment_added', new=file['original_name'])
        return {'id':attachment_id, 'resource_id':resource_id}
    return run_transaction(operation)


def unlink(task_id, attachment_id):
    def operation(connection):
        actor, task, manage = context(connection, task_id, write=True)
        item = repo.attachment(connection, task_id, attachment_id)
        if item is None: raise APIError('not_found', 'Attachment not found', 404)
        if not manage and item['added_by'] != actor['id']:
            raise APIError('forbidden', 'You can remove only your own attachments', 403)
        file = repo.resource(connection, task['project_id'], item['resource_id'])
        if file is None: raise APIError('not_found', 'File not found in project library', 404)
        repo.unlink(connection, attachment_id)
        task_repo.activity(connection, task_id, actor['id'], 'attachment_removed', old=file['original_name'])
        return {'message':'Attachment removed'}
    return run_transaction(operation)
