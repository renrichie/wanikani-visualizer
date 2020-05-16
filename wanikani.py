import requests

# The ISO-8601 datetime format used by WaniKani.
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


class WaniKaniClient:
    """
    This is a simple WaniKani client to get data from the API such as
    user info, level progression, assignments, and subjects.

    Parameters
    ----------
    api_key : str
        The API key to be used to query for info - preferably read-only.
    """
    API_URI = 'https://api.wanikani.com/v2/'

    def __init__(self, api_key: str):
        self.__auth_header = {
            'Authorization': f'Bearer {api_key}'
        }

    def _perform_paginated_get_request(self, endpoint: str) -> dict:
        """
        A generator for generic GET requests that automatically handles pagination for the user.

        Parameters
        ----------
        endpoint : str
            The full endpoint URI to send the GET request to.

        Returns
        -------
        dict
            The JSON response for the current page.

        """
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

    def get_user(self) -> dict:
        """
        Gets the user info.

        Returns
        -------
        dict
            A JSON response containing the user info.

        """
        response = requests.get(url=WaniKaniClient.API_URI + 'user', headers=self.__auth_header)
        response.raise_for_status()

        user = response.json()

        return user['data']

    def get_level_progressions(self):
        """
        A generator for getting all the level progression info.

        Returns
        -------
        dict
            The JSON response for the current page of level progression info.

        """
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'level_progressions')

    def get_assignments(self) -> dict:
        """
        A generator for getting all the assignment info.

        Returns
        -------
        dict
            The JSON response for the current page of assignment info.

        """
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'assignments')

    def get_subjects(self) -> dict:
        """
        A generator for getting all the subject info.

        Returns
        -------
        dict
            The JSON response for the current page of subject info.

        """
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'subjects')

    def get_srs_stages(self) -> dict:
        """
        Gets all the SRS stage info.

        Returns
        -------
        dict
            The JSON response for the current page of SRS stage info.

        """
        session = requests.Session()
        response = session.get(url=WaniKaniClient.API_URI + 'srs_stages', headers=self.__auth_header)
        response.raise_for_status()

        return response.json()

    def get_reviews(self) -> dict:
        """
        A generator for getting all the review info.

        Returns
        -------
        dict
            The JSON response for the current page of review info.

        """
        return self._perform_paginated_get_request(endpoint=WaniKaniClient.API_URI + 'reviews')
