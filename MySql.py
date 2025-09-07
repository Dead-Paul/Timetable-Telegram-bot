import logging
import mysql.connector
from typing import cast

import mysql.connector.cursor

class MySql:
    def __init__(self, user: str, password: str, host: str, database: str, logger: logging.Logger, autocommit: bool = False):
        try:
            self.connection = mysql.connector.connect(user=user, password=password, host=host, database=database, autocommit=autocommit)
            self.cursor = cast(mysql.connector.cursor.MySQLCursorDict, self.connection.cursor(dictionary=True))
        except mysql.connector.Error as error:
            logger.error(f"Database connection error: \"{error.msg}\"")
            raise

if __name__ == "__main__":
    exit()