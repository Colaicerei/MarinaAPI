from google.cloud import datastore
from flask import Blueprint, request, Response, jsonify, abort
import json

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

# get all existing loads
def get_all_loads(request):
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
                e["carrier"]["self"] = request.url_root + '/boats/' + str(boat.id)
    output = {"loads": results}
    if next_url:
        output["next"] = next_url
    return output

# create a new load with weight, content, and delivery date as parameters
def add_load(load_weight, load_content, delivery_date):
    new_load = datastore.Entity(key=client.key('Load'))
    new_load.update({
        'weight': load_weight,
        'carrier': None,
        'content': load_content,
        'delivery_date': delivery_date
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
    if result is None:
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
    return load

# create a new load via POST or view all loads via GET
@ bp.route('', methods=['POST', 'GET'])
def manage_loads():
    if request.method == 'POST':
        content = json.loads(request.data) or {}
        if 'weight' not in content or 'content' not in content or 'delivery_date' not in content:
            error_message = {"Error": "The request object is missing at least one of the required attributes"}
            return (error_message, 400)
        new_load = add_load(content["weight"], content["content"], content["delivery_date"])
        load_id = str(new_load.key.id)
        new_load["id"] = load_id
        new_load["self"] = request.base_url + '/' + load_id
        return Response(json.dumps(new_load), status=201, mimetype='application/json')
    elif request.method == 'GET':
        load_list = get_all_loads(request)
        return Response(json.dumps(load_list), status=200, mimetype='application/json')
    else:
        return 'Method not recogonized'

# view, modify or delete an existing load, return 404 if load not exists
@bp.route('/<load_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def manage_load(load_id):
    if request.method == 'GET':
        return get_load(load_id, request.base_url)
    elif request.method == 'DELETE':
        return delete_load(load_id)
    elif request.method == 'PUT' or request.method == 'PATCH':
        return edit_boat(request_content, load_id)
    else:
        return 'Method not recogonized'

# main function
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)



