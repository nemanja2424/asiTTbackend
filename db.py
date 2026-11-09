import time

import psycopg
from flask import current_app
from psycopg.rows import dict_row


def run_transaction(operation):
    """Execute operation(connection); retry the ENTIRE DB-only operation on conflict.

    Callbacks must have no external side effects, and must not commit themselves.
    """
    attempts = current_app.config['DB_TRANSACTION_ATTEMPTS']
    for attempt in range(attempts):
        try:
            with psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row,
                                 connect_timeout=5) as connection:
                connection.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                return operation(connection)
        except psycopg.Error as error:
            if error.sqlstate not in ('40001', '40P01') or attempt + 1 == attempts:
                raise
            time.sleep(0.05 * (attempt + 1))
