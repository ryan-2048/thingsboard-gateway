from thingsboard_gateway.connectors.pluginsc.pluginsc_converter import PluginscConverter, log
from thingsboard_gateway.gateway.statistics_service import StatisticsService
import json

class PluginscDownlinkConverter(PluginscConverter):
    def __init__(self, config):
        self.__config = config

    @StatisticsService.CollectStatistics(start_stat_type='allReceivedBytesFromTB',  end_stat_type='allBytesSentToDevices')
    def convert(self, data):
        try:
            return json.dumps(data)
        except Exception as e:
            log.exception(e)
