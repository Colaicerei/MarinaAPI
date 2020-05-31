from google.cloud import datastore
from flask import Flask, request, Response, jsonify, session, render_template, redirect, url_for
import boat
import user
import load

app = Flask(__name__)
app.register_blueprint(boat.bp)
app.register_blueprint(user.bp)
app.register_blueprint(load.bp)
client = datastore.Client()
app.secret_key = 'super secret 8888'

# This link will redirect users to begin the OAuth flow with Google
@app.route('/')
def root():
    return render_template('welcome.html')
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)



