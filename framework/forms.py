# forms.py - Формы приложения
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, BooleanField,
    SelectField, IntegerField, DateField, SubmitField,
    SelectMultipleField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional, Regexp, NumberRange
)
from flask_wtf.file import FileField, FileRequired, FileAllowed
from datetime import date

from models import User   # ← нужен для User.ROLE_CHOICES


# === АУТЕНТИФИКАЦИЯ ===

class LoginForm(FlaskForm):
    """Форма входа в систему"""
    username = StringField(
        'Имя пользователя',
        validators=[DataRequired(message='Введите имя пользователя')]
    )
    password = PasswordField(
        'Пароль',
        validators=[DataRequired(message='Введите пароль')]
    )


# === ПОЛЬЗОВАТЕЛИ ===

class UserForm(FlaskForm):
    """Форма создания/редактирования пользователя.

    При создании пароль обязателен. При редактировании — необязателен
    (если пусто, пароль не меняется).
    """
    username = StringField(
        'Имя пользователя',
        validators=[DataRequired(), Length(min=3, max=80)]
    )
    full_name = StringField(
        'ФИО',
        validators=[Optional(), Length(max=200)],
        description='Отображается в статьях, облаке, почте.',
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )
    password = PasswordField('Пароль')
    confirm_password = PasswordField(
        'Подтвердите пароль',
        validators=[Optional(), EqualTo('password',
                                        message='Пароли должны совпадать')]
    )
    role = SelectField(
        'Роль',
        choices=User.ROLE_CHOICES,
        validators=[DataRequired()],
    )


# === КОНТЕНТ ===

class ArticleForm(FlaskForm):
    """Форма создания/редактирования статьи"""
    title = StringField(
        'Заголовок',
        validators=[DataRequired(), Length(max=200)]
    )
    summary = TextAreaField(
        'Краткое описание',
        validators=[Optional(), Length(max=500)]
    )
    content = TextAreaField(
        'Содержимое',
        validators=[DataRequired()]
    )
    is_published = BooleanField('Опубликовать')


class PageForm(FlaskForm):
    """Форма создания/редактирования страницы"""
    title = StringField('Название',
                        validators=[DataRequired(), Length(max=200)])
    slug = StringField('URL (slug)',
                       validators=[Optional(), Length(max=200)])
    content = TextAreaField('Содержимое (HTML)',
                            validators=[DataRequired()])

    # === Отображение в меню ===
    menu_show = BooleanField('Показать в меню', default=False)

    menu_title = StringField(
        'Название пункта меню',
        validators=[Optional(), Length(max=100)],
        description='Если пусто — используется название страницы',
    )

    menu_position = SelectField(
        'Расположение',
        choices=[
            ('header', 'Верхнее меню'),
            ('sidebar', 'Боковое меню'),
            ('footer', 'Подвал'),
        ],
        default='header',
    )

    menu_parent_id = SelectField(
        'Родительский пункт',
        coerce=int,
        validators=[Optional()],
        default=0,
    )

    menu_order = IntegerField('Порядок', default=0)


class MenuItemForm(FlaskForm):
    """Форма создания/редактирования пункта меню"""
    title = StringField(
        'Название',
        validators=[DataRequired(), Length(max=100)]
    )
    url = StringField(
        'URL',
        validators=[DataRequired(), Length(max=200)]
    )
    order = IntegerField('Порядок', default=0)
    position = SelectField(
        'Позиция',
        choices=[
            ('header', 'Шапка'),
            ('sidebar', 'Боковое меню'),
            ('footer', 'Подвал'),
        ]
    )
    parent_id = SelectField(
        'Родительский пункт',
        coerce=int,
        validators=[Optional()]
    )


# === ФАЙЛОВЫЙ МЕНЕДЖЕР ===

class UploadFileForm(FlaskForm):
    """Форма загрузки файла"""
    file = FileField(
        'Файл',
        validators=[FileRequired(message='Выберите файл')]
    )
    description = StringField(
        'Описание',
        validators=[Optional(), Length(max=500)]
    )
    submit = SubmitField('Загрузить')


