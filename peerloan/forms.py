# Import the forms library to create forms
from django import forms

# Import the CaptchaField from 'django-simple-captcha'
from captcha.fields import CaptchaField

# Create form class for the Registration form
class CaptchaForm(forms.Form):
	captcha = CaptchaField()