import traceback
import boto3
import botocore
import uuid
import requests
import copy
import base64

from lib.Common import Utils as Utils
from lib.Common.Exploration.Environment.State import State
from lib.Common.Utils import Log as Log, Constants as Constants
from lib.Presentation.Web.NmapParser import NmapParser

FAKE_TARGET     = "10.10.10.3"
MISSING_KEY     = "empty"

def set_new_session(session):
    new_uuid = uuid.uuid4()
    Log.logger.debug(f"Session id not set, will set it to {new_uuid}")
    session['session_id'] = str(new_uuid)

    return session

def create_lex_client():
    return boto3.client('lex-runtime',
        aws_access_key_id    = Constants.LEX_AWS_ACCESS_KEY,
        aws_secret_access_key= Constants.LEX_AWS_SECRET_KEY,
        region_name          = Constants.WEB_AWS_REGION,
    )

def create_ses_client():
    return boto3.client('ses',
        aws_access_key_id    = Constants.LEX_AWS_ACCESS_KEY,
        aws_secret_access_key= Constants.LEX_AWS_SECRET_KEY,
        region_name          = Constants.WEB_AWS_REGION,
    )

def get_annotation(connection, space, action_name):
    results = connection.query("SELECT description, link FROM annotations WHERE space=%s AND name=%s", (space, action_name))

    if len(results) > 0:
        annotation = {
            "description": results[0]['description'],
            "link":        results[0]['link']
        }
        return annotation
    else:
        return None

def get_action_annotation(connection, action_name):
    return get_annotation(connection, "ACTION", action_name)

def get_port_annotation(connection, port_number):
    return get_annotation(connection, "PORT", port_number)

def get_application_annotation(connection, port_number):
    return get_annotation(connection, "APPLICATION", port_number)

def get_history(session, connection):
    history = []
    results = connection.query(
        "SELECT message, response_message FROM conversations WHERE session_id=%s ORDER BY id ASC",
        (session['session_id'],))

    for result in results:
        history.append(f"user:{result['message']}")
        history.append(f"drako:{result['response_message']}")

    return history

def send_email(ses_client, email, test=False):
    SENDER    = "info@drako.ai"
    RECIPIENT = "juan@berner.fyi"

    if test:
        SUBJECT = "Test from contact message in drako.ai"
    else:
        SUBJECT   = "New contact message to drako.ai"


    BODY_TEXT = f"New subscriber: {email}"
    BODY_HTML = BODY_TEXT
    CHARSET   = "UTF-8"

    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = ses_client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.
    except botocore.exceptions.ClientError as e:
        Log.logger.error(e.response['Error']['Message'])
        return False
    else:
        Log.logger.debug("Email sent! Message ID:"),
        Log.logger.debug(response['MessageId'])
        return True


def get_user_action_history(session, connection, prev_state):
    prev_state_hash = prev_state.get_state_hash(prev_state.deduce_game_type())

    query_stmt = "SELECT recommended_action_entry FROM conversations WHERE session_id=%s AND prev_state_hash=%s AND recommended_action_entry IS NOT NULL"
    results = connection.query(query_stmt, (session['session_id'], prev_state_hash))

    action_history = []
    for res in results:
        # Log.logger.debug(res['recommended_action_entry'])
        action_history.append(Utils.json_loads(res['recommended_action_entry']))

    # Log.logger.debug(action_history)
    return action_history


