import json

from wanikani import WaniKaniClient


class Analyzer:
    def process_level_progressions(self, progressions):
        for level_prog in progressions['data']:
            level = level_prog['data']['level']
            start_date = level_prog['data']['started_at'] or 'N/A'
            pass_date = level_prog['data']['passed_at'] or 'N/A'
            end_date = level_prog['data']['completed_at'] or 'N/A'
            print(f'Level: {level:>2} | Start date: {start_date:>27} | Pass date: {pass_date:>27} | Completion date: {end_date:>27}')

    def process_assignments(self, assignments, subjects):
        for assignment in assignments['data']:
            # TODO: Query reviews for more data too.
            subject_id = assignment['data']['subject_id']
            subject = subjects[subject_id]  # Radicals use an image not a character.
            srs_stage_name = assignment['data']['srs_stage_name']
            srs_stage_id = assignment['data']['srs_stage']
            start_date = assignment['data']['started_at'] or 'N/A'
            pass_date = assignment['data']['passed_at'] or 'N/A'
            end_date = assignment['data']['burned_at'] or 'N/A'

            # Hack to properly pad UTF-8 Japanese characters.
            # Python does not handle multi-byte characters that well, especially considering full vs half width.
            if 'Radical' not in subject:
                padding_to_remove = len(subject) - 1
                subject = f'{subject:>15}'.replace(' ', '', padding_to_remove)
            else:
                subject = f'{subject:>16}'

            print(f'Subject ID: {subject_id:>8} | Subject: {subject} | SRS stage: {srs_stage_name:>14} ({srs_stage_id}) | Start date: {start_date:>27} | Pass date: {pass_date:>27} | Completion date: {end_date:>27}')


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

    subjects = {}

    for page in client.get_subjects():
        for subject in page['data']:
            subjects[subject['id']] = subject['data']['characters'] or '[Radical]'

    print('\n======== ASSIGNMENT PROGRESS DATA ========')

    for page in client.get_assignments():
        analyzer.process_assignments(page, subjects)
