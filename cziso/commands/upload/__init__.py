import cziso
from cziso.commands import CommonArgs, Arg, Opt


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Upload the specified file to specified Google drive folder.  If file
		already exists, the upload will fail unless revision=true is specified.
		""",
		[
			Arg("file", "The path to  file you want to upload to Google Drive"),
			Arg(
				"gdrive_folder",
				"Google Drive ID for folder you want to upload to")
		],
		[
			Opt(
				"revision",
				"Upload the file as a revision of existing Google drive file",
				"false"),
			Opt("description", "New description of file", None)
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		gdrivemodule = None
		try:
			gdrivemodule = __import__("cziso.gdrive")
		except ImportError as e:
			cziso.abort("Missing %s" % str(e))

		gdrive = gdrivemodule.GdriveAuth(config)

		gdrive.upload(
			arg_vals["file"],
			arg_vals["gdrive_folder"],
			self.is_arg_true(arg_vals["revision"]),
			arg_vals["description"])

