from thingsboard_gateway.connectors.iec104.iec104_converter import Iec104Converter, log
from thingsboard_gateway.gateway.statistics_service import StatisticsService


class Iec104UplinkConverter(Iec104Converter):
    def __init__(self, config):
        self.__config = config
        self.__datatypes = {"timeseries": "telemetry", "attributes": "attributes"}

    @StatisticsService.CollectStatistics(start_stat_type='receivedBytesFromDevices', end_stat_type='convertedBytesFromDevice')
    def convert(self, data):

        dict_result = {"deviceName": None, "deviceType": None, "attributes": [], "telemetry": []}

        dict_result["deviceName"] = self.__config.get("deviceName")
        dict_result["deviceType"] = self.__config.get("deviceType")

        have_data_flag = False

        try:
            for datatype in self.__datatypes:
                for object_config in self.__config.get(self.__datatypes[datatype], []):
                    if object_config['ioa'] in data:
                        decoded_data = data[object_config['ioa']]
                        if object_config.get("divider"):
                            decoded_data = float(decoded_data) / float(object_config["divider"])
                        if object_config.get("multiplier"):
                            decoded_data = decoded_data * object_config["multiplier"]
                        if object_config.get("addition"):
                            decoded_data = float(decoded_data) + float(object_config["addition"])
                        dict_result[self.__datatypes[datatype]].append({object_config['key']: decoded_data})
                        have_data_flag = True
        except Exception as e:
            log.exception(e)

        if (have_data_flag):
            return dict_result
        else:
            return None
