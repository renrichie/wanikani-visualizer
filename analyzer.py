import json

from wanikani import WaniKaniClient


class Analyzer:
    def process_level_progressions(self, progressions):
        for level_prog in progressions['data']:
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at'] or 'N/A'
            pass_date = level_prog['data']['passed_at'] or 'N/A'
            end_date = level_prog['data']['completed_at'] or 'N/A'
            print(f'Level: {level} | Start date: {start_date} | Pass date: {pass_date} | Completion date: {end_date}')

    def process_assignments(self, assignments):
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

    client = WaniKaniClient(api_key)
    client.get_user()

    analyzer = Analyzer()

    print('======== LEVEL PROGRESSION DATA ========')

    for page in client.get_level_progressions():
        analyzer.process_level_progressions(page)

    print('\n======== ASSIGNMENT PROGRESS DATA ========')

    for page in client.get_assignments():
        analyzer.process_assignments(page)
