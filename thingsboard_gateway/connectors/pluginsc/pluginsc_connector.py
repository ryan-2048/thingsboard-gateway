from threading import Thread
from random import choice
from string import ascii_lowercase
from time import sleep

from thingsboard_gateway.connectors.pluginsc.pluginsc_lib import *

from thingsboard_gateway.connectors.connector import Connector, log
from thingsboard_gateway.connectors.pluginsc.pluginsc_uplink_converter import PluginscUplinkConverter
from thingsboard_gateway.connectors.pluginsc.pluginsc_downlink_converter import PluginscDownlinkConverter


class PluginscConnector(Connector, Thread):
    def __init__(self, gateway, config, connector_type):
        super().__init__()
        self.statistics = {'MessagesReceived': 0, 'MessagesSent': 0}
        self.__config = config
        self._connector_type = connector_type
        self.__gateway = gateway
        self.setName(self.__config.get("name", "".join(choice(ascii_lowercase) for _ in range(5))))
        self.daemon = True
        self.__connected = False
        self.__stopped = False

        self.__uplink_converter = PluginscUplinkConverter(self.__config)
        self.__downlink_converter = PluginscDownlinkConverter(self.__config)

        self.monitor = LgProtocolMonitor_create(self.__config.get("protocolName"), self.__config.get("cfgFileName"))
        self.p_connectionHandler = LgProtocolMonitor_ConnectionHandler(self.__connectionHandler)
        self.p_messageHandler = LgProtocolMonitor_MessageHandler(self.__messageHandler)
        LgProtocolMonitor_setConnectionHandler(self.monitor, self.p_connectionHandler)
        LgProtocolMonitor_setMessageHandler(self.monitor, self.p_messageHandler)
        

    def run(self):
        while not self.__stopped:
            if (LgProtocolMonitor_start(self.monitor)):
                break
            else:
                sleep(5)
        
    def close(self):
        self.__stopped = True
        LgProtocolMonitor_close(self.monitor)
        LgProtocolMonitor_destroy(self.monitor)

    def on_attributes_update(self, content):
        try:
            log.debug(content)
            for key, value in content.get("data").items():
                LgProtocolMonitor_control(self.monitor, self.__downlink_converter.convert(value))
        except Exception as e:
            log.exception(e)

    def server_side_rpc_handler(self, content):
        try:
            log.debug(content)
        except Exception as e:
            log.exception(e)

    def open(self):
        self.__stopped = False
        self.start()

    def get_name(self):
        return self.name

    def is_connected(self):
        return self.__connected
    
    def get_config(self):
        return self.__config
    
    def __connectionHandler (self, msg):
        pass
    
    def __messageHandler (self, msg):
        self.__convert_data(msg)
    
    def __convert_data(self, data):
        data_to_send = self.__uplink_converter.convert(data)
        log.debug(data_to_send)
        if data_to_send is not None:
            self.__gateway.send_to_storage(self.get_name(), data_to_send)
