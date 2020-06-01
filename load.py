from google.cloud import datastore
from flask import Blueprint, request, Response, make_response
import json

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

def count():
    query = client.query(kind='Load')
    query.keys_only()
    results = query.fetch()
    count = 0
    for e in results:
        count += 1
    return count

# get all existing loads
def get_all_loads(request):
    print(request.base_url)
    print(request.url_root)
    query = client.query(kind='Load')
    q_limit = int(request.args.get('limit', '5'))
    q_offset = int(request.args.get('offset', '0'))
    g_iterator = query.fetch(limit = q_limit, offset = q_offset)
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
        carrier = e["carrier"]
        if carrier is not None:
            boat_key = client.key("Boat", int(carrier["id"]))
            boat = client.get(key=boat_key)
            if boat is not None:
                e["carrier"]["self"] = request.url_root + 'boats/' + str(boat.id)
    output = {"loads": results, "total count": count()}
    if next_url:
        output["next"] = next_url
    return output

# create a new load with weight, content, and delivery date as parameters
def add_load(content):
    if 'weight' not in content or 'content' not in content or 'delivery_date' not in content:
        error_message = {"Error": "The request object is missing at least one of the required attributes"}
        return (error_message, 400)
    new_load = datastore.Entity(key=client.key('Load'))
    new_load.update({
        'weight': content['weight'],
        'carrier': None,
        'content': content['content'],
        'delivery_date': content['delivery_date']
    })
    client.put(new_load)
    return new_load

# get an existing load with given load id
def get_load(load_id, base_url):
    load_key = client.key('Load', int(load_id))
    result = client.get(key=load_key)
    if result is None:
        error_message = {"Error": "No load with this load_id exists"}
        return (error_message, 404)
    else:
        result["id"] = load_id
        result["self"] = base_url
        carrier = result["carrier"]
        if carrier is not None:
            boat_key = client.key("Boat", int(carrier["id"]))
            boat = client.get(key=boat_key)
            if boat is not None:
                result["carrier"]["self"] = request.url_root + '/boats/' + str(boat.id)
    return Response(json.dumps(result), status=200, mimetype='application/json')


# delete load and remove it's id from boat if it is assigned to one
def delete_load(load_id):
    load_key = client.key('Load', int(load_id))
    result = client.get(key=load_key)
    if result is None:
        error_message = {"Error": "No load with this load_id exists"}
        return (error_message, 404)
    else:
        client.delete(load_key)
        boat = result['carrier']
        if boat is not None:
            boat_key = client.key('Boat', int(boat["id"]))
            boat_get = client.get(key=boat_key)
            for load in boat_get['loads']:
                if load["id"] == load_id:
                    boat_get['loads'].remove(load)
            client.put(boat_get)
        return ('', 204)

# modify an existing load
def edit_load(content, load_id):
    load_key = client.key('Load', int(load_id))
    load = client.get(key=load_key)
    if load is None:
        error_message = {"Error": "No load with this load_id exists"}
        return (error_message, 404)
    else:
        if 'weight' in content:
            load_weight = content["weight"]
        else:
            load_weight = load["weight"]
        if 'content' in content:
            load_content = content["content"]
        else:
            load_content = load["content"]
        if 'delivery_date' in content:
            delivery_date = content["delivery_date"]
        else:
            delivery_date = load["delivery_date"]
        load.update({
            'weight': load_weight,
            'content': load_content,
            'delivery_date': delivery_date
        })
        client.put(load)
        load["id"] = load_id
        load["self"] = request.url_root + 'loads/' + str(load.id)
        return Response(json.dumps(load), status=200, mimetype='application/json')

# create a new load via POST or view all loads via GET
@ bp.route('', methods=['POST', 'GET', 'PUT', 'DELETE'])
def manage_loads():
    if 'application/json' not in request.accept_mimetypes:
        error_msg = {"Error": "Only JSON is supported as returned content type"}
        return (error_msg, 406)
    if request.method == 'POST':
        request_content = json.loads(request.data) or {}
        new_load = add_load(request_content)
        if isinstance(new_load, tuple):
            return new_load
        load_id = str(new_load.key.id)
        new_load["id"] = load_id
        new_load["self"] = request.base_url + '/' + load_id
        return Response(json.dumps(new_load), status=201, mimetype='application/json')
    elif request.method == 'GET':
        load_list = get_all_loads(request)
        return Response(json.dumps(load_list), status=200, mimetype='application/json')

    # invalid action - edit/delete all loads
    elif request.method == 'PUT' or request.method == 'DELETE':
        res = make_response('')
        res.headers.set('Allow', 'GET, PUT')
        res.status_code = 405
        return res
    else:
        return 'Method not recogonized'

# view, modify or delete an existing load, return 404 if load not exists
@bp.route('/<load_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def manage_load(load_id):
    if request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            error_msg = {"Error": "Only JSON is supported as returned content type"}
            return (error_msg, 406)
        return get_load(load_id, request.base_url)
    elif request.method == 'DELETE':
        return delete_load(load_id)
    elif request.method == 'PUT' or request.method == 'PATCH':
        if 'application/json' not in request.accept_mimetypes:
            error_msg = {"Error": "Only JSON is supported as returned content type"}
            return (error_msg, 406)
        request_content = json.loads(request.data) or {}
        return edit_load(request_content, load_id)
    else:
        return 'Method not recogonized'




