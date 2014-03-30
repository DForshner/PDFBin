"""
PDFBin - prototype
"""

import os
import urllib
import webapp2
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.blobstore import BlobInfo

import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class MainHandler(webapp2.RequestHandler):
  def get(self):

    # Upload new blob
    upload_url = blobstore.create_upload_url('/upload')

    # List existing blobs
    docs = []
    for blob in BlobInfo.all().fetch(10):
      print("Found: ", blob.filename, " - ", blob.key())
      url = '/serve/' + urllib.quote(str(blob.key()).encode('utf-8'))
      doc = {'name': blob.filename, 'url': url}
      docs.append(doc)

    template_values = {
      'url': upload_url,
      'docs': docs
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.headers['Content-Type'] = 'text/html'
    self.response.write(template.render(template_values))

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  def post(self):
    upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
    blob_info = upload_files[0]
    self.redirect('/serve/%s' % blob_info.key())

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, resource):
    resource = str(urllib.unquote(resource.encode('ascii')).decode('utf-8'))
    blob_info = blobstore.BlobInfo.get(resource)
    self.send_blob(blob_info)

application = webapp2.WSGIApplication([
  ('/', MainHandler),
  ('/upload', UploadHandler),
  ('/serve/([^/]+)?', ServeHandler)],
  debug=True)
