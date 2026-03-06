from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from insider.models import Invitation


class InvitationSendForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["email"]  # optional: add role if you want to pre-assign

User = get_user_model()

class InvitationAcceptForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    avatar = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'avatar', 'username', 'password1', 'password2')

