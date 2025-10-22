from pathlib import Path
import os
from decouple import config, Csv # Adicione Csv à importação

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECRET_KEY: Sua configuração está perfeita.
# Ela será lida do arquivo .env localmente, ou das variáveis de ambiente no servidor.
SECRET_KEY = config('SECRET_KEY')

# DEBUG: Sua configuração está ótima.
# O padrão `default=False` é mais seguro. Para rodar localmente, certifique-se
# de ter `DEBUG=True` no seu arquivo .env
DEBUG = config('DEBUG', default=False, cast=bool)

# ALLOWED_HOSTS: Esta é a principal mudança.
# Em vez de uma lista vazia, vamos ler os domínios permitidos do ambiente.
# No seu .env local, você pode ter: ALLOWED_HOSTS=127.0.0.1,localhost
# No PythonAnywhere, você definirá: ALLOWED_HOSTS=seunome.pythonanywhere.com
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'cadastros',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gestao_escola.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gestao_escola.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i1n/

LANGUAGE_CODE = 'pt-br'

# MUDANÇA RECOMENDADA: Ajuste o TIME_ZONE para refletir sua localidade.
# Isso garante que datas e horas salvas no banco de dados sejam consistentes.
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'

# MUDANÇA NECESSÁRIA PARA DEPLOY:
# STATIC_ROOT é a pasta para onde o Django irá copiar todos os arquivos estáticos
# quando você rodar o comando `python manage.py collectstatic`.
# O servidor de produção (Nginx, Apache) será configurado para usar esta pasta.
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'), # BASE_DIR aponta para mms_portal/
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'cadastros:portal_login'
LOGIN_REDIRECT_URL = 'cadastros:portal_aluno' # Redirecionamento padrão para o portal do aluno
LOGOUT_REDIRECT_URL = 'cadastros:portal_login' # Para onde vai após o logout
