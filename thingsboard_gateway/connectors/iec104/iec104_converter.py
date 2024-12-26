from thingsboard_gateway.connectors.converter import Converter, abstractmethod

class Iec104Converter(Converter):
    @abstractmethod
    def convert(self, config, data):
        pass