class ArchiveForm(FlaskForm):
    """Форма архивации файлов за период"""
    date_from = DateField(
        'Дата с',
        default=lambda: date.today().replace(day=1),
        validators=[DataRequired()]
    )
    date_to = DateField(
        'Дата по',
        default=date.today,
        validators=[DataRequired()]
    )
    file_type = SelectField(
        'Тип файлов',
        choices=[
            ('all', 'Все типы'),
            ('image', 'Изображения'),
            ('video', 'Видео'),
            ('audio', 'Аудио'),
            ('document', 'Документы'),
            ('archive', 'Архивы'),
            ('other', 'Прочее'),
        ],
        default='all'
    )
    archive_format = SelectField(
        'Формат',
        choices=[
            ('zip', 'ZIP (.zip)'),
            ('targz', 'TAR.GZ (.tar.gz)'),
        ],
        default='zip'
    )
    delete_after = BooleanField('Удалить исходные файлы после архивации')
    submit = SubmitField('Создать архив')


# === ГАЛЕРЕЯ ===

class AlbumForm(FlaskForm):
    """Форма создания/редактирования альбома"""
    title = StringField(
        'Название альбома',
        validators=[DataRequired(), Length(max=200)]
    )
    slug = StringField('URL (slug)', validators=[Optional(), Length(max=200)])
    description = TextAreaField('Описание', validators=[Optional()])
    is_published = BooleanField('Опубликовать', default=True)
    order = IntegerField('Порядок сортировки', default=0)
    submit = SubmitField('Сохранить')


class AlbumPhotosForm(FlaskForm):
    """Форма массового добавления фото в альбом из файлового менеджера"""
    file_ids = SelectMultipleField(
        'Файлы',
        coerce=int,
        validators=[Optional()]
    )
    submit = SubmitField('Добавить выбранные')


# === НАСТРОЙКИ САЙТА ===

class SiteSettingsForm(FlaskForm):
    """Форма общих настроек сайта"""
    # Идентификация
    site_title = StringField(
        'Название сайта',
        validators=[DataRequired(), Length(max=200)]
    )
    site_subtitle = StringField(
        'Подзаголовок',
        validators=[Optional(), Length(max=300)]
    )
    site_description = StringField(
        'Описание (meta description)',
        validators=[Optional(), Length(max=500)]
    )
    site_keywords = StringField(
        'Ключевые слова (meta keywords)',
        validators=[Optional(), Length(max=300)]
    )
        # === Базовые URL для кросс-приложений ===
    site_base_url = StringField(
        'Базовый URL сайта',
        validators=[Optional(), Length(max=200)],
        description='Например: http://192.168.2.18 или http://мойсайт.рф'
    )
    cloud_base_url = StringField(
        'URL облака',
        validators=[Optional(), Length(max=200)],
        description='Например: http://192.168.2.18:5001 или http://облако.мойсайт.рф'
    )
    mail_base_url = StringField(
        'URL почты',
        validators=[Optional(), Length(max=200)],
        description='Например: http://192.168.2.18:5002 или http://почта.мойсайт.рф'
    )

    # Элементы интерфейса
    show_header = BooleanField('Показывать шапку сайта', default=True)
    show_header_menu = BooleanField('Показывать верхнее меню', default=True)
    show_sidebar = BooleanField('Показывать боковое меню', default=True)
    show_footer = BooleanField('Показывать подвал', default=True)
    show_slider = BooleanField('Показывать слайдер в шапке', default=False)
    slider_delay_seconds = IntegerField(
        'Время показа каждого слайда (сек)',
        default=5,
        validators=[Optional(), NumberRange(min=1, max=60)]
    )

    # Оформление
    active_theme = SelectField('Тема оформления', choices=[])
    logo_file_id = SelectField('Логотип', coerce=int, validators=[Optional()])
    favicon_file_id = SelectField('Favicon', coerce=int, validators=[Optional()])

    submit = SubmitField('Сохранить настройки')