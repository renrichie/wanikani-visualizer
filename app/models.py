from app import app, database


class Account(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    level = database.Column(database.Integer)
    username = database.Column(database.String(16), unique=True, nullable=False)
    last_queried = database.Column(database.DateTime, server_default=database.func.now(), server_onupdate=database.func.now())
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())

    assignments = database.relationship('Assignment', backref='user', lazy='dynamic')
    levels = database.relationship('LevelProgression', backref='user', lazy='dynamic')
    reviews = database.relationship('Review', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}, Level {self.level}>'


class Assignment(database.Model):
    id = database.Column(database.Integer, primary_key=True, autoincrement=False)
    user_id = database.Column(database.Integer, database.ForeignKey('account.id'), nullable=False)
    started_at = database.Column(database.DateTime)
    passed_at = database.Column(database.DateTime)
    burned_at = database.Column(database.DateTime)
    srs_stage = database.Column(database.Integer, database.ForeignKey('stage.id'), nullable=False)
    subject_id = database.Column(database.Integer, database.ForeignKey('subject.id'), nullable=False)
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())
    reviews = database.relationship('Review', backref='assignment', lazy='dynamic')

    def __repr__(self):
        return f'<User ID {self.user_id}, Assignment ID {self.id}, Subject ID {self.subject_id}>'


class LevelProgression(database.Model):
    id = database.Column(database.Integer, primary_key=True, autoincrement=False)
    level = database.Column(database.Integer)
    user_id = database.Column(database.Integer, database.ForeignKey('account.id'), nullable=False)
    started_at = database.Column(database.DateTime)
    passed_at = database.Column(database.DateTime)
    completed_at = database.Column(database.DateTime)
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())

    def __repr__(self):
        return f'<User ID {self.user_id}, Level ID {self.id}, Level {self.level}>'


class Review(database.Model):
    id = database.Column(database.Integer, primary_key=True, autoincrement=False)
    user_id = database.Column(database.Integer, database.ForeignKey('account.id'), nullable=False)
    assignment_id = database.Column(database.Integer, database.ForeignKey('assignment.id'), nullable=False)
    starting_srs_stage = database.Column(database.Integer, database.ForeignKey('stage.id'), nullable=False)
    ending_srs_stage = database.Column(database.Integer, database.ForeignKey('stage.id'), nullable=False)
    incorrect_meaning_answers = database.Column(database.Integer)
    incorrect_reading_answers = database.Column(database.Integer)
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())

    def __repr__(self):
        return f'<User ID: {self.user_id}, Review ID {self.id}, Assignment ID {self.assignment_id}>'


class Stage(database.Model):
    id = database.Column(database.Integer, primary_key=True, autoincrement=False)
    name = database.Column(database.String(30), unique=True)
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())

    def __repr__(self):
        return f'<User ID: {self.user_id}, Stage ID {self.id}, Name {self.name}>'


class Subject(database.Model):
    id = database.Column(database.Integer, primary_key=True, autoincrement=False)
    level = database.Column(database.Integer)
    type = database.Column(database.String(10))
    image_url = database.Column(database.String(256))
    characters = database.Column(database.String(64))
    create_date = database.Column(database.DateTime, server_default=database.func.now())
    modify_date = database.Column(database.DateTime, server_onupdate=database.func.now())

    def __repr__(self):
        return f'<ID: {self.id}, Level {self.level}, Type {self.type}, Characters {self.characters}>'
