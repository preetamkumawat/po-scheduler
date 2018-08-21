"""This file takes care of DB connection/insertion/updation"""
import os
import sqlalchemy
from traceback import format_exc

db_user = os.environ.get("DB_USER", "root")
db_password = os.environ.get("DB_PASSWORD", "root")
db_host = os.environ.get("DB_HOST", "localhost")
db_port = os.environ.get("DB_PORT", "3306")

DB_CONNECTION = 'mysql://{db_user}:{db_password}@{db_host}:{db_port}/?charset=utf8&use_unicode=1'.format(**{
    "db_user": db_user,
    "db_password": db_password,
    "db_host": db_host,
    "db_port": db_port,
})


def get_engine(db):
    """fetch mysql engine
       :param db: mysql connection string in format mysql://username:password@host:port
    """
    conn = sqlalchemy.create_engine(db, pool_recycle=60, max_overflow=0, pool_timeout=30)
    return conn.connect()


def write_to_db(query):
    """
    Write our date to DB.
    :param query: string representation of query
    :return:
    """
    try:
        return __run_write_to_db(query)
    except:
        print(format_exc())  # We can log this
        return False


def __run_write_to_db(query):
    """update data to mysql table
      :param query: raw insert/update query to be executed
    """
    db = DB_CONNECTION
    engine = get_engine(db)
    engine.execute(query)
    engine.close()
    engine.engine.dispose()

    return engine


def get_results_as_dict(query):
    """return sql data as a list of dict
      :param query: sql query to be executed
      :return list: mysql connection string
    """

    return list(get_results_as_dict_iter(query, DB_CONNECTION))


def get_results_as_dict_iter(query, db):
    """fetch results from sql read query
       :param engine: mysql connection string
       :param query: mysql query to be executed
    """
    engine = get_engine(db)

    is_session = 'session' in repr(engine.__class__).lower()

    result = engine.execute(query) if is_session else engine.execute(query)
    keys = result.keys()

    for r in result:
        yield dict((k, v) for k, v in zip(keys, r))

    engine.close()
    engine.engine.dispose()