def recommend_action(session, connection, game_type, prev_state, response):
    if len(prev_state.get_sessions()) > 0:
        session_object = prev_state.get_newest_session()
        if session_object.is_super_user_session():
            return None, "You already have a session with a super user account, the rest is up to you!"

    action_history = get_user_action_history(session, connection, prev_state)

    environment_options = {
        "target": FAKE_TARGET,
    }

    data_to_send = {
        'state':               prev_state.get_json(),
        'game_type':           game_type,
        'action_history':      Utils.dump_json(action_history),
        'skip_payload':        1,
        'environment_options': Utils.dump_json(environment_options),
    }
    Log.logger.debug(data_to_send)

    req_response = requests.post(f"http://{Constants.WEB_PREDICTION_API}:{Constants.PREDICTION_WEB_API_PORT}/predict_web", data=data_to_send)
    if req_response.status_code != 200:
        Log.logger.error("Error requesting prediction => %s" % req_response.text)
        return None, "Ups, something went wrong, please try later!"
    else:
        Log.logger.debug("API RESPONSE => %s" % req_response.text[:500])
        response_data = Utils.json_loads(req_response.text)
        action_name   = response_data['action_name']
        # Log.logger.debug(utils.dump_json(response_data))

        action_history_entry = {
            "action_source":      response_data['action_source'],
            "action_name_picked": response_data['action_name'],
            "action_options":     {},
            "top_20_q_vals":      response_data['action_extra']['top_20_q_vals'],
        }

        # Look for action information to add to the response.
        action_annotation = get_action_annotation(connection, action_name)
        if action_annotation is not None:
            if len(action_annotation['description']) > 0:
                response = response.replace("#ACTION_NAME#", action_annotation['description'])
            if len(action_annotation['link']) > 0:
                response += f"<br>You can read more about it <b><a target=\"_blank\" href=\"{action_annotation['link']}\">here</a></b>."
        else:
            if "auxiliary/" in action_name or "exploit/" in action_name:
                response = response.replace("action #ACTION_NAME#", "metasploit's action #ACTION_NAME#")

        # Now in case we did not replace it before
        response = response.replace("#ACTION_NAME#", action_name)

        return action_history_entry, response

def check_if_collection_nmap_slot(session, connection):
    query_stmt = "SELECT message_intention, fulfilled FROM conversations WHERE session_id=%s ORDER BY id DESC LIMIT 1"
    res = connection.query(query_stmt, (session['session_id'],))
    print(res)
    if len(res) > 0:
        res = res[0]
        if res['message_intention'] == 'UploadNmap' and res['fulfilled'] == 0:
            return True
    return False

def create_target_teaching_cards():
    return [{
        "buttons": [
            {
                "text": "I know the OS",
                "value": "I would like to tell you what the operating system for my target is"
            },
            {
                "text": "I know a port",
                "value": "I would like to tell you about an open port on the target"
            },
            {
                "text": "I got a shell!",
                "value": "I would like to tell you about a shell I have in the target"
            },
            {
                "text": "I want to upload an nmap scan",
                "value": "I would like to upload an nmap scan"
            },
            {
                "text": "Ok Im ready",
                "value": "Ok Im ready"
            }
        ],
        "title": "Recommended responses"
    }]

def create_initial_cards():
    return [{
        "buttons": [
            {
                "text": "Guide me!",
                "value": "I would like to know what I should do next"
            },
            {
                "text": "About my target",
                "value": "I want to tell you more about my target"
            },
            {
                "text": "What do you know?",
                "value": "I would like to understand what you know about my target"
            },
            {
                "text": "How does this work?",
                "value": "How does this work"
            }
        ],
        "title": "Recommended responses"
    }]


def get_lex_response(session, connection, lex_client, received_message):
    collecting_nmap_slot = check_if_collection_nmap_slot(session, connection)
    if len(received_message) > 1024:
        raise ValueError("A message cannot be longer than 1024")
    # else:
    #     Log.logger.debug("Message length is %d" % len(received_message))

    if collecting_nmap_slot:
        received_message = "XXXXXXX" #FORCING THIS SO NMAP SLOT IS FULLFILLED

    # Do a normal lex request
    lex_response = lex_client.post_text(
        botName   = 'PentesterBot',
        botAlias  = 'drako',
        userId    = session['session_id'],
        inputText = received_message[:1024]
    )
    Log.logger.debug(Utils.dump_json(lex_response))

    # WHEN PROCESSING NMAP WE NEED TO REPLACE THE RESPONSE FROM LEX SINCE THE SIZE MIGHT BE LARGER THAN 1k
    # WE STILL DO A CALL TO CLEAN THE CONTEXT
    if collecting_nmap_slot:
        Log.logger.debug("We are processing an nmap slot!")
        lex_response = {
            "intentName": "UploadNmap",
            "nluIntentConfidence": {"score": 1.0},
            "slots": {
                "nmap_scan": received_message
            },
            "message": "Thanks, I just processed the scan and added it to my knowledge base",
            "responseCard": {
                "genericAttachments": create_target_teaching_cards(),
            },
            "dialogState": "Fulfilled",
        }

    return lex_response


