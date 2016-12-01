from cziso.commands import CommonArgs, Arg, Opt
import cziso.commands
import cziso.clonezilla
import os


class Command(cziso.commands.Command):
	usage = CommonArgs(
		"""
		Update our customized Clonezilla Live VM iso
		""",
		[
			Arg("zip", "The path to regular Clonezilla Live VM zip file"),
		],
		[
			Opt(
				"revision",
				"Upload the ISOs as a revision of existing ISOs",
				"false"),
			 Opt(
				"upload",
				"Upload the customized and regular ISOs",
				"false")
		]
	)

	def __init__(self):
		cziso.commands.Command.__init__(self)
		self.file = __file__

	def run(self, config, args):
		arg_vals = self.parse_args(args)

		cz = cziso.clonezilla.Clonezilla(config)
		(regular_iso, custom_iso) = cz.update(arg_vals["zip"])
		if self.is_arg_true(arg_vals["upload"]):
			revision = self.is_arg_true(arg_vals["revision"])
			import cziso.gdrive as googledrive
			drive = googledrive.GdriveAuth(config)
			drive.upload(regular_iso, revision=revision)
			drive.upload(custom_iso, revision=revision)
			self.logger.info("Removing cached custom and regular ISOs")
			os.remove(cz.clonezilla_custom.get_or_download())
			os.remove(cz.clonezilla_regular.get_or_download())


