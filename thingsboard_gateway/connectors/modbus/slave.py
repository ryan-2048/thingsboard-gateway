#     Copyright 2024. ThingsBoard
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

from threading import Thread
from time import sleep, monotonic

from pymodbus.constants import Defaults

from thingsboard_gateway.connectors.modbus.constants import *
from thingsboard_gateway.connectors.modbus.bytes_modbus_uplink_converter import BytesModbusUplinkConverter
from thingsboard_gateway.connectors.modbus.bytes_modbus_downlink_converter import BytesModbusDownlinkConverter
from thingsboard_gateway.tb_utility.tb_loader import TBModuleLoader


class Slave(Thread):
    def __init__(self, **kwargs):
        super().__init__()
        self.timeout = kwargs.get('timeout')
        self.device_name = kwargs['deviceName']
        self._log = kwargs['logger']
        self.poll_period = kwargs['pollPeriod'] / 1000

        self.last_connect_time = 0

        self.byte_order = kwargs.get('byteOrder', 'LITTLE')
        self.word_order = kwargs.get('wordOrder', 'LITTLE')

        attributes_data = kwargs.get('attributes', [])
        timeseries_data = kwargs.get('timeseries', [])
        once_register_count = kwargs.get('onceRegisterCount', 100)
        
        # attributes_sorted_data = sorted(attributes_data, key=lambda x: x['address'])
        attributes_sorted_data = sorted(
            attributes_data,
            key=lambda x: (x.get('functionCode', 0), x.get('address', 0))
        )

        attributes_data_result = []
        attributes_current_group = None
        attributes_last_address = -1

        for item in attributes_sorted_data:
            if item.get('pollPeriod') is None:
                item['pollPeriod'] = self.poll_period;
            if  attributes_current_group is None or item['functionCode'] != attributes_current_group['functionCode'] or item['pollPeriod'] != attributes_current_group['pollPeriod'] or item['address'] - attributes_last_address > attributes_current_group['details'][-1]['objectsCount'] or len(attributes_current_group['details']) >= once_register_count:
                if attributes_current_group is not None:
                    attributes_current_group['objectsCount'] = sum(detail['objectsCount'] for detail in attributes_current_group['details'])
                    attributes_data_result.append(attributes_current_group)
                attributes_current_group = {
                    'tag': len(attributes_data_result),
                    'functionCode': item['functionCode'],
                    'address': item['address'],
                    'pollPeriod': item['pollPeriod'],
                    'details': [item]
                }
            else:
                attributes_current_group['details'].append(item)

            attributes_last_address = item['address'] + item['objectsCount'] - 1

        attributes_prev_address = None
        if attributes_current_group is not None:
            attributes_current_group['objectsCount'] = sum(detail['objectsCount'] for detail in attributes_current_group['details'] if (attributes_prev_address != detail['address']) and (attributes_prev_address := detail['address']) is not None)
            attributes_data_result.append(attributes_current_group)

        # timeseries_sorted_data = sorted(timeseries_data, key=lambda x: x['address'])
        timeseries_sorted_data = sorted(
            timeseries_data,
            key=lambda x: (x.get('functionCode', 0), x.get('address', 0))
        )

        timeseries_data_result = []
        timeseries_current_group = None
        timeseries_last_address = -1

        for item in timeseries_sorted_data:
            if timeseries_current_group is None or item['functionCode'] != timeseries_current_group['functionCode'] or item['pollPeriod'] != timeseries_current_group['pollPeriod'] or item['address'] - timeseries_last_address > timeseries_current_group['details'][-1]['objectsCount'] or len(timeseries_current_group['details']) >= once_register_count:
                if timeseries_current_group is not None:
                    timeseries_current_group['objectsCount'] = sum(detail['objectsCount'] for detail in timeseries_current_group['details'])
                    timeseries_data_result.append(timeseries_current_group)
                timeseries_current_group = {
                    'tag': len(timeseries_data_result),
                    'functionCode': item['functionCode'],
                    'address': item['address'],
                    'pollPeriod': item['pollPeriod'],
                    'details': [item]
                }
            else:
                timeseries_current_group['details'].append(item)

            timeseries_last_address = item['address'] + item['objectsCount'] - 1

        timeseries_prev_address = None
        if timeseries_current_group is not None:
            timeseries_current_group['objectsCount'] = sum(detail['objectsCount'] for detail in timeseries_current_group['details'] if (timeseries_prev_address != detail['address']) and (timeseries_prev_address := detail['address']) is not None)
            timeseries_data_result.append(timeseries_current_group)
        
        self.config = {
            'unitId': kwargs['unitId'],
            'deviceType': kwargs.get('deviceType', 'default'),
            'type': kwargs['type'],
            'host': kwargs.get('host'),
            'port': kwargs['port'],
            'byteOrder': kwargs.get('byteOrder', 'LITTLE'),
            'wordOrder': kwargs.get('wordOrder', 'LITTLE'),
            'tls': kwargs.get('tls', kwargs.get('security')),
            'timeout': kwargs.get('timeout', 35),
            'stopbits': kwargs.get('stopbits', Defaults.Stopbits),
            'bytesize': kwargs.get('bytesize', Defaults.Bytesize),
            'parity': kwargs.get('parity', Defaults.Parity),
            'strict': kwargs.get('strict', True),
            'retries': kwargs.get('retries', 3),
            'connection_attempt': 0,
            'last_connection_attempt_time': 0,
            'waitAfterFailedAttemptsMs': kwargs.get('waitAfterFailedAttemptsMs', 0),
            'connectAttemptTimeMs': kwargs.get('connectAttemptTimeMs', 0),
            'retry_on_empty': kwargs.get('retryOnEmpty', False),
            'retry_on_invalid': kwargs.get('retryOnInvalid', False),
            'method': kwargs.get('method', 'rtu'),
            'baudrate': kwargs.get('baudrate', 19200),
            'attributes': attributes_data_result,
            'timeseries': timeseries_data_result,
            'attributeUpdates': kwargs.get('attributeUpdates', []),
            'rpc': kwargs.get('rpc', []),
            'readSleep': kwargs.get('readSleep', 0),
        }

        self.__basic_device_report_strategy_config = (
            self.__get_report_strategy_from_config(kwargs, kwargs.get(REPORT_STRATEGY_PARAMETER, {})))

        self.__load_converters(kwargs['connector'], kwargs.get('gateway'))

        self.callback = kwargs['callback']

        self.__last_polled_time = {'timeseries': {}, 'attributes': {}}
        self.__last_checked_time = monotonic()
        self.daemon = True
        self.stop = False
        # Cache for devices data for report strategy
        # Two possible for keys options, depending on type of slave:
        # 1. For tcp, tls, udp slaves:
        # (host, port, unit_id, datatype, function_code, address, bit - Optional, byteOrder - Optional, wordOrder - Optional)
        # 2. For serial slaves:
        # (port, unit_id, datatype, function_code, address, bit - Optional, byteOrder - Optional, wordOrder - Optional)
        # Value
        # {last_telemetry:{key: {strategy, reportPeriodMs(Depends on strategy), next_send_monotonic_ms, previous_value, values_for_calculation(In next release), processing_function(In next release)}},
        # last_attributes:{...}}

        self.cached_data = {
            LAST_PREFIX + TELEMETRY_PARAMETER: {},
            LAST_PREFIX + ATTRIBUTES_PARAMETER: {}
        }

        # Data to send periodically, key is monotonic of time when data should be sent

        self.__data_to_send_periodically = {}

        self.__init_cache_for_data()

        self.name = "Modbus slave processor for unit " + str(self.config['unitId']) + " on host " + str(
            self.config['host']) + ":" + str(self.config['port'])

        self.start()

    def timer(self):
        device_config = {'timeseries': {}, 'attributes': {}}
        for config_item in device_config:
            for index, item in enumerate(self.config[config_item]):
                self.callback(self, RequestType.POLL, {"type": config_item, "index": index})
                self.__last_polled_time[config_item][index] = {"ts": monotonic(), "period": item['pollPeriod'] / 1000}
        
        while not self.stop:
            try:
                current_monotonic = monotonic()
                for config_item in device_config:
                    for index in self.__last_polled_time[config_item]:
                        if current_monotonic - self.__last_polled_time[config_item][index]['ts'] >= self.__last_polled_time[config_item][index]['period']:
                            self.callback(self, RequestType.POLL, {"type": config_item, "index": index})
                            self.__last_polled_time[config_item][index]['ts'] = monotonic()
                            if (self.config['readSleep'] != 0):
                                sleep(self.config['readSleep'])
                if current_monotonic - self.__last_checked_time >= 1.0:
                    self.__check_data_to_send_periodically(current_monotonic)
                    self.__last_checked_time = current_monotonic
            except Exception as e:
                self._log.exception("Error in slave timer: %s", e)

            sleep(0.001)

    def run(self):
        self.timer()

    def close(self):
        self.stop = True

    def get_name(self):
        return self.device_name

    def __check_data_to_send_periodically(self, current_monotonic):
        telemetry_data_to_send = []
        attributes_data_to_send = []

        self.__check_data_to_send_periodically_entry(TELEMETRY_PARAMETER, telemetry_data_to_send, current_monotonic)
        self.__check_data_to_send_periodically_entry(ATTRIBUTES_PARAMETER, attributes_data_to_send, current_monotonic)

        if telemetry_data_to_send or attributes_data_to_send:
            self.callback(self, RequestType.SEND_DATA, {DEVICE_NAME_PARAMETER: self.device_name,
                            DEVICE_TYPE_PARAMETER: self.config["deviceType"],
                            TELEMETRY_PARAMETER: telemetry_data_to_send,
                            ATTRIBUTES_PARAMETER: attributes_data_to_send})

    def __check_data_to_send_periodically_entry(self, section, data_array: list, current_monotonic: float):
        for key, report_data_config in self.cached_data[LAST_PREFIX + section].items():
            if (report_data_config['type'] in (ReportStrategy.ON_CHANGE_OR_REPORT_PERIOD, ReportStrategy.ON_REPORT_PERIOD)
                    and report_data_config['previous_value'] is not None
                    and report_data_config['next_send_monotonic_ms'] <= current_monotonic):
                data_array.append({key: report_data_config['previous_value']})
                report_data_config['next_send_monotonic_ms'] = current_monotonic + report_data_config[REPORT_PERIOD_PARAMETER]

    def __init_cache_for_data(self):
        for indexs, key_configs in enumerate(self.config[TIMESERIES_PARAMETER]):
            for index, key_config in enumerate(key_configs['details']):
                key = key_config.get('key', key_config.get('tag'))
                self.cached_data[LAST_PREFIX + TELEMETRY_PARAMETER][key] = {
                    **self.__get_report_strategy_from_config(key_config, self.__basic_device_report_strategy_config),
                    'next_send_monotonic_ms': 0,
                    'previous_value': None
                }
        for indexs, key_configs in enumerate(self.config[ATTRIBUTES_PARAMETER]):
            for index, key_config in enumerate(key_configs['details']):
                key = key_config.get('key', key_config.get('tag'))
                self.cached_data[LAST_PREFIX + ATTRIBUTES_PARAMETER][key] = {
                    **self.__get_report_strategy_from_config(key_config, self.__basic_device_report_strategy_config),
                    'next_send_monotonic_ms': 0,
                    'previous_value': None
                }

    def update_cached_data_and_check_is_data_should_be_send(self, configuration_section, key, value) -> bool:
        section_with_prefix = LAST_PREFIX + configuration_section

        if key == 'lastDataTs':
            return True
        
        if self.cached_data[section_with_prefix][key]['type'] == ReportStrategy.ON_REPORT_PERIOD:
            return True
        
        previous_value = self.cached_data.get(section_with_prefix, {}).get(key, {}).get('previous_value')
        if previous_value is None:
            self.cached_data[section_with_prefix][key]['previous_value'] = value
            if self.cached_data[section_with_prefix][key]['type'] in (ReportStrategy.ON_CHANGE_OR_REPORT_PERIOD,
                                                                      ReportStrategy.ON_REPORT_PERIOD):
                self.cached_data[section_with_prefix][key]['next_send_monotonic_ms'] = (
                        monotonic() + self.cached_data[section_with_prefix][key][REPORT_PERIOD_PARAMETER])
            return True
        if previous_value != value:
            self.cached_data[section_with_prefix][key]['previous_value'] = value
            if self.cached_data[section_with_prefix][key]['type'] == ReportStrategy.ON_CHANGE:
                return True
            elif self.cached_data[section_with_prefix][key]['type'] == ReportStrategy.ON_CHANGE_OR_REPORT_PERIOD:
                self.cached_data[section_with_prefix][key]['next_send_monotonic_ms'] = (
                        monotonic() + self.cached_data[section_with_prefix][key][REPORT_PERIOD_PARAMETER])
                return True

        return False

    def __get_report_strategy_from_config(self, config: dict, default_report_strategy_config):
        report_strategy_config = default_report_strategy_config
        if not config:
            return report_strategy_config
        if config.get(SEND_DATA_ONLY_ON_CHANGE_PARAMETER) is not None and not (config.get(REPORT_STRATEGY_PARAMETER)):
            report_strategy_config = {
                'type': ReportStrategy.ON_CHANGE if config.get(SEND_DATA_ONLY_ON_CHANGE_PARAMETER) else ReportStrategy.ON_REPORT_PERIOD,
                REPORT_PERIOD_PARAMETER: config.get(REPORT_PERIOD_PARAMETER, report_strategy_config.get(REPORT_PERIOD_PARAMETER, self.poll_period))
            }
        elif config.get(REPORT_STRATEGY_PARAMETER) is not None:
            try:
                report_strategy_config = {
                    'type': ReportStrategy[config[REPORT_STRATEGY_PARAMETER].get('type', ReportStrategy.ON_REPORT_PERIOD.name).upper()],
                    REPORT_PERIOD_PARAMETER: config[REPORT_STRATEGY_PARAMETER].get(REPORT_PERIOD_PARAMETER, 60000) / 1000
                }
            except Exception:
                self._log.error("Report strategy config is not valid. Using default report strategy for config: %r", config)
                report_strategy_config = default_report_strategy_config
        return report_strategy_config

    def __load_converters(self, connector, gateway):
        try:
            if self.config.get(UPLINK_PREFIX + CONVERTER_PARAMETER) is not None:
                converter = TBModuleLoader.import_module(connector.connector_type,
                                                         self.config[UPLINK_PREFIX + CONVERTER_PARAMETER])(self, self._log)
            else:
                converter = BytesModbusUplinkConverter({**self.config, 'deviceName': self.device_name}, self._log)

            if self.config.get(DOWNLINK_PREFIX + CONVERTER_PARAMETER) is not None:
                downlink_converter = TBModuleLoader.import_module(connector.connector_type, self.config[
                    DOWNLINK_PREFIX + CONVERTER_PARAMETER])(self, self._log)
            else:
                downlink_converter = BytesModbusDownlinkConverter(self.config, self._log)

            if self.name not in gateway.get_devices():
                gateway.add_device(self.name, {CONNECTOR_PARAMETER: connector},
                                   device_type=self.config.get(DEVICE_TYPE_PARAMETER))

            self.config[UPLINK_PREFIX + CONVERTER_PARAMETER] = converter
            self.config[DOWNLINK_PREFIX + CONVERTER_PARAMETER] = downlink_converter
        except Exception as e:
            self._log.exception(e)

    def __str__(self):
        return f'{self.device_name}'