def get_intention_from_message(session, connection, lex_client, received_message):
    # First we will check if there is a similar message that we can reuse to avoid calling Lex
    Log.logger.debug('Will request intention for message: "%s" and user_id:%s' % (received_message, session['session_id']))

    lex_response = get_lex_response(session, connection, lex_client, received_message)

    # IF WE GOT AN INTENTION
    if 'intentName' in lex_response:
        intention_data = {
            "intention":        lex_response["intentName"],
            "slots":            lex_response["slots"],
        }

        message = ""
        if 'message' in lex_response:
            message = lex_response["message"]
        intention_data["response_message"] = message
        
        if 'confidence' in lex_response:
            intention_data['confidence'] = lex_response['nluIntentConfidence']['score']
        else:
            intention_data['confidence'] = -1

        if 'responseCard' in lex_response:
            intention_data["cards"] = lex_response['responseCard']['genericAttachments']
        else:
            intention_data["cards"] = {}

        intention_data['dialog_state'] = lex_response['dialogState']

        if 'slotToElicit' in lex_response:
            intention_data['slot_to_elicit'] = lex_response['slotToElicit']
        else:
            intention_data['slot_to_elicit'] = None

        # Log.logger.debug(utils.dump_json(intention_data))

        return intention_data, lex_response
    else:
        return None, lex_response


def get_latest_session_state_dict(session, connection):
    query_stmt = "SELECT next_state FROM conversations WHERE session_id=%s ORDER by id DESC LIMIT 1"
    res = connection.query(query_stmt, (session['session_id'],))

    if len(res) > 0:
        return res[0]['next_state']
    else:
        return '{}'


def store_conversation(session, connection, received_message, intention_data, response, prev_game_type, previous_state_dict, prev_state_hash, next_game_type, next_state_dict, next_state_hash, lex_response, recommended_action_entry):
    if intention_data['dialog_state'] == 'Fulfilled':
        fulfilled = True
    else:
        fulfilled = False

    if recommended_action_entry is not None:
        recommended_action_entry_json = Utils.dump_json(recommended_action_entry)
    else:
        recommended_action_entry_json = None

    insert_stmt = "INSERT INTO conversations(session_id, message, message_intention, message_slots, message_slot_requested, message_confidence, response_message, response_cards, prev_game_type, prev_state, prev_state_hash, next_game_type, next_state, next_state_hash, fulfilled, lex_response, recommended_action_entry) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    data = (
        session['session_id'], received_message,
        intention_data['intention'], Utils.dump_json(intention_data['slots']), intention_data['slot_to_elicit'], intention_data['confidence'], response, Utils.dump_json(intention_data["cards"]),
        prev_game_type, Utils.dump_json(previous_state_dict), prev_state_hash, next_game_type, Utils.dump_json(next_state_dict), next_state_hash, fulfilled, Utils.dump_json(lex_response), recommended_action_entry_json
    )

    # print(data)
    connection.execute(insert_stmt, data)

def store_error(session, connection, received_message, lex_response, intention_data, error_message):
    # TODO: Add test for this
    insert_stmt = "INSERT INTO errors(session_id, utterance, lex_response, intention_data, error_message) VALUES(%s,%s,%s,%s,%s)"
    data        = (session['session_id'], received_message, Utils.dump_json(lex_response), Utils.dump_json(intention_data), error_message)
    connection.execute(insert_stmt, data)

def store_missed_utterance(session, connection, received_message, lex_response):
    # TODO: Add test for this
    insert_stmt = "INSERT INTO missed_utterances(session_id, utterance, lex_response, response) VALUES(%s,%s,%s,%s)"
    data        = (session['session_id'], received_message, Utils.dump_json(lex_response), lex_response['message'])
    connection.execute(insert_stmt, data)

def process_nmap_scan(next_state, nmap_scan):
    parser = NmapParser(nmap_scan)

    ports = parser.get_open_ports()
    for port in ports:
        Log.logger.debug(port)
        if port['state'] == 'open':
            next_state.add_service(next_state.get_target_address(), port=port['port'], protocol=port['protocol'], state=port['state'], name=port['name'], application=port['application'])

    os_info = parser.get_os_info()
    if 'os_name' in os_info:
        next_state.add_host(next_state.get_target_address(), os_name=os_info['os_name'])
    if 'os_flavor' in os_info:
        next_state.add_host(next_state.get_target_address(), os_flavor=os_info['os_flavor'])

    return next_state

def create_response_card(buttons):
    return [{
        "buttons": buttons,
        "title": "Recommended responses"
    }]

