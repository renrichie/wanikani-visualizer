import json
import requests

API_URI = 'https://api.wanikani.com/v2/'

class Scraper:
    def __init__(self, api_key):
        self.__auth_header = {
            'Authorization': f'Bearer {api_key}'
        }

    def _perform_request(self, method: str, endpoint: str, headers: dict = None, params: dict = None, body: dict = None):
        response = requests.request(method=method, url=endpoint, headers=headers, params=params, json=body)
        response.raise_for_status()

        return response.json()

    def get_user(self):
        user = self._perform_request(method='GET', endpoint=API_URI + 'user', headers=self.__auth_header)
        username = user['data']['username']
        level = user['data']['level']

        print(f'Username: {username}\nLevel: {level}\n')

    def get_all_level_progressions(self):
        print('======== LEVEL PROGRESSION DATA ========')
        # TODO: Handle pagination using pages['next_url'] even though it's set to 500 per page and there are only 60 levels.
        #       The pagination amount could change in the future.
        level_progressions = self._perform_request(method='GET', endpoint=API_URI + 'level_progressions', headers=self.__auth_header)

        for level_prog in level_progressions['data']:
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at'] or 'N/A'
            pass_date = level_prog['data']['passed_at'] or 'N/A'
            end_date = level_prog['data']['completed_at'] or 'N/A'
            print(f'Level: {level} | Start date: {start_date} | Pass date: {pass_date} | Completion date: {end_date}')

    def get_all_assignments(self):
        print('\n======== ASSIGNMENT PROGRESS DATA ========')
        assignments = self._perform_request(method='GET', endpoint=API_URI + 'assignments', headers=self.__auth_header)

        # TODO: Handle pagination.
        for assignment in assignments['data']:
            # TODO: Also consider srs_stage and match subject_id to actual character(s).
            #       Query reviews for more data too.
            subject_id = assignment['data']['subject_id']
            start_date = assignment['data']['started_at'] or 'N/A'
            pass_date = assignment['data']['passed_at'] or 'N/A'
            end_date = assignment['data']['burned_at'] or 'N/A'
            print(f'Subject ID: {subject_id} | Start date: {start_date} | Pass date: {pass_date} | Completion date: {end_date}')

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

    scraper = Scraper(api_key)
    scraper.get_user()
    scraper.get_all_level_progressions()
    scraper.get_all_assignments()
