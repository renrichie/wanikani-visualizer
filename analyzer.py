import json
import logging
from datetime import datetime
from typing import Union

from wanikani import WaniKaniClient, DATE_FORMAT
import stats
from psql import PostgresClient


class Analyzer:
    """
    This is the main application.
    It aggregates and analyzes the WaniKani data.

    Parameters
    ----------
    wanikani : WaniKaniClient
        The WaniKani client initialized using an API key.
    db : PostgresClient
        The Postgres DB client.
    """
    def __init__(self, wanikani: WaniKaniClient, db: PostgresClient):
        self._client = wanikani
        self._db = db
        self._cache = {}
        logging.basicConfig(filename=f"logs/{datetime.today().strftime('%Y-%m-%d')}.log", level=logging.DEBUG)

    def analyze_user_info(self):
        """
        Processes all the user's info through the WaniKani API.

        Returns
        -------
        None

        """
        self._clean_stale_data()
        self._initialize_static_info()

        id = self._process_user(user_info=self._client.get_user())

        # Query the API for newer info if we're past our 10 minute cache time or if the data doesn't exist.
        if not self._cache[id]:
            logging.debug(f'{datetime.now()} | Processing new data...')
            print('======== LEVEL PROGRESSION DATA ========')

            for page in self._client.get_level_progressions():
                self._process_level_progressions(user_id=id, progressions=page)

            print('\n======== ASSIGNMENT PROGRESS DATA ========')

            for page in self._client.get_assignments():
                self._process_assignments(user_id=id, assignments=page)

            print('\n======== REVIEW DATA ========')

            for page in self._client.get_reviews():
                self._process_reviews(user_id=id, reviews=page)

        self._analyze_level_progressions()
        self._analyze_assignments()
        self._analyze_reviews()

    def _clean_stale_data(self):
        """
        Removes all data from the database every week to ensure its accuracy.

        Returns
        -------
        None

        """
        current_time = datetime.now()

        # Oldest record can be determined by looking at the create dates if any records exist.
        # If there are no records, then the current time would be the oldest since we are about to make one.
        oldest_record = self._db.query_one('SELECT create_date FROM account ORDER BY create_date ASC LIMIT 1')
        old_time = oldest_record['create_date'] if oldest_record else current_time

        time_elapsed_since_first_query = self._calculate_time_delta(old_time, current_time)

        if time_elapsed_since_first_query >= (60 * 60 * 24 * 7):
            logging.debug(f'{datetime.now()} | Time elapsed since first query: {time_elapsed_since_first_query} seconds')
            logging.debug(f'{datetime.now()} | Clearing stale data...')
            self._db.clear_tables(
                ['review', 'assignment', 'level_progression', 'srs_stage', 'subject', 'account']
            )

    def _initialize_static_info(self):
        """
        Initializes all static info that won't change such as subjects and SRS stages.

        Returns
        -------
        None

        """
        # Only need to populate the subjects once.
        if self._db.query_one('SELECT COUNT(*) FROM subject')['count'] == 0:
            for page in self._client.get_subjects():
                self._process_subjects(subjects=page)

        if self._db.query_one('SELECT COUNT(*) FROM srs_stage')['count'] == 0:
            self._process_srs_stages(stages=self._client.get_srs_stages())  # No need to paginate since there are so few.

    def _get_aggregates(self, data: list) -> dict:
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

    def _calculate_time_delta(self, first_date: Union[str, datetime], second_date: Union[str, datetime]) -> float:
        """
        Calculates the time delta between two dates in terms of number of seconds.
        The order of the parameters does not matter.

        Parameters
        ----------
        first_date : Union[str, datetime]
            A datetime object or string in ISO-8601 format.
        second_date : Union[str, datetime]
            A datetime object or string in ISO-8601 format.

        Returns
        -------
        int
            The number of seconds elapsed between the two datetimes.

        """
        if first_date is None or second_date is None:
            return None

        start = first_date if isinstance(first_date, datetime) else datetime.strptime(first_date, DATE_FORMAT)
        end = second_date if isinstance(second_date, datetime) else datetime.strptime(second_date, DATE_FORMAT)
        delta = abs((end - start).total_seconds())

        return delta

    def _process_user(self, user_info: dict) -> int:
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

        print(f'Username: {username}')
        print(f"Level: {user_info['level']}\n")

        existing_user = self._db.query_one(
            f"SELECT id, username, level, last_queried FROM account WHERE username = '{username}'"
        )

        current_time = datetime.now()

        if existing_user:
            user_id = existing_user['id']
            last_queried_time = existing_user['last_queried']
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

        self._cache[user_id] = False

        return user_id

    def _process_level_progressions(self, user_id: int, progressions: dict):
        for level_prog in progressions['data']:
            id = level_prog['id']
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at']
            pass_date = level_prog['data']['passed_at']
            end_date = level_prog['data']['completed_at']

            self._db.process_row(
                exists_query=f'SELECT EXISTS(SELECT 1 FROM level_progression WHERE id = {id}) AS "exists"',
                update_sql='UPDATE level_progression SET started_at = %s, passed_at = %s, completed_at = %s WHERE id = %s',
                update_args=(start_date, pass_date, end_date, id),
                insert_sql='INSERT INTO level_progression (id, level, user_id, started_at, passed_at, completed_at) VALUES (%s, %s, %s, %s, %s, %s)',
                insert_args=(id, level, user_id, start_date, pass_date, end_date)
            )

            print(f'ID: {id:>10} | Level: {level:>2} | Start date: {start_date or "N/A":>27} | Pass date: {pass_date or "N/A":>27} | Completion date: {end_date or "N/A":>27}')

    def _process_subjects(self, subjects: dict):
        """
        Processes all WaniKani subjects and stores it in the database to be easily accessible.
        This only needs to happen once since the subject info is the same for everyone.

        Parameters
        ----------
        subjects : dict
            The JSON containing the subject info.

        Returns
        -------
        None

        """
        for subject in subjects['data']:
            character_images = None

            try:
                character_images = subject['data']['characters_images']['url']
            except:
                pass  # Only radicals will have an image defined, so this isn't really an error.

            self._db.execute(
                'INSERT INTO subject (id, level, type, image_url, characters) VALUES (%s, %s, %s, %s, %s)',
                (subject['id'], subject['data']['level'], subject['object'], character_images, subject['data']['characters'] or '[Radical]')
            )

    def _process_assignments(self, user_id: int, assignments: dict):
        for assignment in assignments['data']:
            # TODO: Query reviews for more data too.
            id = assignment['id']
            subject_id = assignment['data']['subject_id']
            subject = self._db.query_one(f'SELECT characters FROM subject WHERE id = {subject_id}')['characters']
            srs_stage_name = assignment['data']['srs_stage_name']
            srs_stage_id = assignment['data']['srs_stage']
            start_date = assignment['data']['started_at']
            pass_date = assignment['data']['passed_at']
            end_date = assignment['data']['burned_at']

            self._db.process_row(
                exists_query=f'SELECT EXISTS(SELECT 1 FROM assignment WHERE id = {id}) AS "exists"',
                update_sql='UPDATE assignment SET srs_stage = %s, started_at = %s, passed_at = %s, burned_at = %s WHERE id = %s',
                update_args=(srs_stage_id, start_date, pass_date, end_date, id),
                insert_sql='INSERT INTO assignment (id, user_id, started_at, passed_at, burned_at, srs_stage, subject_id) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                insert_args=(id, user_id, start_date, pass_date, end_date, srs_stage_id, subject_id)
            )

            # Hack to properly pad UTF-8 Japanese characters.
            # Python does not handle multi-byte characters that well, especially considering full vs half width.
            if 'Radical' not in subject:
                padding_to_remove = len(subject) - 1
                subject = f'{subject:>15}'.replace(' ', '', padding_to_remove)
            else:
                subject = f'{subject:>16}'

            print(f'ID: {id:>10} | Subject ID: {subject_id:>8} | Subject: {subject} | SRS stage: {srs_stage_name:>14} ({srs_stage_id}) | Start date: {start_date or "N/A":>27} | Pass date: {pass_date or "N/A":>27} | Completion date: {end_date or "N/A":>27}')

    def _process_srs_stages(self, stages: dict):
        """
        Processes all WaniKani SRS stages and stores it in the database to be easily accessible.
        This only needs to happen once since the stage info is the same for everyone.

        Parameters
        ----------
        stages : dict
            The JSON containing the stage info.

        Returns
        -------
        None

        """
        for stage in stages['data']:
            self._db.execute(
                'INSERT INTO srs_stage (id, name) VALUES (%s, %s)',
                (stage['srs_stage'], stage['srs_stage_name'])
            )

    def _process_reviews(self, user_id: int, reviews: dict):
        for review in reviews['data']:
            id = review['id']
            assignment_id = review['data']['assignment_id']
            starting_srs_stage = review['data']['starting_srs_stage']
            ending_srs_stage = review['data']['ending_srs_stage']
            incorrect_meaning_answers = review['data']['incorrect_meaning_answers']
            incorrect_reading_answers = review['data']['incorrect_reading_answers']

            self._db.process_row(
                exists_query=f'SELECT EXISTS(SELECT 1 FROM review WHERE id = {id}) AS "exists"',
                update_sql='UPDATE review SET starting_srs_stage = %s, ending_srs_stage = %s, incorrect_meaning_answers = %s, incorrect_reading_answers = %s WHERE id = %s',
                update_args=(starting_srs_stage, ending_srs_stage, incorrect_meaning_answers, incorrect_reading_answers, id),
                insert_sql='INSERT INTO review (id, user_id, assignment_id, starting_srs_stage, ending_srs_stage, incorrect_meaning_answers, incorrect_reading_answers) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                insert_args=(id, user_id, assignment_id, starting_srs_stage, ending_srs_stage, incorrect_meaning_answers, incorrect_reading_answers)
            )

            print(f'ID: {id:>10} | Assignment ID: {assignment_id:>10} | Starting stage: {starting_srs_stage:>2} | Ending stage: {ending_srs_stage:>2} | Incorrect meaning answers: {incorrect_meaning_answers:>4} | Incorrect reading answers: {incorrect_reading_answers:>4}')

    def _analyze_level_progressions(self):
        level_stats = {}
        durations = {
            'pass': [],
            'complete': []
        }

        level_progs = self._db.query_all('SELECT * FROM level_progression')

        for level_prog in level_progs:
            level = level_prog['level']
            start_date = level_prog['started_at']
            pass_date = level_prog['passed_at']
            end_date = level_prog['completed_at']

            level_stats[level] = {
                'pass_duration': self._calculate_time_delta(start_date, pass_date),
                'complete_duration': self._calculate_time_delta(start_date, end_date)
            }

            if level_stats[level]['pass_duration'] is not None:
                durations['pass'].append(level_stats[level]['pass_duration'])

            if level_stats[level]['complete_duration'] is not None:
                durations['complete'].append(level_stats[level]['complete_duration'])

            level_stats['aggregates'] = {
                'pass': self._get_aggregates(durations['pass']),
                'complete': self._get_aggregates(durations['complete'])
            }

        return level_stats

    def _analyze_assignments(self):
        pass

    def _analyze_reviews(self):
        pass


if __name__ == '__main__':
    api_key = None

    try:
        with open('secret.json', 'r') as file:
            try:
                api_key = json.load(file)['api_key']
                print('API key loaded.\n')
            except Exception as e:
                logging.debug(f'{datetime.now()} | ERROR: {str(e)}')
                raise SystemExit(f'An error occurred while loading the JSON: {e}')
    except IOError as e:
        logging.debug(f'{datetime.now()} | ERROR: {str(e)}')
        raise SystemExit('Unable to load the API key.')

    client = WaniKaniClient(api_key)
    db = PostgresClient(dbname='postgres', user='postgres', password='postgres')
    analyzer = Analyzer(wanikani=client, db=db)

    try:
        analyzer.analyze_user_info()
    finally:
        db.close()
