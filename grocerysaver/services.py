import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


def build_unique_username_from_email(email):
    base = email.split('@')[0].lower()
    base = re.sub(r'[^a-z0-9_.-]', '', base)[:20] or 'user'

    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        suffix = str(counter)
        username = f'{base[: max(1, 20 - len(suffix))]}{suffix}'
        counter += 1

    return username


def validate_password_or_raise(password, user=None):
    from django.contrib.auth.password_validation import validate_password

    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise DjangoValidationError(list(exc.messages)) from exc


def issue_jwt_pair(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_email_verification(user, token):
    message = (
        'Tu cuenta fue creada. Para verificarla usa este token en el endpoint '
        'POST /api/auth/verify-email/:\n\n'
        f'{token}\n\n'
        'Si no solicitaste este registro, ignora este correo.'
    )

    send_mail(
        subject='Verifica tu cuenta en GrocerySaver',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
