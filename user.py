from google.cloud import datastore
from flask import Blueprint, request, Response, jsonify, session, render_template, redirect, url_for
from requests_oauthlib import OAuth2Session
import json
from google.oauth2 import id_token
from google.auth import crypt
from google.auth import jwt
from google.auth.transport import requests
import secrets

# This disables the requirement to use HTTPS so that you can test locally.
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
#os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

client = datastore.Client()
bp = Blueprint('user', __name__, url_prefix='/user')

# These should be copied from an OAuth2 Credential section at
# https://console.cloud.google.com/apis/credentials
client_id = '775301840052-9oua4seeq9hs087cct454g703a6apgcg.apps.googleusercontent.com'
client_secret = 'P5Je6PeP3L9SWu2XVtDJLQXI'
redirect_uri = 'http://localhost:8080/user/oauth'
#redirect_uri = 'https://fp-zouch000.appspot.com/user/oauth'
scope = 'openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email'
oauth = OAuth2Session(client_id, redirect_uri=redirect_uri,
                          scope=scope)
# get all existing boats
def get_owner_boats(owner):
    query = client.query(kind='Boat')
    query.add_filter('owner', '=', owner)
    #query.order = ['-']
    results = list(query.fetch())
    for e in results:
        e["id"] = str(e.key.id)
    return results

# check if user is new
def user_is_new(sub):
    query = client.query(kind='Boat')
    results = list(query.fetch())
    for e in results:
        if e['user_id'] == sub:
            return False
    return True

# add user to datastore
def create_user(id_info):
    if user_is_new(id_info['sub']):
        new_user = datastore.Entity(key=client.key('User'))
        new_user.update({
            'user_id': id_info['sub'],
            'email': id_info['email']
        })
        client.put(new_user)
        return new_user

# get all user from datastore
def get_users(base_url):
    query = client.query(kind='User')
    results = list(query.fetch())
    for e in results:
        e['id'] = e.key.id
        e['self'] = base_url + '/' + str(e.key.id)
    return results

# This link will redirect users to begin the OAuth flow with Google
@bp.route('')
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
            return redirect(url_for('user', message='Error: Token expired, please try again'))
        jwt = token['id_token']

        req = requests.Request()
        try:
            id_info = id_token.verify_oauth2_token(jwt, req, client_id)
        except ValueError:
            error = "Error: invalid JWT"
            return redirect(url_for('user', message=error))
        if id_info['iss'] != 'accounts.google.com':
            raise ValueError('Wrong issuer.')
        else:
            user = create_user(id_info)
        return render_template('user_info.html',jwt = jwt, user = user)

@bp.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('user',message='You are logged out'))

# view all boats for given owner
@bp.route('/users/<user_id>/boats', methods=['GET'])
def get_boats_by_owner(user_id):
    # delete the boat
    if request.method == 'GET':
        if 'Authorization' not in request.headers:
            error_msg = {"Error": "Missing JWT"}
            return (error_msg, 401)
        jwt = request.headers['Authorization'][7:]
        req = requests.Request()
        try:
            id_info = id_token.verify_oauth2_token(
                jwt, req, client_id)
        except ValueError:
            error_msg = {"Error": "Invalid JWT"}
            return (error_msg, 401)
        if id_info['iss'] != 'accounts.google.com':
            raise ValueError('Wrong issuer.')
        owner = id_info['sub']
        if owner != user_id:
            error_msg = {"Error": "JWT doesn't match the owner_id specified in the URL"}
            return (error_msg, 401)
        boats = get_owner_boats(owner)
        return Response(json.dumps(boats), status=200, mimetype='application/json')
    else:
        return 'Method not recogonized'

@bp.route('/verify-jwt')
def verify():
    req = requests.Request()

    id_info = id_token.verify_oauth2_token(
    request.args['jwt'], req, client_id)

    return repr(id_info) + "<br><br> the user is: " + id_info['email']


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)



