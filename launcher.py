
import os
import subprocess
import sys
import time

try:
    import monitor
except ImportError:
    monitor = None
    
HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.basename(os.path.dirname(__file__))
PROG = "C14-webservice.exe"


def trace(msg):
    """
    Print a trace message
    :param msg:
    :return:
    """
    print(PLUGIN + ": {}".format(msg), file=sys.stderr)
    return msg

def find_server_program():
    """
    Look for C14-webservice.exe
    """
    # global _prog
    # if _prog is not None:
    #     return _prog

    locations = [
        os.path.join(HERE, PROG),
        os.path.join(HERE, PLUGIN, PROG)
    ]
    for item in locations:
        if os.path.isfile(item):
            trace(PLUGIN+": exe found at {}...".format(item))
            _prog = item
            return item
    return None


_service = None

def check_game_running():
    return True
    if not monitor:
        return True

    return monitor.monitor.game_running()


def launch_server():
    """
    Start the service program
    """
    trace(f'Launching serveur...')
    if HERE not in sys.path:
        sys.path.append(HERE)

    if not check_game_running():
        return

    global _service
    program = find_server_program()
    exedir = os.path.abspath(os.path.dirname(program))

    try:
        if _service:
            if _service.poll() is not None:
                _service = None

        if not _service:
            if check_game_running():
                trace(PROG + " is starting {}".format(program))
            _service = subprocess.Popen([program], cwd=exedir)
        time.sleep(3)
        if _service.poll() is not None:
            subprocess.check_call([program], cwd=exedir)
            raise Exception("{} exited".format(program))
    except Exception as err:
        if check_game_running():
            trace("error in ensure_service: {}".format(err))
