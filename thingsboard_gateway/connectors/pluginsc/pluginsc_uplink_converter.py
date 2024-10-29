from thingsboard_gateway.connectors.pluginsc.pluginsc_converter import PluginscConverter, log
from thingsboard_gateway.gateway.statistics_service import StatisticsService
import json


class PluginscUplinkConverter(PluginscConverter):
    def __init__(self, config):
        self.__config = config
        self.__datatypes = {"timeseries": "telemetry", "attributes": "attributes"}

    @StatisticsService.CollectStatistics(start_stat_type='receivedBytesFromDevices', end_stat_type='convertedBytesFromDevice')
    def convert(self, data):
        try:
            return json.loads(data)
        except Exception as e:
            log.exception(e)
