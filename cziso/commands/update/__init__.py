from cziso.commands import CommonArgs, Arg, Opt
import cziso.commands
import cziso.clonezilla


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
		cz.update(arg_vals["zip"])
		# gdrive = cziso.gdrive.GdriveAuth(config)
		# gdrive.upload(
		# 	arg_vals["file"],
		# 	arg_vals["gdrive_folder"],
		# 	self.is_arg_true(arg_vals["revision"]))

