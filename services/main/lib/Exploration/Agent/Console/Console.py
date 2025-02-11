import sys
import lib.Common.Utils.Log as Log

HEADER = '\033[95m'
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

def set_highlighted_excepthook():
    import sys, traceback
    def myexcepthook(type, value, tb):
        tbtext = ''.join(traceback.format_exception(type, value, tb))
        sys.stderr.write(FAIL + tbtext + ENDC)

    sys.excepthook = myexcepthook

set_highlighted_excepthook()

def print_to_console(message, message_type = "normal"):
    if message_type == "error":
        print(FAIL + message + ENDC)
        Log.logger.error(message)
    elif message_type == "warning":
        print(WARNING + message + ENDC)
        Log.logger.warn(message)
    else:
        print(OKGREEN + message + ENDC)
        Log.logger.info(message)
    sys.stdout.flush()

def print_input_prompt(input_message):
    print(input_message.strip())
    sys.stdout.flush()

def raise_exception(error_message):
    raise Exception(error_message)