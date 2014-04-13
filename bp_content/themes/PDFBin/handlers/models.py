
# Put here your models or extend User model from bp_includes/models.py

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.blobstore import blobstore


class PDF(db.Model):
    file_name = db.StringProperty(db.Key)
    blob_key = blobstore.BlobReferenceProperty(blobstore.BlobKey, required=False)
    create_timestamp = db.DateTimeProperty(auto_now_add=True)
    update_timestamp = db.DateTimeProperty(auto_now=True)