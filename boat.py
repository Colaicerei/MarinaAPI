from google.cloud import datastore
from flask import Blueprint, request, Response, make_response
from requests_oauthlib import OAuth2Session
import json
from google.oauth2 import id_token
from google.auth import crypt
from google.auth import jwt
from google.auth.transport import requests

client = datastore.Client()

bp = Blueprint('boat', __name__, url_prefix='/boats')

client_id = '775301840052-9oua4seeq9hs087cct454g703a6apgcg.apps.googleusercontent.com'
client_secret = 'P5Je6PeP3L9SWu2XVtDJLQXI'

def count(owner_id):
    query = client.query(kind='Boat')
    query.add_filter('owner', '=', owner_id)
    query.keys_only()
    results = query.fetch()
    count = 0
    for e in results:
        count += 1
    return count

# get all existing boats
def get_all_boats(request, owner_id):
    query = client.query(kind='Boat')
    query.add_filter('owner', '=', owner_id)
    q_limit = int(request.args.get('limit', '5'))
    q_offset = int(request.args.get('offset', '0'))
    g_iterator = query.fetch(limit=q_limit, offset=q_offset)
    pages = g_iterator.pages
    results = list(next(pages))
    if g_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None
    for e in results:
        e["id"] = str(e.key.id)
        e["self"] = request.base_url + '/' + str(e.key.id)
        if e['loads']:
            for l in e["loads"]:
                load_key = client.key("Load", int(l["id"]))
                load = client.get(key=load_key)
                if load is not None:
                    l["self"] = request.url_root + '/loads/' + str(load.id)
    output = {"boats": results, "count": count(owner_id)}
    if next_url:
        output["next"] = next_url
    return output

# create a new boat with name, type and length passed as parameters
def add_boat(request_content, user_id):
    if 'name' not in request_content or 'type' not in request_content or 'length' not in request_content:
        error_msg = {"Error": "The request object is missing at least one of the required attributes"}
        return (error_msg, 400)
    new_boat = datastore.Entity(key=client.key('Boat'))
    new_boat.update({
        'name': request_content['name'],
        'type': request_content['type'],
        'length': request_content['length'],
        'owner': user_id,
        'loads': []
    })
    client.put(new_boat)
    return new_boat

# get an existing boat with boat_id
def get_boat(boat_id, owner_id):
    boat_key = client.key('Boat', int(boat_id))
    boat = client.get(key=boat_key)
    if boat is None:
        error_message = {"Error": "No boat with this boat_id exists"}
        return (error_message, 404)
    else:
        if boat['owner'] != owner_id:
            error_msg = {"Error": "The boat is owned by someone else"}
            return (error_msg, 403)
        boat["id"] = boat_id
        boat["self"] = request.url_root + 'boats/' + str(boat.id)
        loads = boat["loads"]
        if loads:
            for l in loads:
                load_key = client.key("Load", int(l["id"]))
                load = client.get(key=load_key)
                if load is not None:
                    l["self"] = request.url_root + 'loads/' + str(load.id)
        return Response(json.dumps(boat), status=200, mimetype='application/json')

# delete boat and remove it from loads assigned to it
def delete_boat(boat_id, owner_id):
    boat_key = client.key('Boat', int(boat_id))
    result = client.get(key=boat_key)
    if result is None:
        error_message = {"Error": "No boat with this boat_id exists"}
        return (error_message, 404)
    else:
        if result['owner'] != owner_id:
            error_msg = {"Error": "The boat is owned by someone else and cannot be deleted"}
            return (error_msg, 403)
        for l in result['loads']:
            load_key = client.key('Load', int(l['id']))
            load = client.get(key=load_key)
            if load is not None:
                load.update({
                    "carrier": None
                })
                client.put(load)
        client.delete(boat_key)
        return ('', 204)

# modify an existing boat with name, type and length passed as parameters
def edit_boat(content, boat_id, owner_id):
    boat_key = client.key('Boat', int(boat_id))
    boat = client.get(key=boat_key)
    if result is None:
        error_message = {"Error": "No boat with this boat_id exists"}
        return (error_message, 404)
    else:
        if result['owner'] != owner_id:
            error_msg = {"Error": "The boat is owned by someone else and cannot be edited"}
            return (error_msg, 403)
        if 'name' in content:
            boat_name = content["name"]
        else:
            boat_name = boat["name"]
        if 'type' in content:
            boat_type = content["type"]
        else:
            boat_type = boat["type"]
        if 'length' in content:
            boat_length = int(content["length"])
        else:
            boat_length = boat["length"]
        boat.update({
            'name': boat_name,
            'type': boat_type,
            'length': boat_length
        })
        client.put(boat)
    return boat

