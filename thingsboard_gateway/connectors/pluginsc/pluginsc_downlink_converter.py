from thingsboard_gateway.connectors.pluginsc.pluginsc_converter import PluginscConverter
from thingsboard_gateway.gateway.statistics.decorators import CollectStatistics
import json

class PluginscDownlinkConverter(PluginscConverter):
    def __init__(self, config, logger):
        self.__log = logger
        self.__config = config

    @CollectStatistics(start_stat_type='allReceivedBytesFromTB',
                       end_stat_type='allBytesSentToDevices')
    def convert(self, data):
        try:
            return json.dumps(data)
        except Exception as e:
            self.__log.exception(e)
