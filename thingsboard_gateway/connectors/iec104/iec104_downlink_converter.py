from thingsboard_gateway.connectors.iec104.iec104_converter import Iec104Converter, log
from thingsboard_gateway.gateway.statistics_service import StatisticsService

class Iec104DownlinkConverter(Iec104Converter):
    def __init__(self, config):
        self.__config = config

    @StatisticsService.CollectStatistics(start_stat_type='allReceivedBytesFromTB',  end_stat_type='allBytesSentToDevices')
    def convert(self, config, data):
        try:
            pass
        except Exception as e:
            log.exception(e)
