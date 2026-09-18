from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Email, Regexp, EqualTo
from wtforms import ValidationError
from ..models import User, Bar, Drink


class EditProfileForm(FlaskForm):
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    username = StringField('Username', validators=[
        DataRequired(),
        Length(1, 64),
        Regexp(
            '^[A-Za-z][A-Za-z0-9_.]*$',
            message='Usernames must have only letters, numbers, dots or underscores'
        )
    ])
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role')

    # 🌟 ДОБАВЛЯЕМ ПОЛЕ ВЫБОРА БАРА ИЗ POSTGRES (coerce=int для ID)
    assigned_bar = SelectField('Assigned Bar', coerce=int)

    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [
            ('user', 'User (Посетитель)'),
            ('manager', 'Manager (Управляющий)'),
            ('administrator', 'Administrator (Админ)')
        ]

        # 🌟 ДИНАМИЧЕСКИЙ СБОР БАРОВ ИЗ СУБД ПРИ ИНИЦИАЛИЗАЦИИ ФОРМЫ
        # Импортируем модель Bar локально, чтобы избежать циклического импорта
        from ..models import Bar
        all_bars = Bar.query.order_by(Bar.name.asc()).all()
        self.assigned_bar.choices = [(0, '— Не назначен —')] + [(bar.id, f"{bar.name} ({bar.city})") for bar in
                                                                all_bars]

        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if field.data != self.user.username and User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')
