from thingsboard_gateway.connectors.iec104.iec104_converter import Iec104Converter
from thingsboard_gateway.gateway.statistics.decorators import CollectStatistics

class Iec104DownlinkConverter(Iec104Converter):
    def __init__(self, config, logger):
        self.__log = logger
        self.__config = config

    @CollectStatistics(start_stat_type='allReceivedBytesFromTB',
                       end_stat_type='allBytesSentToDevices')
    def convert(self, config, data):
        pass
