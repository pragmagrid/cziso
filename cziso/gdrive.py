import logging
import cziso
import httplib2
import os


class GdriveAuth:
	SCOPE = "https://www.googleapis.com/auth/drive"

	def __init__(self, config):
		self.logger = logging.getLogger(self.__module__)
		self.service_account_credentials = config.get(
			"google", "service_account_credentials")
		self.chunk_size = int(config.get("google", "chunk_size"))
		self.default_drive_dir_id = config.get("google", "default_drive_id")

		try:
			import apiclient.discovery
			from oauth2client.service_account import ServiceAccountCredentials

			self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
				self.service_account_credentials, GdriveAuth.SCOPE)

			http_auth = self.credentials.authorize(httplib2.Http())
			self.drive = apiclient.discovery.build('drive', 'v3', http=http_auth,
				cache_discovery=False)
		except Exception as e:
			error = """
Problem authenticating to Google Drive: %s

To use the upload function, you must have the Python Google APIs installed.
Please see the following URL to see how to install the APIs:

https://developers.google.com/api-client-library/python/start/installation
			"""
			cziso.abort(error % str(e))

		self.logger.debug("Successfully imported Google API")

	def _request_create_or_update(self, existing_file, file_path, folder_id,
	                              filename, description=None):
		"""
		Private function to start a HTTP request as either a create or update
		to file if file already exists

		:param existing_file: A boolean where True indicates this file
		currently exists in Google drive so update; otherwise False and
		create is requested.
		:param file_path: A string containing the path of the file to upload
		:param folder_id:  A string containing the Google drive folder id to
		upload file to
		:param filename: A string containing the Google drive filename
		:param description:  An optional description for the Google drive file

		:return:
		"""

		file_metadata = {
			'name': filename,
			'mimeType': 'application/octetstream'}
		if description is not None:
			file_metadata["description"] = description

		import apiclient.http
		media = apiclient.http.MediaFileUpload(
			file_path, mimetype='application/octetstream',
			chunksize=self.chunk_size, resumable=True)
		request = None
		if existing_file is None:
			file_metadata['parents'] = [folder_id]
			request = self.drive.files().create(
				body=file_metadata, media_body=media, keepRevisionForever=True)
		else:
			request = self.drive.files().update(
				fileId=existing_file, body=file_metadata, media_body=media,
				keepRevisionForever=True)
		return request, media

	def _upload_file(self, request, media):
		"""
		Given the start of a create or update request, upload the file and
		report progress.

		:param request: An object of type apiclient.http.HttpRequest
		:param media: An object of type apiclient.http.MediaFileUpload

		:return: The Google drive id for successfully uploaded file
		"""
		total_megabytes = media.size() / (1024.0 * 1024.0)
		response = None
		while response is None:
			status, response = request.next_chunk()
			if status:
				percent_progress = status.progress() * 100
				uploaded_megabytes = total_megabytes * status.progress()
				self.logger.info(
					"Uploaded %.1f of %.1f MB (%.1f%% complete)" % (
						uploaded_megabytes, total_megabytes, percent_progress))
		return response['id']

	def get_file(self, filename, folder_id):
		"""
		Get the Google drive id for matching filename in Google drive folder

		:param filename: Name of a file to search for in Google drive
		:param folder_id: The Google drive id for the folder to search in

		:return: A string representing the Google id for file
		"""
		query = "name = '%s' and '%s' in parents" % (filename, folder_id)
		results = self.drive.files().list(q=query).execute()
		items = results.get('files', [])
		if not items:
			return None
		self.logger.debug("Found %i matching files for %s in folder %s" % (
			len(items), filename, folder_id))
		file_id = None
		for item in items:
			self.logger.debug('Google drive id %s' % item['id'])
			file_id = item['id']
		return file_id

	def get_metadata(self, id):
		"""
		Get metadata for Google drive object

		:param id: Identifier for Google drive object

		:return: Metadata as a JSON object or None if not found
		"""
		import apiclient.http
		try:
			return self.drive.files().get(fileId=id).execute()
		except apiclient.errors.HttpError:
			return None

	def upload(self, file_path,
			filename=None, folder_id=None, revision=False, description=None):
		"""
		Upload specified file to Google drive folder

		:param file_path: A string containing the path to the file to upload
		:param filename: A string containing a different name of the file on
		Google drive (default: filename of uploading file)
		:param folder_id: The Google drive id for the folder to upload to
		:param revision: A boolean value that is True if the file being uploaded
		already exists in Google drive and this is a new revision of file;
		otherwise False.
		:param description: A description for the Google drive file

		:return: A string containing the Google drive id for file
		"""

		if not os.path.exists(file_path):
			cziso.abort("File %s does not exist" % file_path)
		if filename is None:
			filename = os.path.basename(file_path)

		if folder_id is None:
			folder_id = self.default_drive_dir_id
		if self.get_metadata(folder_id) is None:
			cziso.abort("Google Drive folder %s does not exist" % folder_id)

		self.logger.info(
			"Uploading file %s to Gdrive %s" % (file_path, folder_id))

		existing_file = self.get_file(filename, folder_id)
		if existing_file is not None and revision is False:
			cziso.abort("File %s already exists in drive folder %s. %s" % (
				filename, folder_id,
				"Please re-run with revision=true to upload as new revision"
			))

		request, media = self._request_create_or_update(
			existing_file, file_path, folder_id, filename, description)
		id = self._upload_file(request, media)
		self.logger.info("Upload Complete!")
		self.logger.info(
			"Google drive id for %s is %s" % (file_path, id))
		return id


