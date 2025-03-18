import logging
import os
from datetime import datetime, timedelta
import time
import threading
logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
def get_log_file_path():
    now = datetime.now()
    log_dir = os.path.join(os.getcwd(), 'utils/logs', str(now.year), str(now.month), str(now.day))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'{now.hour}.log')
    return log_file
file_handler = logging.FileHandler(get_log_file_path())
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = True
__all__ = ['logger']
def update_file_handler():
    global file_handler
    while True:
        current_log_file = file_handler.baseFilename
        new_log_file = get_log_file_path()
        if current_log_file != new_log_file:
            logger.removeHandler(file_handler)
            file_handler.close()
            file_handler = logging.FileHandler(new_log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        time.sleep(720)

thread = threading.Thread(target=update_file_handler)
thread.daemon = True
thread.start()