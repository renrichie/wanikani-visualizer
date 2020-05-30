from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError


class AuthenticationForm(FlaskForm):
    api_key = StringField('API Key', validators=[DataRequired()])
    submit = SubmitField('Analyze')
