#     Copyright 2021. ThingsBoard
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

from time import sleep
from queue import Queue
from random import choice
from string import ascii_lowercase
from threading import Thread
from ftplib import FTP, FTP_TLS
import io
import simplejson

from thingsboard_gateway.connectors.ftp.path import Path
from thingsboard_gateway.connectors.ftp.file import File
from thingsboard_gateway.tb_utility.tb_utility import TBUtility
from thingsboard_gateway.connectors.ftp.ftp_uplink_converter import FTPUplinkConverter

try:
    from requests import Timeout, request
except ImportError:
    print("Requests library not found - installing...")
    TBUtility.install_package("requests")
    from requests import Timeout, request

from thingsboard_gateway.connectors.connector import Connector, log


class FTPConnector(Connector, Thread):
    def __init__(self, gateway, config, connector_type):
        super().__init__()
        self.statistics = {'MessagesReceived': 0,
                           'MessagesSent': 0}
        self.__log = log
        self.__rpc_requests = []
        self.__config = config
        self.__connector_type = connector_type
        self.__gateway = gateway
        self.security = {**self.__config['security']} if self.__config['security']['type'] == 'basic' else {
            'username': 'anonymous', "password": 'anonymous@'}
        self.__tls_support = self.__config.get("TLSSupport", False)
        self.setName(self.__config.get("name", "".join(choice(ascii_lowercase) for _ in range(5))))
        self.daemon = True
        self.__stopped = False
        self.__requests_in_progress = []
        self.__convert_queue = Queue(1000000)
        self.__attribute_updates = []
        self._connected = False
        self.host = self.__config['host']
        self.port = self.__config.get('port', 21)
        self.__ftp = FTP_TLS if self.__tls_support else FTP
        self.paths = [
            Path(
                path=obj['path'],
                read_mode=obj['readMode'],
                telemetry=obj['timeseries'],
                device_name=obj['devicePatternName'],
                attributes=obj['attributes'],
                txt_file_data_view=obj['txtFileDataView'],
                with_sorting_files=obj.get('with_sorting_files', True),
                poll_period=obj.get('pollPeriod', 60),
                max_size=obj.get('maxFileSize', 5),
                delimiter=obj.get('delimiter', ','),
                device_type=obj.get('devicePatternType', 'Device')
            )
            for obj in self.__config['paths']
        ]

    def open(self):
        self.__stopped = False
        self.start()

    def run(self):
        try:
            with self.__ftp() as ftp:
                self.__connect(ftp)

                for path in self.paths:
                    path.find_files(ftp)

                self.__process_paths(ftp)

                while True:
                    sleep(.01)
                    if self.__stopped:
                        break

        except Exception as e:
            self.__log.exception(e)
            try:
                self.close()
            except Exception as e:
                self.__log.exception(e)
        while True:
            if self.__stopped:
                break

    def __connect(self, ftp):
        try:
            ftp.connect(self.host, self.port)

            if isinstance(ftp, FTP_TLS):
                ftp.sendcmd('USER ' + self.security['username'])
                ftp.sendcmd('PASS ' + self.security['password'])
                ftp.prot_p()
                self.__log.info('Data protection level set to "private"')
            else:
                ftp.login(self.security['username'], self.security['password'])

        except Exception as e:
            self.__log.error(e)
            sleep(10)
        else:
            self._connected = True
            self.__log.info('FTP connected')

    def __process_paths(self, ftp):
        # TODO: call path on timer
        for path in self.paths:
            configuration = path.config
            converter = FTPUplinkConverter(configuration)
            # TODO: check if to rescan path
            for file in path.files:
                current_hash = file.get_current_hash(ftp)
                if ((file.has_hash() and current_hash != file.hash) or not file.has_hash()) and file.check_size_limit(
                        ftp):
                    file.set_new_hash(current_hash)

                    handle_stream = io.BytesIO()

                    ftp.retrbinary('RETR ' + file.path_to_file, handle_stream.write)

                    handled_str = str(handle_stream.getvalue(), 'UTF-8')
                    handled_array = handled_str.split('\n')

                    convert_conf = {'file_ext': file.path_to_file.split('.')[-1]}

                    if convert_conf['file_ext'] == 'json':
                        json_data = simplejson.loads(handled_str)
                        if isinstance(json_data, list):
                            for obj in json_data:
                                converted_data = converter.convert(convert_conf, obj)
                                self.__gateway.send_to_storage(self.getName(), converted_data)
                                self.statistics['MessagesSent'] = self.statistics['MessagesSent'] + 1
                                log.debug("Data to ThingsBoard: %s", converted_data)
                        else:
                            converted_data = converter.convert(convert_conf, json_data)
                            self.__gateway.send_to_storage(self.getName(), converted_data)
                            self.statistics['MessagesSent'] = self.statistics['MessagesSent'] + 1
                            log.debug("Data to ThingsBoard: %s", converted_data)
                    else:
                        cursor = file.cursor or 0

                        for (index, line) in enumerate(handled_array):
                            if index == 0 and not path.txt_file_data_view == 'SLICED':
                                convert_conf['headers'] = line.split(path.delimiter)
                            else:
                                if file.read_mode == File.ReadMode.PARTIAL and index >= cursor:
                                    converted_data = converter.convert(convert_conf, line)
                                    if index + 1 == len(handled_array):
                                        file.cursor = index
                                else:
                                    converted_data = converter.convert(convert_conf, line)

                                self.__gateway.send_to_storage(self.getName(), converted_data)
                                self.statistics['MessagesSent'] = self.statistics['MessagesSent'] + 1
                                log.debug("Data to ThingsBoard: %s", converted_data)

                    handle_stream.close()

    def close(self):
        self.__stopped = True

    def get_name(self):
        return self.name

    def is_connected(self):
        return self._connected

    def on_attributes_update(self, content):
        pass

    def server_side_rpc_handler(self, content):
        pass
