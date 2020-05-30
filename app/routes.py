from flask import render_template, redirect, url_for, flash

from app import app
from app.forms import AuthenticationForm
from .analyzer import Analyzer
from .psql import PostgresClient
from .wanikani import WaniKaniClient


@app.route('/', methods=['GET', 'POST'])
def index():
    form = AuthenticationForm()

    if form.validate_on_submit():
        flash('Analyzing your data!')

        client = WaniKaniClient(form.api_key.data)
        db = PostgresClient(dbname='postgres', user='postgres', password='postgres')
        analyzer = Analyzer(wanikani=client, db=db)
        flash(analyzer.analyze_user_info())

        form.api_key.data = ''

        # TODO: This should be a return statement but will fail due to the result containing floats which you cannot directly JSONify.
        redirect(url_for('index'))

    return render_template('index.html', form=form, logo=app.config['LOGO'])


@app.route('/stats', methods=['GET'])
def stats():
    return render_template('stats.html', logo=app.config['LOGO'])
