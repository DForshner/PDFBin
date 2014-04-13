
# Put here your models or extend User model from bp_includes/models.py

from google.appengine.ext import ndb

class PDF(ndb.Model):
    """
    Stores information about a PDF.
    """

    file_name = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
    create_timestamp = ndb.DateTimeProperty(auto_now_add=True)
    update_timestamp = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def query_pdf(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(-cls.create_timestamp)