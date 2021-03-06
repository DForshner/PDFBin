# -*- coding: utf-8 -*-

"""
    A real simple app for using webapp2 with auth and session.

    It just covers the basics. Creating a user, login, logout
    and a decorator for protecting certain handlers.

    Routes are setup in routes.py and added in main.py
"""
# standard library imports
import logging

# related third party imports
import os
import webapp2
import urllib
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from webapp2_extras.auth import InvalidAuthIdError, InvalidPasswordError
from webapp2_extras.i18n import gettext as _
from bp_includes.external import httpagentparser
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers



# local application/library specific imports
import bp_includes.lib.i18n as i18n
from bp_includes.lib.basehandler import BaseHandler
from bp_includes.lib.decorators import user_required
from bp_includes.lib import captcha, utils
import bp_includes.models as models_boilerplate

# Import from current theme
import models as models
import forms as forms


class ListHandler(BaseHandler):
    """
    Lists uploaded content.
    """

    def get(self):
        # List 30 latest PDFs uploaded
        docs = []
        doc_key = ndb.Key("Documents", "PDFs")
        for blob in models.PDF.query_pdf(doc_key).fetch(30):
        #for blob in models.PDF.fetch(30):
            print("Found: ", blob.file_name, " - ", blob.blob_key, " - ", blob.create_timestamp)
            url = '/serve/' + urllib.quote(str(blob.blob_key).encode('utf-8'))
            view_text_url = '/view/' + urllib.quote(str(blob.blob_key).encode('utf-8'))
            doc = {'name': blob.file_name, 'url': url, 'view_text_url': view_text_url,
                   'created_timestamp': blob.create_timestamp}
            docs.append(doc)

        upload_url = blobstore.create_upload_url('/upload/')

        params = {
            'upload_url': upload_url,
            'docs': docs
        }
        return self.render_template('list.html', **params)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    """
    Handler for uploading new content.
    """

    def post(self):
        upload_files = self.get_uploads('file')  # 'file' is file upload field in the form

        if not upload_files:
            logging.info("User did not upload file")
            self.redirect('/list/')
            return

        blob_info = upload_files[0]
        logging.info("FOUND blob info" + str(blob_info))

        # Store in data store
        doc_key = ndb.Key("Documents", "PDFs")
        pdf = models.PDF(parent=doc_key, file_name=blob_info.filename, blob_key=blob_info.key())
        pdf.put()

        self.redirect('/serve/%s' % blob_info.key())


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    """
    Handler for serving uploaded content.
    """

    def get(self, **kwargs):
        resource = kwargs['param']
        logging.info("SERVE " + str(resource))
        resource = str(urllib.unquote(resource.encode('ascii')).decode('utf-8'))
        blob_info = blobstore.BlobInfo.get(resource)

        self.send_blob(blob_info)


from bp_content.themes.PDFBin.external.pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from bp_content.themes.PDFBin.external.pdfminer.converter import HTMLConverter, TextConverter, PDFConverter
from bp_content.themes.PDFBin.external.pdfminer.layout import LAParams
from bp_content.themes.PDFBin.external.pdfminer.pdfpage import PDFPage
from bp_content.themes.PDFBin.external.pdfminer.pdfparser import PDFParser
from bp_content.themes.PDFBin.external.pdfminer.pdfdocument import PDFDocument

class ViewHandler(BaseHandler):
    """
    """

    def get(self, **kwargs):
        resource = kwargs['param']
        logging.info("SERVE " + str(resource))
        resource = str(urllib.unquote(resource.encode('ascii')).decode('utf-8'))
        blob_info = blobstore.BlobInfo.get(resource)

        blob_reader = blobstore.BlobReader(resource)

        #from cStringIO import StringIO
        #retstr = StringIO(blob_info)

        # Cast to StringIO object
        from StringIO import StringIO
        memory_file = StringIO(blob_reader.read())
        blob_reader.close()

        # Create a PDF parser object associated with the StringIO object
        parser = PDFParser(memory_file)

        # Create a PDF document object that stores the document structure
        document = PDFDocument(parser)

        # Define parameters to the PDF device object
        rsrcmgr = PDFResourceManager()
        retstr = StringIO()

        # Create a PDF device object
        device = TextConverter(rsrcmgr, retstr, codec='utf-8', laparams=LAParams())
        #device = HTMLConverter(rsrcmgr, retstr, codec='utf-8', laparams=LAParams())

        # Create a PDF interpreter object
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        # Process each page contained in the document
        for page in PDFPage.create_pages(document):
            interpreter.process_page(page)
            data = retstr.getvalue()

        self.response.out.write('<html><body>')
        self.response.out.write("%s" % data)
        self.response.out.write("</body></html>")


