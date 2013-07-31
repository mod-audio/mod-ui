import os
import os.path as path

os.environ['MOD_DATA_DIR'] = path.join(path.dirname(path.realpath(__file__)), "fixtures/dados/")
os.environ['MOD_DEV_ENVIRONMENT'] = "1"
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = "9696"
