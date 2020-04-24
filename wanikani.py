import requests


class WaniKaniClient:
    API_URI = 'https://api.wanikani.com/v2/'

    def __init__(self, api_key):
        self.__auth_header = {
            'Authorization': f'Bearer {api_key}'
        }

    def _perform_paginated_get_request(self, endpoint):
        session = requests.Session()
        response = session.get(url=endpoint, headers=self.__auth_header)
        response.raise_for_status()

        page = response.json()
        yield page

        while page['pages']['next_url'] is not None:
            response = session.get(url=page['pages']['next_url'], headers=self.__auth_header)
            response.raise_for_status()
            page = response.json()
            yield page

    def get_user(self):
        response = requests.get(url=WaniKaniClient.API_URI + 'user', headers=self.__auth_header)
        response.raise_for_status()

        user = response.json()
        username = user['data']['username']
        level = user['data']['level']

        print(f'Username: {username}\nLevel: {level}\n')

    def get_level_progressions(self):
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'level_progressions')

    def get_assignments(self):
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'assignments')