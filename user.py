from google.cloud import datastore
from flask import Blueprint, request, Response, jsonify, session, render_template, redirect, url_for
from requests_oauthlib import OAuth2Session
import json
from google.oauth2 import id_token
from google.auth import crypt
from google.auth import jwt
from google.auth.transport import requests
import datetime

# This disables the requirement to use HTTPS so that you can test locally.
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
#os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

client = datastore.Client()
bp = Blueprint('user', __name__, url_prefix='/users')

# These should be copied from an OAuth2 Credential section at
# https://console.cloud.google.com/apis/credentials
client_id = '775301840052-9oua4seeq9hs087cct454g703a6apgcg.apps.googleusercontent.com'
client_secret = 'P5Je6PeP3L9SWu2XVtDJLQXI'
redirect_uri = 'http://localhost:8080/users/oauth'
#redirect_uri = 'https://fp-zouch000.appspot.com/user/oauth'
scope = 'openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email'
oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)

# check if user exists
def find_user(sub):
    query = client.query(kind='User')
    results = list(query.fetch())
    for e in results:
        if e['user_id'] == str(sub):
            return e
    return None

# add user to datastore
def create_user(id_info):
    user_query = find_user(id_info['sub'])
    if user_query is None:
        new_user = datastore.Entity(key=client.key('User'))
        new_user.update({
            'user_id': id_info['sub'],
            'email': id_info['email'],
            'last_login': datetime.datetime.now()
        })
        client.put(new_user)
        return new_user
    else:
        user_query.update({
            'last_login': datetime.datetime.now()
        })
        client.put(user_query)
        return user_query

# get all user from datastore
def get_users(base_url):
    query = client.query(kind='User')
    results = list(query.fetch())
    for e in results:
        e['id'] = e.key.id
        e['self'] = base_url + '/' + str(e.key.id),
        e['last_login'] = str(e['last_login'])
    return results

# This link will redirect users to begin the OAuth flow with Google
@bp.route('/login')
def user():
    if 'email' in session:
        return render_template('welcome.html', name=session['email'])
    return render_template('welcome.html', message=request.args.get('message', ''))

# Redirect user to google authentication to obtain JWT and user info
@bp.route('/oauth')
def oauthroute():
    if 'code' not in request.args:
        authorization_url, state = oauth.authorization_url(
            'https://accounts.google.com/o/oauth2/auth',
            # access_type and prompt are Google specific extra parameters.
            access_type="offline", prompt="select_account")
        return redirect(authorization_url)
    else:
        token = oauth.fetch_token(
            'https://accounts.google.com/o/oauth2/token',
            authorization_response=request.url,
            client_secret=client_secret)

        if token['expires_in'] <= 0:
            return redirect(url_for('user.user', message='Error: Token expired, please try again'))
        jwt = token['id_token']

        req = requests.Request()
        try:
            id_info = id_token.verify_oauth2_token(jwt, req, client_id)
        except ValueError:
            error = "Error: invalid JWT"
            return redirect(url_for('user.user', message=error))
        if id_info['iss'] != 'accounts.google.com':
            raise ValueError('Wrong issuer.')
        else:
            new_user = create_user(id_info)
        return render_template('user_info.html',jwt = jwt, user = new_user)

@bp.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('user.user',message='You are logged out'))

# create a new boat via POST or view all boats via GET
@ bp.route('', methods=['GET'])
def view_users():
    if request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            error_msg = {"Error": "Only JSON is supported as returned content type"}
            return (error_msg, 406)
        user_list = get_users(request.base_url)
        return Response(json.dumps(user_list), status=200, mimetype='application/json')
    else:
        return 'Method not recogonized'

@bp.route('/verify-jwt')
def verify():
    req = requests.Request()

    id_info = id_token.verify_oauth2_token(
    request.args['jwt'], req, client_id)

    return repr(id_info) + "<br><br> the user is: " + id_info['email']