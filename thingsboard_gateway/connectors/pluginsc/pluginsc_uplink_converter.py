from thingsboard_gateway.connectors.pluginsc.pluginsc_converter import PluginscConverter
from thingsboard_gateway.gateway.statistics.decorators import CollectStatistics
import json


class PluginscUplinkConverter(PluginscConverter):
    def __init__(self, config, logger):
        self.__log = logger
        self.__config = config
        self.__datatypes = {"timeseries": "telemetry", "attributes": "attributes"}

    @CollectStatistics(start_stat_type='receivedBytesFromDevices',
                       end_stat_type='convertedBytesFromDevice')
    def convert(self, data):
        try:
            return json.loads(data)
        except Exception as e:
            self.__log.exception(e)
