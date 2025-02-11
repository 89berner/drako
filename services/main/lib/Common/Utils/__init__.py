from datetime import datetime
import json
import argparse
import hashlib
from lib.Common.Exploration.Environment.Session import Session

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Session):
            return o.get_dict()
        elif isinstance(o, datetime):
            return str(o)
        else:
            return super().default(o)

def str2bool(v):
    if isinstance(v, bool):
       return v
    elif v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0', 'none'):
        return False
    elif v is None:
        return False
    else:
        raise argparse.ArgumentTypeError(f'Boolean value expected, got {v}.')

def get_hash_of_dumped_json(json_obj):
    dumped_json = dump_json(json_obj)

    json_hash = hashlib.md5(dumped_json.encode("utf-8")).hexdigest()

    return json_hash

def get_hash_of_dumped_json_session(session_dict):
    # We remove the session id to avoid having different hashes
    if "session_id" in session_dict:
        del session_dict["session_id"]
    if "SESSION" in session_dict:
        del session_dict["SESSION"]
    dumped_json = dump_json(session_dict)

    json_hash = hashlib.md5(dumped_json.encode("utf-8")).hexdigest()

    return json_hash

def get_hash_of_dumped_json_options(options_dict):
    # We remove the session id to avoid having different hashes
    if "session_id" in options_dict:
        del options_dict["session_id"]
    if "SESSION" in options_dict:
        del options_dict["SESSION"]
    dumped_json = dump_json(options_dict)

    json_hash = hashlib.md5(dumped_json.encode("utf-8")).hexdigest()

    return json_hash

def get_hash_of_dict(dictionary):
    # We remove the session id to avoid having different hashes
    dumped_json = dump_json(dictionary)

    json_hash = hashlib.md5(dumped_json.encode("utf-8")).hexdigest()

    return json_hash

def get_hash_of_list(list_obj):
    #return str(hash(frozenset(list_obj)) ** 2)
    return hashlib.sha1(list_obj).hexdigest()[:5].upper()

def dump_json(json_obj):
    response = json.dumps(json_obj, sort_keys=True, indent=4, cls=CustomEncoder)

    return response

def dump_json_pretty(json_obj, replace_new_line=True, sort_keys=True):
    response = json.dumps(json_obj, sort_keys=sort_keys, indent=4, cls=CustomEncoder)
    if replace_new_line:
        response = response.replace('\\n', '\n').replace('\\"', '"') # This is only applied when you don't need to programatically read jsons

    return response

def dump_json_sorted_by_values(json_obj) -> str:
    response = json.dumps(json_obj, sort_keys=False, indent=4, cls=CustomEncoder)
    response = response.replace('\\n', '\n').replace('\\"', '"')

    return response

def dump_json_with_separators(obj, separators):
    return json.dumps(obj, indent=4, sort_keys=True, separators=separators, cls=CustomEncoder)

def json_loads(obj):
    return json.loads(obj)