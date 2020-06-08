import os
import logging.config
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap


from config import Config

app = Flask(__name__)
app.config.from_object(Config)

bootstrap = Bootstrap(app)

database = SQLAlchemy(app)
migrate = Migrate(app, database)

if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = logging.FileHandler('logs/{:%Y-%m-%d}.log'.format(datetime.utcnow()))
file_handler.setFormatter(
    logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Wanikani analyzer starting...')

from app import routes, models
