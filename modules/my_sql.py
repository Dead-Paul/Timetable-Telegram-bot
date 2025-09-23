import logging
import mysql.connector
from typing import cast

import mysql.connector.cursor

from .dict_types import MySQLConnectionDict

class MySQL:
    def __init__(self, connection_dict: MySQLConnectionDict, logger: logging.Logger, autocommit: bool = False):
        self.connection_dict: MySQLConnectionDict = connection_dict
        self.logger: logging.Logger = logger
        self.__connection: mysql.connector.MySQLConnection|None = None
        self.__cursor: mysql.connector.cursor.MySQLCursorDict|None = None
        self.connect()

    def connect(self) -> None:
        try:
            self.__connection = cast(mysql.connector.MySQLConnection, mysql.connector.connect(**self.connection_dict))
        except mysql.connector.Error as error:
            self.logger.error(f"Database connection error: \"{error.msg}\"")
            raise

    def cursor(self) -> mysql.connector.cursor.MySQLCursorDict:
        if self.__connection is None or not self.__connection.is_connected():
            self.connect()
            self.__cursor = None
        assert self.__connection is not None
        if self.__cursor is None:
            self.__cursor = cast(mysql.connector.cursor.MySQLCursorDict, self.__connection.cursor(dictionary=True))
        return self.__cursor

    def close(self) -> bool:
        if self.__connection is not None and self.__connection.is_connected():
            if self.__cursor is not None:
                self.__cursor.close()
                self.__cursor = None
            self.__connection.close()
            self.__connection = None
            return True
        return False

if __name__ == "__main__":
    exit()