def process_unfullfilled_state(response, intention_data, response_dict):
    intention_name = intention_data['intention']

    if intention_name == "UploadNmap":
        response_dict['action_required'] = "file_upload"        
    elif intention_name == "AddPort":
        if response.startswith("Please provide the protocol"):
            buttons_data = [
                {"text": "tcp", "value": "tcp"},
                {"text": "udp", "value": "udp"},
            ]
            response_dict["cards"] = create_response_card(buttons_data)
        elif response.startswith("Please provide the application name"):
            buttons_data = [{"text": "I don't know", "value": MISSING_KEY}]
            response_dict["cards"] = create_response_card(buttons_data)
        elif response.startswith("Please provide the port name"):
            buttons_data = [{"text": "I don't know", "value": MISSING_KEY}]
            response_dict["cards"] = create_response_card(buttons_data)

    return response_dict

def create_status_string(received_message, response, previous_state):
    if received_message == "debug status":
        return previous_state.get_json()

    added_data = False
    os_name = previous_state.get_os_name()
    if os_name is not None:
        response += f"</br></br>The operating system for the target is {os_name}"
        added_data = True

    ports_available = previous_state.get_open_ports_map()
    all_ports       = previous_state.get_open_ports()

    if len(all_ports) > 0:
        added_data = True
        response += "</br>"
        for protocol in ports_available:
            if len(ports_available[protocol]) > 0:
                response += f"</br>The target has these {protocol} ports open:</br>"
                for port in ports_available[protocol]:
                    if 'name' in ports_available[protocol][port]['information']:
                        name = f"({ports_available[protocol][port]['information']['name']})"
                    else:
                        name = ""

                    if 'application' in ports_available[protocol][port]['information']:
                        application = f"running {ports_available[protocol][port]['information']['application']}"
                    else:
                        application = ""

                    response += f"{port}{name} {application}</br>"

    game_type = previous_state.deduce_game_type()
    if game_type == "PRIVESC":
        if not added_data: #Extra line break for clarity
            response += "</br>"
        session_information = previous_state.get_newest_session_information()
        response += f"</br>You have a session opened on the target for user {session_information['username']}"
        added_data = True

    if not added_data:
        response = "I don't know anything about your target yet!"

    return response

def get_dialog_state_fulfillment(response, lex_response, intention_data):
    if intention_data['dialog_state'] == 'Fulfilled' or intention_data['dialog_state'] == 'ReadyForFulfillment':
        return response, True

    Log.logger.debug(intention_data)
    if lex_response['dialogState'] == "Failed":
        if intention_data['intention'] == "AddPort":
            slots = intention_data['slots']
            Log.logger.debug(slots)
            if slots['port_name'] is None:
                slots['port_name'] = MISSING_KEY
            if slots['port_name'] is None:
                slots['application'] = MISSING_KEY

            Log.logger.debug(slots)

            new_response = "Thanks! Now I know that your target has that port open!"
            intention_data['cards'] = create_target_teaching_cards()

            return new_response, True

    return response, False

def get_previous_state(session, connection):
    previous_state_json = get_latest_session_state_dict(session, connection)

    previous_state = None
    if previous_state_json == '{}':
        Log.logger.debug("We don't have a previous state, will create an empty one")
        previous_state      = State()
        # fake a target
        previous_state.set_target(FAKE_TARGET)
        previous_state.set_target_ip(FAKE_TARGET)
        previous_state_dict = previous_state.get_state_dict()
    else:
        Log.logger.debug("We found state %s, will use it" % previous_state_json)
        previous_state_dict = Utils.json_loads(previous_state_json)
        previous_state      = State(previous_state_dict)

    # Lets deduce the game type from the state itself
    prev_game_type  = previous_state.deduce_game_type()
    prev_state_hash = previous_state.get_state_hash(prev_game_type)

    # We default to having the same as the next state
    next_state      = State(copy.deepcopy(previous_state_dict))
    Log.logger.debug(previous_state_dict)

    return previous_state, prev_game_type, prev_state_hash, next_state

