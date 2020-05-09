import psycopg2
import psycopg2.extras
import logging
from datetime import datetime


class PostgresClient:
    """
    A wrapper client for Postgres.
    The intention of this class is to easily allow mocking when testing.

    Parameters
    ----------
    dbname : str
        The Postgres database name.
    user : str
        The Postgres user.
    password: str
        The password for the user.
    """
    def __init__(self, dbname: str, user: str, password: str, host='localhost', port='5432'):
        self._connection = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        logging.basicConfig(filename=f"{datetime.today().strftime('%Y-%m-%d')}.log", level=logging.DEBUG)

    def __del__(self):
        # Close the connection for the user if they forgot to.
        try:
            self._connection.close()
        except Exception as e:
            logging.debug(f'ERROR: {str(e)}')

    def execute(self, sql: str, args: tuple = ()):
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
        int
            An integer from the database, most likely an ID.
        str
            Any string.
        None
            Returned when no return value is specified in the SQL.

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
            logging.debug(f'ERROR: {str(e)}')
            self._connection.rollback()
        finally:
            self._connection.commit()
            cursor.close()

        return retval

    def query_all(self, sql: str):
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
        None
            Returned when an error occurs.

        """
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        values = None

        try:
            cursor.execute(sql)
            values = cursor.fetchall()
        except Exception as e:
            logging.debug(f'ERROR: {str(e)}')
        finally:
            cursor.close()

        return values

    def query_one(self, sql: str):
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
        None
            Returned when an error occurs.

        """
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        values = None

        try:
            cursor.execute(sql)
            values = cursor.fetchone()
        except Exception as e:
            logging.debug(f'ERROR: {str(e)}')
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