# assign an existing load to an existing boat
def add_load_to_boat(load_id, boat_id):
    load_key = client.key('Load', int(load_id))
    boat_key = client.key('Boat', int(boat_id))
    load = client.get(key=load_key)
    boat = client.get(key=boat_key)
    # check if both load and boat exist and load is not occupied
    if load is None or boat is None:
        return 404
    # check if load has been assigned to another boat
    elif load['carrier'] is not None:
        return 403
    # update list of loads in boat
    load_brief = {'id':str(load.id)}
    boat['loads'].append(load_brief)
    client.put(boat)
    # update carrier information in load
    boat_brief = {'id': str(boat.id), 'name': boat['name']}
    load.update({
        "carrier": boat_brief
    })
    client.put(load)
    return 204

# remove an existing load from the boat it is assigned to one
def remove_load_from_boat(load_id, boat_id):
    load_key = client.key('Load', int(load_id))
    boat_key = client.key('Boat', int(boat_id))
    load = client.get(key=load_key)
    boat = client.get(key=boat_key)
    # check if both load and boat exist and load is assigned to the boat
    if load is None or boat is None or load["carrier"] is None or str(load["carrier"]["id"])!=boat_id:
        return 404
    load.update({
        "carrier": None
    })
    client.put(load)
    for load in boat['loads']:
        print(load["id"])
        if load["id"] == load_id:
            boat['loads'].remove(load)
    client.put(boat)
    return 204

def get_owner_id(request_headers):
    if 'Authorization' not in request_headers:
        error_msg = {"Error": "Missing JWT"}
        return (error_msg, 401)
    elif request_headers['Authorization'][:6] != 'Bearer':
        error_msg = {"Error": "Invalid JWT"}
        return (error_msg, 401)
    else:
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
    return id_info['sub']

# create a new boat via POST or view all boats via GET
@ bp.route('', methods=['POST', 'GET'])
def manage_boats():
    if 'application/json' not in request.accept_mimetypes:
        error_msg = {"Error": "Only JSON is supported as returned content type"}
        return (error_msg, 406)
    result = get_owner_id(request.headers)
    if isinstance(result, tuple):
        return result
    owner_id = result

    # create new boat
    if request.method == 'POST':
        request_content = json.loads(request.data) or {}
        new_boat = add_boat(request_content, owner_id)
        if isinstance(new_boat, tuple):
            return new_boat
        boat_id = str(new_boat.key.id)
        new_boat["id"] = boat_id
        new_boat["self"] = request.base_url + '/' + boat_id
        return Response(json.dumps(new_boat), status=201, mimetype='application/json')
    #view user's boats
    elif request.method == 'GET':
        boat_list = get_all_boats(request, owner_id)
        return Response(json.dumps(boat_list), status=200, mimetype='application/json')
    else:
        return 'Method not recogonized'


# view, or delete an existing boat, return 404 if boat not exists
@bp.route('/<boat_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def manage_boat(boat_id):
    # get boat with authorization
    result = get_owner_id(request.headers)
    if isinstance(result, tuple):
        return result
    user_id = result
    if request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            error_msg = {"Error": "Only JSON is supported as returned content type"}
            return (error_msg, 406)
        return get_boat(boat_id, user_id)
    elif request.method == 'DELETE':
        return delete_boat(boat_id, user_id)
    elif request.method == 'PUT' or request.method == 'PATCH':
        if 'application/json' not in request.accept_mimetypes:
            error_msg = {"Error": "Only JSON is supported as returned content type"}
            return (error_msg, 406)
        return edit_boat(request_content, boat_id, user_id)
    else:
        return 'Method not recogonized'


# assign or un-assign a load to boat
@bp.route('/<boat_id>/loads/<load_id>', methods=['PUT', 'DELETE'])
def manage_boat_load(load_id, boat_id):
    if request.method == 'PUT':
        status = add_load_to_boat(request.url_root, load_id, boat_id)
        if status == 403:
            error_message = {"Error": "The load has already been assigned to another boat"}
            return (error_message, 403)
        elif status == 404:
            error_message = {"Error":  "The specified boat and/or load don\u2019t exist"}
            return (error_message, 404)
        elif status == 204:
            return ('', 204)
    elif request.method == 'DELETE':
        status = remove_load_from_boat(load_id, boat_id)
        if status == 404:
            error_message = {"Error":  "No load with this load_id is at the boat with this boat_id"}
            return (error_message, 404)
        elif status == 204:
            return ('', 204)
    else:
        return 'Method not recogonized'






