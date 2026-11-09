"""Read-only inspection of the schema required by Work Pulse Tasks V2.2.

Run from the repository root: python -m backend.tools.check_tasks_schema
Only object names and pass/fail statuses are printed; connection details and
business rows are never printed. This does not run migrations or tests.
"""
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


TABLES = {
    'users': ('id', 'email', 'password_hash', 'full_name', 'role', 'is_active', 'profile_img'),
    'projects': ('id', 'name', 'status', 'start_date', 'end_date', 'archived_at'),
    'resource_libraries': ('id', 'project_id', 'department_id'),
    'resource_folders': ('id', 'library_id', 'parent_folder_id', 'name', 'created_by', 'created_at', 'updated_at', 'deleted_at', 'trash_batch'),
    'resource_files': ('id', 'library_id', 'folder_id', 'original_name', 'storage_key', 'mime_type', 'size_bytes', 'uploaded_by', 'created_at', 'updated_at', 'deleted_at', 'trash_batch'),
    'resource_hierarchy_guard': ('singleton', 'revision'),
    'tasks': ('id', 'project_id', 'title', 'description', 'assigned_to', 'created_by', 'status', 'priority', 'due_date', 'created_at', 'updated_at', 'completed_at'),
    'task_comments': ('id', 'task_id', 'author_id', 'content', 'created_at'),
    'task_activity': ('id', 'task_id', 'actor_id', 'event_type', 'old_value', 'new_value', 'reason', 'created_at'),
    'task_attachments': ('id', 'task_id', 'resource_id', 'added_by', 'created_at'),
    'notifications': ('id', 'user_id', 'task_id', 'actor_id', 'type', 'title', 'message', 'dedupe_key', 'is_read', 'created_at', 'read_at'),
}
INDEXES = ('tasks_project_idx', 'tasks_assigned_idx', 'tasks_status_idx', 'tasks_due_idx',
           'resource_folders_parent_idx', 'resource_files_folder_idx', 'resource_folders_name_idx', 'resource_files_name_idx',
           'task_comments_task_time_idx', 'task_activity_task_time_idx', 'task_attachments_resource_idx',
           'notifications_user_time_idx', 'notifications_unread_idx')


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if not database_url:
        print('DATABASE_URL nije podesen u serverskom okruzenju ili backend/.env.')
        return 1
    missing = []
    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            db_name, server_version = connection.execute("SELECT current_database(), current_setting('server_version_num')").fetchone()
            print('Baza:', db_name.encode('ascii', 'backslashreplace').decode('ascii'))
            print('PostgreSQL server_version_num:', server_version)
            host = (connection.info.host or '').casefold()
            local = host in ('localhost', '127.0.0.1', '::1')
            print('Konfigurisani endpoint:', 'lokalni/tunel' if local else 'udaljeni ili socket')
            table_rows = connection.execute('''SELECT t.name, to_regclass('public.' || t.name) IS NOT NULL, c.column_name
                FROM unnest(%s::text[]) AS t(name) LEFT JOIN information_schema.columns AS c
                ON c.table_schema='public' AND c.table_name=t.name''', (list(TABLES),)).fetchall()
            table_info = {name: [False, set()] for name in TABLES}
            for name, exists, column in table_rows:
                table_info[name][0] = exists
                if column is not None:
                    table_info[name][1].add(column)
            for table, expected in TABLES.items():
                exists, columns = table_info[table]
                if not exists:
                    print(f'NEDOSTAJE tabela: {table}')
                    missing.append(table)
                    continue
                absent = [name for name in expected if name not in columns]
                print(f'{"NEDOSTAJU KOLONE" if absent else "POSTOJI"}: {table}' + (': ' + ', '.join(absent) if absent else ''))
                missing.extend(f'{table}.{name}' for name in absent)
            index_rows = connection.execute("SELECT name, to_regclass('public.' || name) IS NOT NULL FROM unnest(%s::text[]) AS t(name)", (list(INDEXES),)).fetchall()
            for index, found in index_rows:
                if not found:
                    print(f'NEDOSTAJE indeks: {index}')
                    missing.append(index)
            checks = {
                'tasks_timestamps': '''SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.tasks')
                    AND tgname='tasks_timestamps' AND NOT tgisinternal AND tgenabled <> 'D')''',
                'tasks_completion_consistent': '''SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.tasks')
                    AND conname='tasks_completion_consistent' AND contype='c' AND convalidated)''',
                'resource_hierarchy_lock': '''SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.resource_folders')
                    AND tgname='resource_hierarchy_lock' AND NOT tgisinternal AND tgenabled <> 'D')''',
                'resource_hierarchy_validate': '''SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.resource_folders')
                    AND tgname='resource_hierarchy_validate' AND NOT tgisinternal AND tgenabled <> 'D')''',
                'maintain_timestamps': "SELECT to_regprocedure('public.maintain_timestamps()') IS NOT NULL",
                'task_activity_prilozi': '''SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.task_activity')
                    AND contype='c' AND convalidated AND pg_get_constraintdef(oid) LIKE '%%attachment_added%%'
                    AND pg_get_constraintdef(oid) LIKE '%%attachment_removed%%')''',
                'attachments_task_fk': '''SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.task_attachments')
                    AND confrelid=to_regclass('public.tasks') AND contype='f' AND convalidated)''',
                'attachments_resource_fk': '''SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.task_attachments')
                    AND confrelid=to_regclass('public.resource_files') AND contype='f' AND convalidated)''',
                'notifications_dedupe': '''SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.notifications')
                    AND contype='u' AND convalidated AND pg_get_constraintdef(oid) = 'UNIQUE (user_id, dedupe_key)')''',
            }
            check_rows = connection.execute(' UNION ALL '.join(
                f"SELECT '{name}', ({query})" for name, query in checks.items()
            )).fetchall()
            for name, found in check_rows:
                print(f'{"POSTOJI" if found else "NEDOSTAJE"}: {name}')
                if not found:
                    missing.append(name)
    except (psycopg.Error, OSError, ValueError) as error:
        print('Provera nije uspela: baza nije dostupna ili nalog nema potrebna prava.')
        print('Tip greske:', type(error).__name__)
        code = getattr(error, 'sqlstate', None)
        if code:
            print('SQLSTATE:', code)
        return 1
    if missing:
        print('Rezultat: potrebni objekti nisu svi pronadjeni; ne pokretati migraciju naslepo.')
        return 2
    print('Rezultat: provereni objekti postoje. Ovo nije potpuna provera funkcionalnosti ili istorije migracija.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
