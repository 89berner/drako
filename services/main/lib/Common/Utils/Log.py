import logging
import sys
import pyfiglet

# this is a pointer to the module object instance itself.
this = sys.modules[__name__]

class DummyLogger:
    def warning(self, *args):
        pass

    def warn(self, *args):
        pass

    def info(self, *args):
        pass

    def debug(self, *args):
        pass

    def error(self, *args):
        pass

# we can explicitly make assignments on it 
this.logger       = None
this.super_logger = DummyLogger()

# ONLY WORKS WITH WARNING LEVEL
def setup_super_logger():
    this.super_logger = logging.getLogger()
    formatter         = logging.Formatter('SUPER LOGGER => %(asctime)s - [%(filename)s:%(lineno)s - %(funcName)s() ] - %(levelname)s - %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.DEBUG)
    this.super_logger.addHandler(ch)
    this.super_logger.debug("Finished setting up super logger")
    this.super_logger.warning("Finished setting up super logger")

def add_debug_separator():
    this.logger.debug("=" * 30)
    this.logger.debug("=" * 30)
    this.logger.debug("=" * 30)
    this.logger.debug("=" * 30)

def add_info_separator():
    this.logger.info("=" * 30)
    this.logger.info("=" * 30)
    this.logger.info("=" * 30)
    this.logger.info("=" * 30)

def add_debug_medium_ascii(text):
    ascii_text = pyfiglet.figlet_format(text, font="cybermedium")
    this.logger.debug("\n" + "=" * 75 + "\n" + ascii_text + "=" * 75)

def add_debug_large_ascii(text):
    ascii_text = pyfiglet.figlet_format(text, font="cyberlarge")
    this.logger.debug("\n" + "=" * 100 + "\n" + ascii_text + "=" * 100)

def add_info_medium_ascii(text):
    ascii_text = pyfiglet.figlet_format(text, font="cybermedium")
    this.logger.info("\n" + "=" * 75 + "\n" + ascii_text + "=" * 75)

def add_info_large_ascii(text):
    ascii_text = pyfiglet.figlet_format(text, font="cyberlarge")
    this.logger.info("\n" + "=" * 100 + "\n" + ascii_text + "=" * 100)

def teardown_super_logger():
    close_logger(this.super_logger)
    this.super_logger = DummyLogger()
    this.logger.warning("Finished tearing down super logger")

def initialize_log(log_level, filename=None, identifier=None):
    if this.logger is None:
        this.logger = logging.getLogger("root")
        this.logger.setLevel(logging.DEBUG)

        if log_level == "2":
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
        elif log_level == "1":
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
        elif log_level == "0":
            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)
        else:
            raise NotImplementedError("Unknown log level: %s" % log_level)

        if identifier is None:
            formatter = logging.Formatter(
                '%(asctime)s - [%(filename)s:%(lineno)s - %(funcName)s() ] - %(levelname)s - %(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - (' + str(identifier) + ') [%(filename)s:%(lineno)s - %(funcName)s() ] - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        this.logger.addHandler(ch)

        from logging.handlers import TimedRotatingFileHandler
        handler = TimedRotatingFileHandler('/shared/logs/start_recon.log', when="midnight", interval=1, backupCount=0)
        this.logger.addHandler(handler)

        if filename is not None:
            fh_info = logging.FileHandler(f"{filename}.info", 'w')
            fh_info.setLevel(logging.INFO)
            fh_info.setFormatter(formatter)
            this.logger.addHandler(fh_info)

            fh_debug = logging.FileHandler(f"{filename}.debug", 'w')
            fh_debug.setLevel(logging.DEBUG)
            fh_debug.setFormatter(formatter)
            this.logger.addHandler(fh_debug)

        this.logger.propagate = False
    else:
        # this.logger.warning("Logger is already initialized, will skip this!")
        raise ValueError("You can't initialized logger twice")

def close_logger(logger):
    handlers = logger.handlers[:]
    for handler in handlers:
        handler.close()
        logger.removeHandler(handler)

def close_log():
    this.logger.warning("Closing logger!")
    close_logger(this.logger)
    this.logger = None