def process_intention_and_slots(session, connection, received_message, intention_data, lex_response, file_received):
    previous_state, prev_game_type, prev_state_hash, next_state = get_previous_state(session, connection)

    if received_message == "hi error!":
        raise ValueError("Error triggered!")

    # We default to the response returned by LEX
    response  = intention_data['response_message']

    # DIAlOG STATE HACK
    response, is_dialog_state_fulfilled = get_dialog_state_fulfillment(response, lex_response, intention_data)
    response_dict = {"cards": intention_data['cards']}

    recommended_action_entry = None
    flag_for_new_session     = False
    if is_dialog_state_fulfilled:
        intention = intention_data['intention']
        slots     = intention_data['slots']

        # Log.logger.debug(Utils.dump_json(intention_data))
        # Log.logger.debug(slots)
        # Log.logger.debug(next_state.get_json())
        if intention == "AddOS":
            next_state.add_host(next_state.get_target_address(), os_name=slots['operating_system'], os_flavor=slots['operating_system'])

            response = f'I added the operating system {slots["operating_system"]}'
            response_dict['cards'] = create_target_teaching_cards()
        elif intention == "Teach":
            response = "What do you want to tell me?"
            response_dict['cards'] = create_target_teaching_cards()
        elif intention == "Ready":
            response = "Sure, let me know if you need anything else!"
            response_dict['cards'] = create_initial_cards()
        elif intention == "Help":
            response = "Hi! I'm Drako and I can help you exploiting a target machine.<br/>You can ask me what you should do or provide me information that will help me give you better advise, good luck!"
            response_dict['cards'] = create_initial_cards()
        elif intention == "AddPort":
            # PROCESS SLOTS
            protocol    = slots['protocol'].lower()
            port_number = slots["port_number"]

            response = f'I added the {protocol} opened port {port_number}'

            port_name   = slots['port_name']
            if port_name == "unknown" or port_name == MISSING_KEY: # This is a smart reply for i don't know
                port_name = None
            else:
                response += f'({port_name})'

            application = slots['application']
            if application == "unknown" or application == MISSING_KEY: # This is a smart reply for i don't know
                application = None
            else:
                response += f' for the application {application}'

            next_state.add_service(next_state.get_target_address(), port=slots['port_number'], name=port_name, application=application, protocol=protocol, state="open")

            response_dict['cards'] = create_target_teaching_cards()
        elif intention == 'ShellInfo':
            username = slots['user']
            session_data = {
                "user":     username,
                "username": username
            }
            next_state.add_session("1", session_data)

            response = f'I added an open session for user {username}'
            response_dict['cards'] = create_target_teaching_cards()
        elif intention == 'UploadNmap':
            if file_received is None:
                response = "Sure! You can always send it later."
            else:
                Log.logger.debug(f"Now we need to process the nmap scan (first 100 characters): {file_received[:100]}")
                # Log.logger.debug(file_received)
                try:
                    # Log.logger.debug(file_received)
                    base64_scan = file_received.split("data:text/xml;base64,")[1]
                    # Log.logger.debug(base64_scan)
                    nmap_scan_str = base64.b64decode(base64_scan).decode('utf-8').strip()
                    # Log.logger.debug(nmap_scan_str)
                    next_state = process_nmap_scan(next_state, nmap_scan_str)
                    response = "Thanks. We just ingested your nmap scan. You can ask me what I know to see what I learned!"
                except:
                    Log.logger.error("Error parsing nmap => %s" % traceback.format_exc())
                    response = "Ups, I was unable to understand the nmap file format. Please provide it in xml output (-oX)"

            response_dict['cards'] = create_initial_cards()
        elif intention == 'Status':
            response = "This is what I know so far:"
            response = create_status_string(received_message, response, previous_state)
            # response = "%s\n%s" % (response, previous_state.get_json())
            response_dict['cards'] = create_initial_cards()
        elif intention == 'StartOver':
            flag_for_new_session = True
            response = "Beep Boop! I just rebooted my system. Let me know what you want to do."
            response_dict['cards'] = create_initial_cards()
        elif intention == 'NextAction':
            response = "You should try to use action #ACTION_NAME#, tell me if you get a shell or more information"
            recommended_action_entry, response = recommend_action(session, connection, prev_game_type, previous_state, response)
            response_dict['cards'] = create_initial_cards()
    else:
        response_dict = process_unfullfilled_state(response, intention_data, response_dict)

    Log.logger.debug(next_state.get_json())
    Log.logger.debug(intention_data['slots'])

    next_state_dict = next_state.get_state_dict()
    next_game_type  = next_state.deduce_game_type()
    next_state_hash = next_state.get_state_hash(next_game_type)

    store_conversation(session, connection, received_message, intention_data, response, prev_game_type, previous_state.get_state_dict(), prev_state_hash, next_game_type, next_state_dict, next_state_hash, lex_response, recommended_action_entry)

    response_dict["message"] = response

    return response_dict, flag_for_new_session
