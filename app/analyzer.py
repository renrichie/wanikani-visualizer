import json
import logging
import pprint
from datetime import datetime
from typing import Union


from app import database
from app.models import Account, LevelProgression, Assignment, Stage, Review, Subject


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
    def __init__(self, wanikani, db):  # Duck-typed for easier mocking and dependency injection.
        self._client = wanikani
        self._db = db
        self._cache = {}

    def analyze_user_info(self) -> dict:
        """
        Processes all the user's info through the WaniKani API.

        Returns
        -------
        dict
            JSON containing all the user data.

        """
        self._clean_stale_data()
        self._initialize_static_info()

        user = self._client.get_user()
        id = self._process_user(user_info=user)

        # Query the API for newer info if we're past our 10 minute cache time or if the data doesn't exist.
        if not self._cache[id]:
            logging.info('Processing new data...')
            print('======== LEVEL PROGRESSION DATA ========')

            for page in self._client.get_level_progressions():
                self._process_level_progressions(user_id=id, progressions=page)

            database.session.flush()

            print('\n======== ASSIGNMENT PROGRESS DATA ========')

            for page in self._client.get_assignments():
                self._process_assignments(user_id=id, assignments=page)

            database.session.flush()

            print('\n======== REVIEW DATA ========')

            for page in self._client.get_reviews():
                self._process_reviews(user_id=id, reviews=page)

            database.session.commit()

        user_stats = {
            'user': {
                'level': user['level'],
                'username': user['username'],
                'start_date': user['started_at']
            },
            'level_progressions': self._analyze_level_progressions(user_id=id),
            'assignments': self._analyze_assignments(user_id=id),
            'reviews': self._analyze_reviews(user_id=id)
        }

        pretty_print(user_stats)

        return user_stats

    def _clean_stale_data(self):
        """
        Removes all data from the database every week to ensure its accuracy.

        Returns
        -------
        None

        """
        current_time = datetime.utcnow()

        # Oldest record can be determined by looking at the create dates if any records exist.
        # If there are no records, then the current time would be the oldest since we are about to make one.
        oldest_record = self._db.query_one('SELECT create_date FROM account ORDER BY create_date ASC LIMIT 1')
        old_time = oldest_record['create_date'] if oldest_record else current_time

        time_elapsed_since_first_query = self._calculate_time_delta(old_time, current_time)

        if time_elapsed_since_first_query >= (60 * 60 * 24 * 7):
            logging.info(f'Time elapsed since first query: {time_elapsed_since_first_query} seconds')
            logging.info('Clearing stale data...')
            self._db.clear_tables(
                ['review', 'assignment', 'level_progression', 'stage', 'subject', 'account']
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
            logging.info('Processing subject info...')
            for page in self._client.get_subjects():
                self._process_subjects(subjects=page)

        if self._db.query_one('SELECT COUNT(*) FROM stage')['count'] == 0:
            logging.info('Processing SRS stage info...')
            self._process_srs_stages(stages=self._client.get_srs_stages())  # No need to paginate since there are so few.

        database.session.commit()

    def _calculate_time_delta(self, first_date: Union[str, datetime], second_date: Union[str, datetime]) -> Union[float, None]:
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
        Union[float, None]
            The number of seconds elapsed between the two datetimes. Returns None when either date is None.

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

        user = Account.query.filter_by(username=username).first()

        current_time = datetime.utcnow()

        if user:
            user_id = user.id
            last_queried_time = user.last_queried
            time_since_last_query = self._calculate_time_delta(last_queried_time, current_time) or 0
            use_cached_values = time_since_last_query < (10 * 60)

            if not use_cached_values:
                user.last_queried = current_time
                database.session.commit()

            self._cache[user_id] = use_cached_values  # Use cached data for 10 minutes to prevent unnecessary load.

            return user_id

        user = Account()
        user.level = user_info['level']
        user.username = username
        database.session.add(user)
        database.session.commit()

        self._cache[user.id] = False

        return user.id

    def _process_level_progressions(self, user_id: int, progressions: dict):
        """
        Processes the user's WaniKani level progression info and stores it in the database to be easily accessible.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.
        progressions : dict
            The JSON containing the level progression info.

        Returns
        -------
        None

        """
        for level_prog in progressions['data']:
            id = level_prog['id']
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at']
            pass_date = level_prog['data']['passed_at']
            end_date = level_prog['data']['completed_at']

            lvl = LevelProgression.query.filter_by(id=id).first()

            if lvl:
                lvl.started_at = start_date
                lvl.passed_at = pass_date
                lvl.completed_at = end_date
            else:
                lvl = LevelProgression()
                lvl.id = id
                lvl.level = level
                lvl.user_id = user_id
                lvl.started_at = start_date
                lvl.passed_at = pass_date
                lvl.completed_at = end_date
                database.session.add(lvl)

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
            character_image = None

            # Get an easily usable image (PNG) instead of a vector.
            if subject['object'] == 'radical' and subject['data']['characters'] is None:
                for image in subject['data']['character_images']:
                    if image['content_type'] == 'image/png':
                        character_image = image['url']
                        break

            sbjt = Subject()
            sbjt.id = subject['id']
            sbjt.level = subject['data']['level']
            sbjt.type = subject['object']
            sbjt.image_url = character_image
            sbjt.characters = subject['data']['characters'] or '[Radical]'
            database.session.add(sbjt)

    def _process_assignments(self, user_id: int, assignments: dict):
        """
        Processes the user's WaniKani assignments and stores it in the database to be easily accessible.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.
        assignments : dict
            The JSON containing the review info.

        Returns
        -------
        None

        """
        for assignment in assignments['data']:
            id = assignment['id']
            subject_id = assignment['data']['subject_id']
            subject = self._db.query_one(f'SELECT characters FROM subject WHERE id = {subject_id}')['characters']
            srs_stage_name = assignment['data']['srs_stage_name']
            srs_stage_id = assignment['data']['srs_stage']
            start_date = assignment['data']['started_at']
            pass_date = assignment['data']['passed_at']
            end_date = assignment['data']['burned_at']

            asmt = Assignment.query.filter_by(id=id).first()

            if asmt:
                asmt.srs_stage = srs_stage_id
                asmt.started_at = start_date
                asmt.passed_at = pass_date
                asmt.burned_at = end_date
            else:
                asmt = Assignment()
                asmt.id = id
                asmt.user_id = user_id
                asmt.srs_stage = srs_stage_id
                asmt.started_at = start_date
                asmt.passed_at = pass_date
                asmt.burned_at = end_date
                asmt.subject_id = subject_id
                database.session.add(asmt)

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
            srs_stage = Stage()
            srs_stage.id = stage['srs_stage']
            srs_stage.name = stage['srs_stage_name']
            database.session.add(srs_stage)

    def _process_reviews(self, user_id: int, reviews: dict):
        """
        Processes the user's WaniKani reviews and stores it in the database to be easily accessible.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.
        reviews : dict
            The JSON containing the review info.

        Returns
        -------
        None

        """
        for review in reviews['data']:
            id = review['id']
            assignment_id = review['data']['assignment_id']
            starting_srs_stage = review['data']['starting_srs_stage']
            ending_srs_stage = review['data']['ending_srs_stage']
            incorrect_meaning_answers = review['data']['incorrect_meaning_answers']
            incorrect_reading_answers = review['data']['incorrect_reading_answers']

            rvw = Review.query.filter_by(id=id).first()

            if rvw:
                rvw.starting_srs_stage = starting_srs_stage
                rvw.ending_srs_stage = ending_srs_stage
                rvw.incorrect_meaning_answers = incorrect_meaning_answers
                rvw.incorrect_reading_answers = incorrect_reading_answers
            else:
                rvw = Review()
                rvw.id = id
                rvw.user_id = user_id
                rvw.assignment_id = assignment_id
                rvw.starting_srs_stage = starting_srs_stage
                rvw.ending_srs_stage = ending_srs_stage
                rvw.incorrect_meaning_answers = incorrect_meaning_answers
                rvw.incorrect_reading_answers = incorrect_reading_answers
                database.session.add(rvw)

            print(f'ID: {id:>10} | Assignment ID: {assignment_id:>10} | Starting stage: {starting_srs_stage:>2} | Ending stage: {ending_srs_stage:>2} | Incorrect meaning answers: {incorrect_meaning_answers:>4} | Incorrect reading answers: {incorrect_reading_answers:>4}')

    def _analyze_level_progressions(self, user_id: int):
        """
        Performs some simple analytics on the user's level progression data, such as aggregates and totals.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.

        Returns
        -------
        dict
            The result of the analysis in JSON format.

        """
        stats = {}

        user = Account.query.filter_by(id=user_id).first()

        if user is None:
            raise Exception("User not found.")

        stats['totals'] = {
            'total': user.levels.count(),
            'completion': {
                'started': user.levels.filter(LevelProgression.passed_at.is_(None)).count(),
                'passed': user.levels.filter(LevelProgression.passed_at.isnot(None)).count(),
                'completed': user.levels.filter(LevelProgression.completed_at.isnot(None)).count()
            }
        }

        stats['levels'] = self._db.query_all(
            "SELECT level, "
            "DATEDIFF('seconds', started_at, passed_at) AS pass_duration, "
            "DATEDIFF('seconds', started_at, completed_at) AS complete_duration "
            "FROM level_progression "
            f"WHERE user_id = {user_id} "
            "ORDER BY level ASC"
        )

        stats['aggregates'] = {}

        stats['aggregates']['medians'] = self._db.query_one(
            "SELECT MEDIAN(DATEDIFF('seconds', started_at, passed_at)) AS pass_duration, "
            "MEDIAN(DATEDIFF('seconds', started_at, completed_at)) AS complete_duration "
            "FROM level_progression "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['averages'] = self._db.query_one(
            "SELECT AVG(DATEDIFF('seconds', started_at, passed_at)) AS pass_duration, "
            "AVG(DATEDIFF('seconds', started_at, completed_at)) AS complete_duration "
            "FROM level_progression "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['highest'] = {}
        stats['aggregates']['lowest'] = {}

        # Grab the data in sorted order so we can get both top and bottom N values, where N is arbitrary.
        pass_durations = self._db.query_all(
            "WITH pass_aggregate AS ("
            "SELECT level, DATEDIFF('seconds', started_at, passed_at) AS pass_duration "
            "FROM level_progression "
            f"WHERE user_id = {user_id}) "
            "SELECT * "
            "FROM pass_aggregate "
            "WHERE pass_duration IS NOT NULL "
            "ORDER BY pass_duration DESC"
        )

        stats['aggregates']['highest']['pass_duration'] = pass_durations[:3]
        stats['aggregates']['lowest']['pass_duration'] = pass_durations[-3:]
        stats['aggregates']['lowest']['pass_duration'].reverse()  # Reverse to get the lowest N in correct order.

        complete_durations = self._db.query_all(
            "WITH complete_aggregate AS ("
            "SELECT level, DATEDIFF('seconds', started_at, completed_at) AS complete_duration "
            "FROM level_progression "
            f"WHERE user_id = {user_id}) "
            "SELECT * "
            "FROM complete_aggregate "
            "WHERE complete_duration IS NOT NULL "
            "ORDER BY complete_duration DESC"
        )

        stats['aggregates']['highest']['complete_duration'] = complete_durations[:3]
        stats['aggregates']['lowest']['complete_duration'] = complete_durations[-3:]
        stats['aggregates']['lowest']['complete_duration'].reverse()

        return stats  # Might need to convert this? lambda obj: str(obj) if isinstance(obj, datetime) else obj

    def _analyze_assignments(self, user_id: int) -> dict:
        """
        Performs some simple analytics on the user's assignment data, such as aggregates and totals.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.

        Returns
        -------
        dict
            The result of the analysis in JSON format.

        """
        stats = {}

        total_query_base = f'SELECT COUNT(*) FROM assignment WHERE user_id = {user_id}'
        stats['totals'] = {
            'total': self._db.query_one(total_query_base),
            'completion': {
                'started': self._db.query_one(f'{total_query_base} AND passed_at IS NULL'),
                'passed': self._db.query_one(f'{total_query_base} AND passed_at IS NOT NULL'),
                'completed': self._db.query_one(f'{total_query_base} AND burned_at IS NOT NULL')
            },
            'stage': self._db.query_all(
                "SELECT a.srs_stage, s.name, COUNT(*) "
                "FROM assignment a, stage s "
                f"WHERE a.user_id = {user_id} AND a.srs_stage = s.id "
                "GROUP BY a.srs_stage, s.name "
                "ORDER BY a.srs_stage ASC"
            ),
            'level': self._db.query_all(
                "SELECT s.level, COUNT(*) "
                "FROM assignment a, subject s "
                f"WHERE a.user_id = {user_id} AND a.subject_id = s.id "
                "GROUP BY s.level "
                "ORDER BY s.level ASC"
            ),
            'type': self._db.query_all(
                "SELECT s.type, COUNT(*) "
                "FROM assignment a, subject s "
                f"WHERE a.user_id = {user_id} AND a.subject_id = s.id "
                "GROUP BY s.type"
            )
        }

        stats['aggregates'] = {}

        stats['aggregates']['medians'] = self._db.query_one(
            "SELECT MEDIAN(DATEDIFF('seconds', started_at, passed_at)) AS pass_duration, "
            "MEDIAN(DATEDIFF('seconds', started_at, burned_at)) AS complete_duration "
            "FROM assignment "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['averages'] = self._db.query_one(
            "SELECT AVG(DATEDIFF('seconds', started_at, passed_at)) AS pass_duration, "
            "AVG(DATEDIFF('seconds', started_at, burned_at)) AS complete_duration "
            "FROM assignment "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['highest'] = {}
        stats['aggregates']['lowest'] = {}

        # Grab the data in sorted order so we can get both top and bottom N values, where N is arbitrary.
        pass_durations = self._db.query_all(
            "WITH pass_aggregate AS ("
            "SELECT s.type, s.characters, s.image_url, "
            "DATEDIFF('seconds', a.started_at, a.passed_at) AS pass_duration "
            "FROM assignment a, subject s "
            f"WHERE a.user_id = {user_id} AND a.subject_id = s.id) "
            "SELECT * "
            "FROM pass_aggregate "
            "WHERE pass_duration IS NOT NULL "
            "ORDER BY pass_duration DESC"
        )

        stats['aggregates']['highest']['pass_duration'] = pass_durations[:3]
        stats['aggregates']['lowest']['pass_duration'] = pass_durations[-3:]
        stats['aggregates']['lowest']['pass_duration'].reverse()  # Reverse to get the lowest N in correct order.

        complete_durations = self._db.query_all(
            "WITH complete_aggregate AS ("
            "SELECT s.type, s.characters, s.image_url, "
            "DATEDIFF('seconds', started_at, burned_at) AS complete_duration "
            "FROM assignment a, subject s "
            f"WHERE user_id = {user_id} AND a.subject_id = s.id) "
            "SELECT * "
            "FROM complete_aggregate "
            "WHERE complete_duration IS NOT NULL "
            "ORDER BY complete_duration DESC"
        )

        stats['aggregates']['highest']['complete_duration'] = complete_durations[:3]
        stats['aggregates']['lowest']['complete_duration'] = complete_durations[-3:]
        stats['aggregates']['lowest']['complete_duration'].reverse()

        stats['assignments'] = self._db.query_all(
            "SELECT s.type, s.characters, s.image_url, "
            "DATEDIFF('seconds', a.started_at, a.passed_at) AS pass_duration,"
            "DATEDIFF('seconds', started_at, burned_at) AS complete_duration "
            "FROM assignment a, subject s "
            f"WHERE a.user_id = {user_id} AND a.subject_id = s.id"
        )

        return stats

    def _analyze_reviews(self, user_id: int) -> dict:
        """
        Performs some simple analytics on the user's review data, such as aggregates and totals.

        Parameters
        ----------
        user_id : int
            The user's unique ID in the database, not WaniKani's.

        Returns
        -------
        dict
            The result of the analysis in JSON format.

        """
        stats = {}

        total_query_base = f'SELECT COUNT(*) FROM review WHERE user_id = {user_id}'
        stats['totals'] = {
            'total': self._db.query_one(total_query_base),
            'stage': self._db.query_all(  # The number of reviews required per stage - should be graphed.
                "SELECT r.starting_srs_stage, s.name, COUNT(*) "
                "FROM review r, assignment a, stage s "
                f"WHERE a.user_id = {user_id} AND r.user_id = {user_id} AND r.assignment_id = a.id AND r.starting_srs_stage = s.id "
                "GROUP BY r.starting_srs_stage, s.name "
                "ORDER BY r.starting_srs_stage ASC"
            ),
            'level': self._db.query_all(
                "SELECT s.level, COUNT(*) "
                "FROM review r, assignment a, subject s "
                f"WHERE a.user_id = {user_id} AND r.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id "
                "GROUP BY s.level "
                "ORDER BY s.level ASC"
            ),
            'type': self._db.query_all(
                "SELECT s.type, COUNT(*) "
                "FROM review r, assignment a, subject s "
                f"WHERE a.user_id = {user_id} AND r.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id "
                "GROUP BY s.type"
            ),
            'accuracy': {
                'reading': self._db.query_all(
                    "SELECT s.type, "
                    "ROUND((1 - (SUM(r.incorrect_reading_answers) * 1.0 / (COUNT(*) + SUM(r.incorrect_reading_answers)))) * 100) AS accuracy "
                    "FROM review r, assignment a, subject s "
                    f"WHERE a.user_id = {user_id} AND r.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id AND s.type not like 'radical' "
                    "GROUP BY s.type"
                ),
                'meaning': self._db.query_all(
                    "SELECT s.type, "
                    "ROUND((1 - (SUM(r.incorrect_meaning_answers) * 1.0 / (COUNT(*) + SUM(r.incorrect_meaning_answers)))) * 100) AS accuracy "
                    "FROM review r, assignment a, subject s "
                    f"WHERE a.user_id = {user_id} AND r.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id "
                    "GROUP BY s.type"
                )
            }
        }

        stats['aggregates'] = {}

        stats['aggregates']['medians'] = self._db.query_one(
            "SELECT MEDIAN(incorrect_meaning_answers) AS incorrect_meanings, "
            "MEDIAN(incorrect_reading_answers) AS incorrect_readings,"
            "MEDIAN(ending_srs_stage - starting_srs_stage) AS srs_stage_change "
            "FROM review "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['averages'] = self._db.query_one(
            "SELECT AVG(incorrect_meaning_answers) AS incorrect_meanings, "
            "AVG(incorrect_reading_answers) AS incorrect_readings,"
            "AVG(ending_srs_stage - starting_srs_stage) AS srs_stage_change "
            "FROM review "
            f"WHERE user_id = {user_id}"
        )

        stats['aggregates']['highest'] = {}

        # We only care about highest number of incorrect answers since the lowest is obviously 0.
        # This shows the subjects with the most incorrect answers overall.
        stats['aggregates']['highest']['incorrect_meaning_answers'] = self._db.query_all(
            "SELECT s.type, s.characters, s.image_url, SUM(r.incorrect_meaning_answers) AS incorrect_meaning_answers "
            "FROM review r, assignment a, subject s "
            f"WHERE r.user_id = {user_id} AND a.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id "
            "GROUP BY s.id "
            "ORDER BY incorrect_meaning_answers DESC "
            "LIMIT 3"
        )

        stats['aggregates']['highest']['incorrect_reading_answers'] = self._db.query_all(
            "SELECT s.type, s.characters, s.image_url, SUM(r.incorrect_reading_answers) AS incorrect_reading_answers "
            "FROM review r, assignment a, subject s "
            f"WHERE r.user_id = {user_id} AND a.user_id = {user_id} AND r.assignment_id = a.id AND a.subject_id = s.id "
            "GROUP BY s.id "
            "ORDER BY incorrect_reading_answers DESC "
            "LIMIT 3"
        )

        return stats


def pretty_print(data):
    """
    Simple helper method to pretty print values for debugging.

    Parameters
    ----------
    data : Any

    Returns
    -------
    None

    """
    pp = pprint.PrettyPrinter()
    pp.pprint(data)


if __name__ == '__main__':
    import os

    api_key = None
    basedir = os.path.abspath(os.path.dirname(__file__))
    secret_file = os.path.join(basedir, 'secret.json')

    try:
        with open(secret_file, 'r') as file:
            try:
                api_key = json.load(file)['api_key']
                logging.debug('API key loaded.\n')
            except Exception as e:
                logging.critical(f'ERROR: {str(e)}')
                raise SystemExit(f'An error occurred while loading the JSON: {e}')
    except IOError as e:
        logging.critical(f'ERROR: {str(e)}')
        raise SystemExit('Unable to load the API key.')

    from wanikani import WaniKaniClient, DATE_FORMAT
    from psql import PostgresClient

    client = WaniKaniClient(api_key)
    db = PostgresClient(dbname='postgres', user='postgres', password='postgres')
    analyzer = Analyzer(wanikani=client, db=db)

    try:
        analyzer.analyze_user_info()
    finally:
        db.close()
