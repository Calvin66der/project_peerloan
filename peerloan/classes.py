from django.conf import settings

import requests
import json

class FriendlyScore:

    CLIENT_ID         = settings.FRIENDLY_SCORE_CLIENT_ID
    CLIENT_SECRET     = settings.FRIENDLY_SCORE_CLIENT_SECRET
    BASE_URL          = 'https://friendlyscore.com/'
    REQUEST_TOKEN_URL = BASE_URL+'oauth/v2/token'

    def getToken(self):
        credentials = { 'client_id': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET, 'grant_type': 'client_credentials' }
        r = requests.post(self.REQUEST_TOKEN_URL, json=credentials)
        token = r.json()
        self.auth_headers = { 'Authorization': 'Bearer '+token['access_token'] }
        return r.status_code, token

    def url(self, endpoint):
        return self.BASE_URL+'api/v2/'+endpoint+'.json'

    def get(self, endpoint, params = {}):
        r = requests.get(self.url(endpoint), params=params, headers=self.auth_headers)
        return r.status_code, r.json()

    def put(self, endpoint, params = {}):
        r = requests.put(self.url(endpoint), json=params, headers=self.auth_headers)
        return r.status_code, r.json()

    def post(self, endpoint, params = {}):
        r = requests.post(self.url(endpoint), json=params, headers=self.auth_headers)
        return r.status_code, r.json()

    def getUsers(self, page=1, per_page=20):
        return self.get('users', { 'page': page, 'max_results': per_page })
