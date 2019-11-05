from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedMachineSet


class TestMachineSetPlugin(BasePlugin):
    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        if "bad-machine" in machine_set:
            raise PluginRejectedMachineSet("{} has invalid machine set".format(name))
