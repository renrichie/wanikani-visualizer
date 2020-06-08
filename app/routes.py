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
        client = WaniKaniClient(form.api_key.data)
        db = PostgresClient(dbname='postgres', user='postgres', password='postgres')
        analyzer = Analyzer(wanikani=client, db=db)
        info = analyzer.analyze_user_info()

        form.api_key.data = ''

        # Just re-render everything at the base URL to circumvent people visiting a separate stats page
        # before they even start an analysis.
        return render_template('overall_stats.html', title='Overall Stats', profile_pic=app.config['LOGO'], data=info)

    return render_template('index.html', title='Home', form=form, logo=app.config['LOGO'])
