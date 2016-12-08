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
			description = \
				"Based on Clonezilla Live VM %s and generated on %s." % (
					os.path.basename(arg_vals["zip"]),
					cziso.get_current_time_string()
				)
			import cziso.gdrive as googledrive
			drive = googledrive.GdriveAuth(config)
			drive.upload(regular_iso, description=description, revision=True,
				filename=cz.clonezilla_regular.filename)
			drive.upload(custom_iso, description=description, revision=True,
			    filename=cz.clonezilla_custom.filename)
			for iso in (
				cz.clonezilla_custom.iso_path, cz.clonezilla_regular.iso_path):
				if os.path.exists(iso):
					self.logger.info("Removing cached iso %s" % iso)
					os.remove(iso)


