import json
import os

from sqlalchemy_imageattach.stores.fs import HttpExposedFileSystemStore

# Allowed Extensions for Uploaded Pictures
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'bmp'])

# absolute path of the app on server
app_path = '/vagrant/'

# variables and path for postgres database
user = 'postgres'
password = 'biologics'
db_name = 'biologics-catalog'
db_path = 'postgresql://{0}:{1}@localhost/{2}'.format(user, password, db_name)

# Location of where the pictures will be uploaded and their web url
fs_store = HttpExposedFileSystemStore(
    path=os.path.join(app_path, 'static/images/'))

# Google OAuth Objects
google_client_secrets = json.loads(
    open(os.path.join(app_path,
                      'client_secrets.json'), 'r').read())

# Facebook OAuth Objects
facebook_client_secrets = json.loads(
    open(os.path.join(app_path,
                      'fb_client_secrets.json'), 'r').read())
