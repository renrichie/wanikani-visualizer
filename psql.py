import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
from typing import Any


class PostgresClient:
    """
    A wrapper client for Postgres.
    The intention of this class is to easily allow mocking of the actual connection when testing this class.

    Parameters
    ----------
    dbname : str
        The Postgres database name.
    user : str
        The Postgres user.
    password : str
        The password for the user.
    host : str
        The database host - defaults to localhost.
    port : str
        The port to connect on - defaults to 5432.
    """
    def __init__(self, dbname: str, user: str, password: str, host: str = 'localhost', port: str = '5432'):
        self._connection = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        logging.basicConfig(filename=f"logs/{datetime.today().strftime('%Y-%m-%d')}.log", level=logging.DEBUG)

    def __del__(self):
        # Close the connection for the user if they forgot to.
        try:
            self._connection.close()
        except Exception as e:
            logging.debug(f'{datetime.now()} | ERROR: {str(e)}')

    def execute(self, sql: str, args: tuple = ()) -> Any:
        """
        Performs SQL statements.
        If there are no arguments, pass in an empty tuple.

        Parameters
        ----------
        sql : str
            The SQL statement to perform.
        args : tuple
            The arguments for the statement.

        Returns
        -------
        Any
            Whatever return value is specified in the SQL or None if not.

        """
        retval = None

        cursor = self._connection.cursor()

        try:
            cursor.execute(sql, args)
            try:
                retval = cursor.fetchone()[0]
            except:
                pass  # No return value was designated in the SQL probably, so just ignore it.
        except Exception as e:
            logging.debug(f'{datetime.now()} | ERROR: {str(e)}')
            self._connection.rollback()
            raise e
        finally:
            self._connection.commit()
            cursor.close()

        return retval

    def query_all(self, sql: str) -> list:
        """
        Performs the SQL query and returns all rows in an associative format.

        Parameters
        ----------
        sql : str
            The query to perform.

        Returns
        -------
        list
            A list of dictionaries with the info per row.

        """
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        values = None

        try:
            cursor.execute(sql)
            values = cursor.fetchall()
        except Exception as e:
            logging.debug(f'{datetime.now()} | ERROR: {str(e)}')
            raise e
        finally:
            cursor.close()

        return values

    def query_one(self, sql: str) -> dict:
        """
        Performs the SQL query and returns one row in an associative format.

        Parameters
        ----------
        sql : str
            The query to perform.

        Returns
        -------
        dict
            A dictionary with the info of the first row.

        """
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        values = None

        try:
            cursor.execute(sql)
            values = cursor.fetchone()
        except Exception as e:
            logging.debug(f'{datetime.now()} | ERROR: {str(e)}')
            raise e
        finally:
            cursor.close()

        return values

    def close(self):
        """
        Closes the database connection.

        Returns
        -------
        None

        """
        self._connection.close()

    def clear_tables(self, tables: list):
        """
        Removes the data from the specified tables in order.

        Parameters
        ----------
        tables: list
            A list of tables to clear in order.

        Returns
        -------
        None

        """
        self.execute(f"TRUNCATE {', '.join(tables)}")

    def process_row(self, exists_query: str, insert_sql: str, update_sql: str, insert_args: tuple, update_args: tuple):
        """
        Creates the row if it doesn't already exist, otherwise it updates it.

        Parameters
        ----------
        exists_query : str
            The query to use to check row existence.
        insert_sql : str
            The INSERT statement to execute if the row does not exist.
        update_sql : str
            The UPDATE statement to execute if the row already exists.
        insert_args : tuple
            The arguments to execute the INSERT with.
        update_args : tuple
            The arguments to execute the UPDATE with.

        Returns
        -------
        None

        """
        existing_record = self.query_one(exists_query)['exists']

        if existing_record:
            self.execute(update_sql, update_args)
        else:
            self.execute(insert_sql, insert_args)


if __name__ == '__main__':
    db = PostgresClient(dbname='postgres', user='postgres', password='postgres')

    # Example SELECT query.
    print(db.query_all('SELECT * FROM account'))

    # Example INSERT statement.
    db.execute(
        'INSERT INTO account (id, level, username) VALUES (%s, %s, %s)',
        (1, 420, 'bob')
    )
    print(db.query_all('SELECT * FROM account'))

    # Example UPDATE statement.
    db.execute('UPDATE account SET level = %s WHERE username = %s', (404, 'bob'))
    print(db.query_all('SELECT * FROM account'))

    # Example DELETE statement.
    db.execute('DELETE FROM account')
    print(db.query_all('SELECT * FROM account'))

    db.close()
