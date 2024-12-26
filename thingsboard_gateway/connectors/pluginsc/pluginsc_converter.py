from thingsboard_gateway.connectors.converter import Converter, abstractmethod


class PluginscConverter(Converter):
    @abstractmethod
    def convert(self, config, data):
        pass
