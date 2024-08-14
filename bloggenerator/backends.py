# your_app_name/backends.py

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # Attempt to get the user by their email address
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            return None
        else:
            # Check the password and return the user if it's correct
            if user.check_password(password):
                return user
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