class ContactHandler(BaseHandler):
    """
    Handler for Contact Form
    """

    def get(self):
        """ Returns a simple HTML for contact form """

        if self.user:
            user_info = self.user_model.get_by_id(long(self.user_id))
            if user_info.name or user_info.last_name:
                self.form.name.data = user_info.name + " " + user_info.last_name
            if user_info.email:
                self.form.email.data = user_info.email

        params = {
            "exception": self.request.get('exception')
        }

        return self.render_template('contact.html', **params)

    def post(self):
        """ validate contact form """

        if not self.form.validate():
            return self.get()
        remote_ip = self.request.remote_addr
        city = i18n.get_city_code(self.request)
        region = i18n.get_region_code(self.request)
        country = i18n.get_country_code(self.request)
        coordinates = i18n.get_city_lat_long(self.request)
        user_agent = self.request.user_agent
        exception = self.request.POST.get('exception')
        name = self.form.name.data.strip()
        email = self.form.email.data.lower()
        message = self.form.message.data.strip()
        template_val = {}

        try:
            # parsing user_agent and getting which os key to use
            # windows uses 'os' while other os use 'flavor'
            ua = httpagentparser.detect(user_agent)
            _os = ua.has_key('flavor') and 'flavor' or 'os'

            operating_system = str(ua[_os]['name']) if "name" in ua[_os] else "-"
            if 'version' in ua[_os]:
                operating_system += ' ' + str(ua[_os]['version'])
            if 'dist' in ua:
                operating_system += ' ' + str(ua['dist'])

            browser = str(ua['browser']['name']) if 'browser' in ua else "-"
            browser_version = str(ua['browser']['version']) if 'browser' in ua else "-"

            template_val = {
                "name": name,
                "email": email,
                "ip": remote_ip,
                "city": city,
                "region": region,
                "country": country,
                "coordinates": coordinates,

                "browser": browser,
                "browser_version": browser_version,
                "operating_system": operating_system,
                "message": message
            }
        except Exception as e:
            logging.error("error getting user agent info: %s" % e)

        try:
            subject = _("Contact") + " " + self.app.config.get('app_name')
            # exceptions for error pages that redirect to contact
            if exception != "":
                subject = "{} (Exception error: {})".format(subject, exception)

            body_path = "emails/contact.txt"
            body = self.jinja2.render_template(body_path, **template_val)

            email_url = self.uri_for('taskqueue-send-email')
            taskqueue.add(url=email_url, params={
                'to': self.app.config.get('contact_recipient'),
                'subject': subject,
                'body': body,
                'sender': self.app.config.get('contact_sender'),
            })

            message = _('Your message was sent successfully.')
            self.add_message(message, 'success')
            return self.redirect_to('contact')

        except (AttributeError, KeyError), e:
            logging.error('Error sending contact form: %s' % e)
            message = _('Error sending the message. Please try again later.')
            self.add_message(message, 'error')
            return self.redirect_to('contact')

    @webapp2.cached_property
    def form(self):
        return forms.ContactForm(self)


class SecureRequestHandler(BaseHandler):
    """
    Only accessible to users that are logged in
    """

    @user_required
    def get(self, **kwargs):
        user_session = self.user
        user_session_object = self.auth.store.get_session(self.request)

        user_info = self.user_model.get_by_id(long(self.user_id))
        user_info_object = self.auth.store.user_model.get_by_auth_token(
            user_session['user_id'], user_session['token'])

        try:
            params = {
                "user_session": user_session,
                "user_session_object": user_session_object,
                "user_info": user_info,
                "user_info_object": user_info_object,
                "userinfo_logout-url": self.auth_config['logout_url'],
            }
            return self.render_template('secure_zone.html', **params)
        except (AttributeError, KeyError), e:
            return "Secure zone error:" + " %s." % e


class DeleteAccountHandler(BaseHandler):
    @user_required
    def get(self, **kwargs):
        chtml = captcha.displayhtml(
            public_key=self.app.config.get('captcha_public_key'),
            use_ssl=(self.request.scheme == 'https'),
            error=None)
        if self.app.config.get('captcha_public_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE" or \
                        self.app.config.get('captcha_private_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE":
            chtml = '<div class="alert alert-error"><strong>Error</strong>: You have to ' \
                    '<a href="http://www.google.com/recaptcha/whyrecaptcha" target="_blank">sign up ' \
                    'for API keys</a> in order to use reCAPTCHA.</div>' \
                    '<input type="hidden" name="recaptcha_challenge_field" value="manual_challenge" />' \
                    '<input type="hidden" name="recaptcha_response_field" value="manual_challenge" />'
        params = {
            'captchahtml': chtml,
        }
        return self.render_template('delete_account.html', **params)

    def post(self, **kwargs):
        challenge = self.request.POST.get('recaptcha_challenge_field')
        response = self.request.POST.get('recaptcha_response_field')
        remote_ip = self.request.remote_addr

        cResponse = captcha.submit(
            challenge,
            response,
            self.app.config.get('captcha_private_key'),
            remote_ip)

        if cResponse.is_valid:
            # captcha was valid... carry on..nothing to see here
            pass
        else:
            _message = _('Wrong image verification code. Please try again.')
            self.add_message(_message, 'error')
            return self.redirect_to('delete-account')

        if not self.form.validate() and False:
            return self.get()
        password = self.form.password.data.strip()

        try:

            user_info = self.user_model.get_by_id(long(self.user_id))
            auth_id = "own:%s" % user_info.username
            password = utils.hashing(password, self.app.config.get('salt'))

            try:
                # authenticate user by its password
                user = self.user_model.get_by_auth_password(auth_id, password)
                if user:
                    # Delete Social Login
                    for social in models_boilerplate.SocialUser.get_by_user(user_info.key):
                        social.key.delete()

                    user_info.key.delete()

                    ndb.Key("Unique", "User.username:%s" % user.username).delete_async()
                    ndb.Key("Unique", "User.auth_id:own:%s" % user.username).delete_async()
                    ndb.Key("Unique", "User.email:%s" % user.email).delete_async()

                    #TODO: Delete UserToken objects

                    self.auth.unset_session()

                    # display successful message
                    msg = _("The account has been successfully deleted.")
                    self.add_message(msg, 'success')
                    return self.redirect_to('home')


            except (InvalidAuthIdError, InvalidPasswordError), e:
                # Returns error message to self.response.write in
                # the BaseHandler.dispatcher
                message = _("Incorrect password! Please enter your current password to change your account settings.")
                self.add_message(message, 'error')
            return self.redirect_to('delete-account')

        except (AttributeError, TypeError), e:
            login_error_message = _('Your session has expired.')
            self.add_message(login_error_message, 'error')
            self.redirect_to('login')

    @webapp2.cached_property
    def form(self):
        return forms.DeleteAccountForm(self)
