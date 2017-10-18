#!/usr/bin/python
from common import log
import pymysql


def get_data_mysql(host, user, password, schema, table):

    result = ''
    # Connect to the database
    connection = pymysql.connect(host=table,
                                 user=user,
                                 password=password,
                                 db=schema,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    try:
        with connection.cursor() as cursor:
            # Read the table
            sql = str('SELECT * FROM `' + table + '`;')
            cursor.execute(str(sql))
            result = cursor.fetchall()
    except Exception as exc:
        log(exc)
    finally:
        connection.close()
        return result


