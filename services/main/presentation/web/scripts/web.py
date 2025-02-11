import time
import traceback
import os

from datetime import timedelta

from flask import Flask, request, session, send_from_directory, send_file
from flask_cors import CORS

from lib.Common.Utils.Db import Db

import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log as Log

from lib.Presentation.Web import get_latest_session_state_dict, create_ses_client, get_history, set_new_session, create_lex_client, send_email, get_intention_from_message, store_missed_utterance, store_error, process_intention_and_slots

lex_client = create_lex_client()
ses_client = create_ses_client()

Log.initialize_log("2")
Log.add_info_large_ascii("WEB")

app = Flask(__name__)
app.config['SECRET_KEY']                 = 'ASadsomdodomsomsadodaomsdms'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_COOKIE_SAMESITE']    = 'None'
app.config['SESSION_COOKIE_SECURE']      = True
app.config['SESSION_COOKIE_HTTPONLY']    = True

CORS(app, supports_credentials=True)

connection = Db(db_name=Constants.ASSISTANT_DB_NAME, db_password=Constants.ASSISTANT_DB_PWD, db_host=Constants.ASSISTANT_DB_DNS)

@app.before_request
def make_session_permanent():
    session.permanent = True
    if request.endpoint != 'root':
        if 'session_id' not in session:
            set_new_session(session)
        else:
            Log.logger.debug("Session id is set to %s" % session['session_id'])
            pass 

@app.route("/")
def root():
    # return "<h1 style='color:blue'>Hello There!</h1>"
    return send_file("/app/resources/Robogard-final/index.html")

@app.route('/<path:path>')
def send_report(path):
    return send_from_directory('/app/resources/Robogard-final', path)

@app.route("/api/history", methods = ['GET'])
def history():
    history = get_history(session, connection)

    return {"history": history}

@app.route("/api/contact", methods = ['POST'])
def contact():
    data    = request.form
    # name    = data['name']
    email   = data['email']
    # message = data['message']

    # send email
    send_email(ses_client, email)
    time.sleep(1)  # to avoid ddos attacks harming me economically

    Log.logger.info("Email sent!")

    return {}

@app.route("/api/send_message", methods = ['POST'])
def send_message():
    data = request.form

    received_message = ""
    if 'message' in data:
        received_message = data['message'] # avoid messages longer than 100k

    file_received = None
    if 'file' in data:
        file_received = data['file']

    if len(received_message) > 100000:
        return {"message": "I cannot understand messages longer than 100000 characters!"}
    elif received_message == "/state":
        previous_state_json = get_latest_session_state_dict(session, connection)
        return {"message": previous_state_json.replace("\n", "<br/>")}
    elif len(received_message) > 0 or file_received is not None:
        intention_data, lex_response = get_intention_from_message(session, connection, lex_client, received_message)
        time.sleep(0.1)  # to avoid ddos attacks harming me economically

        if intention_data is not None:
            # Lets check if we need another slot
            try:
                response, flag_for_new_session = process_intention_and_slots(session, connection, received_message, intention_data, lex_response, file_received)
            except:
                error_message = traceback.format_exc()
                store_error(session, connection, received_message, lex_response, intention_data, error_message)
                Log.logger.error(error_message)
                return {"message": "There was an error! Sorry for that."}

            if flag_for_new_session:
                set_new_session(session)

            Log.logger.debug("Returning => %s" % response)

            return response
            # else:
            #     return {"message": intention_data['response_message']}
        else: # There was no intention found, lets return the error message directly
            store_missed_utterance(session, connection, received_message, lex_response)
            return {"message": lex_response['message']}
    else:
        return {"message": "You have to send a message of at least 1 character!"}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)
