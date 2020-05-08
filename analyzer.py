import json
from datetime import datetime

from wanikani import WaniKaniClient, DATE_FORMAT
import stats
from psql import PostgresClient


class Analyzer:
    """
    This is the main application.
    It aggregates and analyzes the WaniKani data.

    Parameters
    ----------
    db : PostgresClient
        The Postgres DB client.
    """
    def __init__(self, wanikani: WaniKaniClient, db: PostgresClient):
        self._client = wanikani
        self._db = db
        self._cache = {}

    def analyze_user_info(self):
        """
        Processes all the user's info through the WaniKani API.

        Returns
        -------
        None

        """
        id = self._process_user(user_info=self._client.get_user())

        print('======== LEVEL PROGRESSION DATA ========')

        for page in self._client.get_level_progressions():
            self._process_level_progressions(user_id=id, progressions=page)

        # Only need to populate the subjects once.
        if self._db.query_one('SELECT COUNT(*) FROM subject')['count'] == 0:
            for page in self._client.get_subjects():
                self._process_subjects(subjects=page)

        print('\n======== ASSIGNMENT PROGRESS DATA ========')

        for page in self._client.get_assignments():
            self._process_assignments(user_id=id, assignments=page)

    def _get_aggregates(self, data: list):
        """
        Creates a dictionary containing the mean and median aggregates for the list.
        If the list is empty, the value for each key will be None.

        Parameters
        ----------
        data : list
            A list of numeric values.

        Returns
        -------
        dict
            A dictionary with the 'mean' and 'median' keys containing their respective values.

        """
        return {'mean': stats.get_mean(data), 'median': stats.get_median(data)}

    def _calculate_time_delta(self, first_date: str, second_date: str):
        """
        Calculates the time delta between two dates in terms of number of seconds.
        The order of the strings does not matter.

        Parameters
        ----------
        first_date : str
            A datetime string in ISO-8601 format.
        second_date : str
            A datetime string in ISO-8601 format.

        Returns
        -------
        int
            The number of seconds elapsed between the two datetimes.

        """
        if first_date is None or second_date is None:
            return None

        start = datetime.strptime(first_date, DATE_FORMAT)
        end = datetime.strptime(second_date, DATE_FORMAT)
        delta = abs((end - start).total_seconds())

        return delta

    def _process_user(self, user_info: dict):
        """
        Creates an entry for the user in the database to establish data relationships.

        Parameters
        ----------
        user_info : dict
            The JSON containing the user info.

        Returns
        -------
        int
            The ID of the user in the database.

        """
        username = user_info['username']
        existing_user = self._db.query_all(f"SELECT id, last_queried FROM account WHERE username = '{username}'")

        current_time = datetime.now().strftime(DATE_FORMAT)

        if existing_user:
            user_id = existing_user[0]['id']
            last_queried_time = existing_user[0]['last_queried'].strftime(DATE_FORMAT)
            time_since_last_query = self._calculate_time_delta(last_queried_time, current_time) or 0
            use_cached_values = time_since_last_query < (10 * 60)

            if not use_cached_values:
                self._db.execute('UPDATE account SET last_queried = %s WHERE id = %s', (current_time, user_id))

            self._cache[user_id] = use_cached_values  # Use cached data for 10 minutes to prevent unnecessary load.

            return user_id

        user_id = self._db.execute(
            'INSERT INTO account (level, username, last_queried) VALUES (%s, %s, %s) RETURNING id',
            (user_info['level'], username, current_time)
        )

        self._cache[user_id] = True

        return user_id

    def _process_level_progressions(self, user_id: int, progressions: dict):
        # Re-use values from the database.
        if self._cache[user_id]:
            pass

        level_stats = {}
        durations = {
            'pass': [],
            'complete': []
        }

        for level_prog in progressions['data']:
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at']
            pass_date = level_prog['data']['passed_at']
            end_date = level_prog['data']['completed_at']

            level_stats[level] = {
                'pass_duration': self._calculate_time_delta(start_date, pass_date),
                'complete_duration':  self._calculate_time_delta(start_date, end_date)
            }

            self._db.execute(
                'INSERT INTO level_progression (level, user_id, started_at, passed_at, completed_at) VALUES (%s, %s, %s, %s, %s)',
                (level, user_id, start_date, pass_date, end_date)
            )

            if level_stats[level]['pass_duration'] is not None:
                durations['pass'].append(level_stats[level]['pass_duration'])

            if level_stats[level]['complete_duration'] is not None:
                durations['complete'].append(level_stats[level]['complete_duration'])

            print(f'Level: {level:>2} | Start date: {start_date or "N/A":>27} | Pass date: {pass_date or "N/A":>27} | Completion date: {end_date or "N/A":>27}')

        level_stats['aggregates'] = {
            'pass': self._get_aggregates(durations['pass']),
            'complete': self._get_aggregates(durations['complete'])
        }

        return level_stats

    def _process_subjects(self, subjects: dict):
        for subject in subjects['data']:
            character_images = None

            try:
                character_images = subject['data']['characters_images']['url']
            except:
                pass

            self._db.execute(
                'INSERT INTO subject (id, level, type, image_url, characters) VALUES (%s, %s, %s, %s, %s)',
                (subject['id'], subject['data']['level'], subject['object'], character_images, subject['data']['characters'] or '[Radical]')
            )

    def _process_assignments(self, user_id: int, assignments: dict):
        # Re-use values from the database.
        if self._cache[user_id]:
            pass

        for assignment in assignments['data']:
            # TODO: Query reviews for more data too.
            subject_id = assignment['data']['subject_id']
            subject = self._db.query_one(f'SELECT characters FROM subject WHERE id = {subject_id}')['characters']
            srs_stage_name = assignment['data']['srs_stage_name']
            srs_stage_id = assignment['data']['srs_stage']
            start_date = assignment['data']['started_at']
            pass_date = assignment['data']['passed_at']
            end_date = assignment['data']['burned_at']

            # Hack to properly pad UTF-8 Japanese characters.
            # Python does not handle multi-byte characters that well, especially considering full vs half width.
            if 'Radical' not in subject:
                padding_to_remove = len(subject) - 1
                subject = f'{subject:>15}'.replace(' ', '', padding_to_remove)
            else:
                subject = f'{subject:>16}'

            print(f'Subject ID: {subject_id:>8} | Subject: {subject} | SRS stage: {srs_stage_name:>14} ({srs_stage_id}) | Start date: {start_date or "N/A":>27} | Pass date: {pass_date or "N/A":>27} | Completion date: {end_date or "N/A":>27}')


if __name__ == '__main__':
    api_key = None

    try:
        with open('secret.json', 'r') as file:
            try:
                api_key = json.load(file)['api_key']
                print('API key loaded.\n')
            except Exception as e:
                raise SystemExit(f'An error occurred while loading the JSON: {e}')
    except IOError:
        raise SystemExit('Unable to load the API key.')

    client = WaniKaniClient(api_key)
    db = PostgresClient(dbname='postgres', user='postgres', password='postgres')
    analyzer = Analyzer(wanikani=client, db=db)

    try:
        analyzer.analyze_user_info()
    finally:
        db.close()
