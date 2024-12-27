from threading import Thread
from random import choice
from string import ascii_lowercase
from time import sleep, time

from thingsboard_gateway.connectors.iec104.lib60870 import *

from thingsboard_gateway.connectors.connector import Connector
from thingsboard_gateway.connectors.iec104.iec104_uplink_converter import Iec104UplinkConverter
from thingsboard_gateway.connectors.iec104.iec104_downlink_converter import Iec104DownlinkConverter
from thingsboard_gateway.tb_utility.tb_logger import init_logger


class Iec104Connector(Connector, Thread):
    def __init__(self, gateway, config, connector_type):
        super().__init__()
        self.statistics = {'MessagesReceived': 0, 'MessagesSent': 0}
        self.__config = config
        self._connector_type = connector_type
        self.__gateway = gateway
        self.__log = init_logger(self.__gateway, config.get('name', self.name),
                                 config.get('logLevel', 'INFO'),
                                 enable_remote_logging=config.get('enableRemoteLogging', False))
        self.setName(self.__config.get("name", "".join(choice(ascii_lowercase) for _ in range(5))))
        self.__id = self.__config.get('id')
        self.daemon = True
        self.__connected = False
        self.__stopped = False
        
        self.__startDtConReceived = False
        self.__firstCall = True
        self.__firstCallKwh = True
        self.__giTerm = True
        self.__giTimestamp = time()
        self.__callTimestamp = time()
        self.__callKwhTimestamp = time()

        self.__uplink_converter = Iec104UplinkConverter(self.__config, self.__log)
        self.__downlink_converter = Iec104DownlinkConverter(self.__config, self.__log)
        
        self.__con = CS104_Connection_create(self.__config["host"], self.__config["port"])
        self.__p_connectionHandler = CS104_ConnectionHandler(self.__connectionHandler)
        self.__p_asduReceivedHandler = CS101_ASDUReceivedHandler(self.__asduReceivedHandler)
        CS104_Connection_setConnectionHandler(self.__con, self.__p_connectionHandler, None)
        CS104_Connection_setASDUReceivedHandler(self.__con, self.__p_asduReceivedHandler, None)

        if self.__config["rawMessage"]:
          self.__p_rawMessageHandler = IEC60870_RawMessageHandler(self.__rawMessageHandler)
          CS104_Connection_setRawMessageHandler(self.__con, self.__p_rawMessageHandler, None)

    def run(self):    
        while not self.__stopped:
            if self.__connected == False:
                self.__connect_to_device()
			
            if self.__connected:
                if self.__startDtConReceived == False:
                    CS104_Connection_sendStartDT(self.__con)
            
            if self.__startDtConReceived:
                now_time = time()

                if self.__giTerm:
                    if self.__firstCall:
                        self.__firstCall = False
                        self.__callTimestamp = now_time
                        CS104_Connection_sendInterrogationCommand(self.__con, CS101_COT_ACTIVATION, 1, IEC60870_QOI_STATION)
                        self.__giTerm = False
                        self.__giTimestamp = now_time	
                    elif (self.__config["scanPeriod"] > 0):
                        if((now_time - self.__callTimestamp) > self.__config["scanPeriod"]):
                            self.__callTimestamp = now_time
                            CS104_Connection_sendInterrogationCommand(self.__con, CS101_COT_ACTIVATION, 1, IEC60870_QOI_STATION)
                            self.__giTerm = False
                            self.__giTimestamp = now_time
					
                if self.__giTerm:
                    if self.__config["scanKwhPeriod"] > 0:
                        if self.__firstCallKwh:	
                            self.__firstCallKwh = False
                            self.__callKwhTimestamp = now_time
                            CS104_Connection_sendCounterInterrogationCommand(self.__con, CS101_COT_ACTIVATION, 1, IEC60870_QOI_STATION)
                            self.__giTerm = False
                            self.__giTimestamp = now_time
                        elif((now_time - self.__callKwhTimestamp) > self.__config["scanKwhPeriod"]):
                            self.__callKwhTimestamp = now_time
                            CS104_Connection_sendCounterInterrogationCommand(self.__con, CS101_COT_ACTIVATION, 1, IEC60870_QOI_STATION)
                            self.__giTerm = False
                            self.__giTimestamp = now_time

                if self.__giTerm == False:
                    if((now_time - self.__giTimestamp) > 15):
                        self.__giTerm = True
            sleep(1)
                
            
    def close(self):
        self.__stopped = True
        CS104_Connection_sendStopDT(self.__con)
        CS104_Connection_destroy(self.__con)

    def on_attributes_update(self, content):
        try:
            for attribute_request in self.__config.get("attributeUpdates", []):
                for attribute_updated in content['data']:
                    if attribute_request['tag'] == attribute_updated:
                        if C_SC_NA_1 == attribute_request['cmd']:
                            # 单指令(BOOLEAN)
                            sc = cast(SingleCommand_create(None, attribute_request['ioa'], content['data'][attribute_updated] == 1, False, 0), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                        elif C_DC_NA_1 == attribute_request['cmd']:
                            # 双指令(ON/OFF/transient)
                            sc = cast(DoubleCommand_create(None, attribute_request['ioa'], content['data'][attribute_updated], False, 0), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                        elif C_SE_NC_1 == attribute_request['cmd']:
                            # 设定值命令 短值(FLOAT32)
                            sc = cast(SetpointCommandShort_create(None, attribute_request['ioa'], content['data'][attribute_updated], False, 0), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                        elif C_SE_NA_1 == attribute_request['cmd']:
                             # 设定值指令 归一化值(-1.0…+1.0)
                            sc = cast(SetpointCommandNormalized_create(None, attribute_request['ioa'], content['data'][attribute_updated], False, 0), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                        elif C_SE_NB_1 == attribute_request['cmd']:
                             # 设定值命令 标定值(-32768…+32767)
                            sc = cast(SetpointCommandScaled_create(None, attribute_request['ioa'], content['data'][attribute_updated], False, 0), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                        elif C_DC_TA_1 == attribute_request['cmd']:
                             # 使用 CP56Time2a 的双重命令（开/关/瞬态）
                            newTime = sCP56Time2a()
                            CP56Time2a_createFromMsTimestamp(CP56Time2a(newTime), Hal_getTimeInMs())
                            sc = cast(DoubleCommandWithCP56Time2a_create(None, attribute_request['ioa'], content['data'][attribute_updated], False, 0, CP56Time2a(newTime)), InformationObject)
                            CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                            InformationObject_destroy(sc)
                            
        except Exception as e:
            self.__log.exception(e)

    def server_side_rpc_handler(self, content):
        try:
            for rpc_request in self.__config.get("serverSideRpc", []):
                if rpc_request['tag'] == content["data"]["method"]:
                    if C_SC_NA_1 == rpc_request['cmd']:
                        # 单指令(BOOLEAN)
                        sc = cast(SingleCommand_create(None, rpc_request['ioa'], content['data']['params']['value'] == 1, False, 0), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
                    elif C_DC_NA_1 == rpc_request['cmd']:
                        # 双指令(ON/OFF/transient)
                        sc = cast(DoubleCommand_create(None, rpc_request['ioa'], content['data']['params']['value'], False, 0), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
                    elif C_SE_NC_1 == rpc_request['cmd']:
                        # 设定值命令 短值(FLOAT32)
                        sc = cast(SetpointCommandShort_create(None, rpc_request['ioa'], content['data']['params']['value'], IEC60870_QUALITY_GOOD), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
                    elif C_SE_NA_1 == rpc_request['cmd']:
                          # 设定值指令 归一化值(-1.0…+1.0)
                        sc = cast(SetpointCommandNormalized_create(None, rpc_request['ioa'], content['data']['params']['value'], False, 0), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
                    elif C_SE_NB_1 == rpc_request['cmd']:
                          # 设定值命令 标定值(-32768…+32767)
                        sc = cast(SetpointCommandScaled_create(None, rpc_request['ioa'], content['data']['params']['value'], False, 0), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
                    elif C_DC_TA_1 == rpc_request['cmd']:
                          # 使用 CP56Time2a 的双重命令（开/关/瞬态）
                        newTime = sCP56Time2a()
                        CP56Time2a_createFromMsTimestamp(CP56Time2a(newTime), Hal_getTimeInMs())
                        sc = cast(DoubleCommandWithCP56Time2a_create(None, rpc_request['ioa'], content['data']['params']['value'], False, 0, CP56Time2a(newTime)), InformationObject)
                        CS104_Connection_sendProcessCommandEx(self.__con, CS101_COT_ACTIVATION, 1, sc)
                        InformationObject_destroy(sc)
        except Exception as e:
            self.__log.exception(e)

    def open(self):
        self.__stopped = False
        self.start()

    def get_type(self):
        return self._connector_type
    
    def get_id(self):
        return self.__id
    
    def is_stopped(self):
        return self.__stopped
 
    def get_name(self):
        return self.name

    def is_connected(self):
        return self.__connected
    
    def get_config(self):
        return self.__config
    
    def __connectionHandler (self, parameter, connection, event):
        if not self.__stopped:
            if event == CS104_CONNECTION_OPENED:
                self.__log.debug("Connection established")
                self.__connected = True
                self.__startDtConReceived = False
            elif event == CS104_CONNECTION_CLOSED:
                self.__log.debug("Connection closed")
                self.__connected = False
                self.__startDtConReceived = False
            elif event == CS104_CONNECTION_STARTDT_CON_RECEIVED:
                self.__log.debug("Received STARTDT_CON")
                self.__startDtConReceived = True
                self.__firstCall = True
                self.__firstCallKwh = True
                self.__giTerm = True
            elif event == CS104_CONNECTION_STOPDT_CON_RECEIVED:
                self.__log.debug("Received STOPDT_CON")

    def __asduReceivedHandler (self, parameter, address, asdu):
        self.__log.debug("RECVD ASDU type: %s(%i) elements: %i" % (
                TypeID_toString(CS101_ASDU_getTypeID(asdu)),
                CS101_ASDU_getTypeID(asdu),
                CS101_ASDU_getNumberOfElements(asdu)))
        data_to_convert = {}
        if (CS101_ASDU_getTypeID(asdu) == M_SP_NA_1):
            # 遥信 单点信息(BOOLEAN)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), SinglePointInformation)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = 1 if SinglePointInformation_getValue(cast(io,SinglePointInformation)) else 0
                SinglePointInformation_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == M_DP_NA_1):
            # 遥信 双点信息(ON/OFF/transient)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), DoublePointInformation)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = DoublePointInformation_getValue(cast(io,DoublePointInformation))
                DoublePointInformation_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == M_ME_NA_1):
            # 遥测 归一化测量值(-1.0...+1.0)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), MeasuredValueScaled)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = MeasuredValueScaled_getValue(cast(io,MeasuredValueScaled))
                MeasuredValueScaled_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == M_ME_NB_1):
            # 遥测 换算后的测量值(-32768...+32767)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), MeasuredValueScaled)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = MeasuredValueScaled_getValue(cast(io,MeasuredValueScaled))
                MeasuredValueScaled_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == M_ME_NC_1):
            # 遥测 短测量值(FLOAT32)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), MeasuredValueShort)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = MeasuredValueShort_getValue(cast(io,MeasuredValueShort))
                MeasuredValueShort_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == M_IT_NA_1):
            # 电度 综合总计(带质量指标的INT32)
            for i in range(CS101_ASDU_getNumberOfElements(asdu)):
                io = cast(CS101_ASDU_getElement(asdu, i), IntegratedTotals)
                data_to_convert[InformationObject_getObjectAddress(cast(io,InformationObject))] = BinaryCounterReading_getValue(IntegratedTotals_getBCR(cast(io,IntegratedTotals)))
                IntegratedTotals_destroy(io)
        elif (CS101_ASDU_getTypeID(asdu) == C_IC_NA_1):
			# 总召
            if (CS101_ASDU_getCOT(asdu) == CS101_COT_ACTIVATION_TERMINATION):
                self.__giTerm = True
        elif (CS101_ASDU_getTypeID(asdu) == C_CI_NA_1):
			# 总召电度
            if (CS101_ASDU_getCOT(asdu) == CS101_COT_ACTIVATION_TERMINATION):
                self.__giTerm = True
        else:
            self.__log.debug("===========================msg not support===========================")
            self.__log.debug("RECVD ASDU type: %s(%i) elements: %i" % (
                TypeID_toString(CS101_ASDU_getTypeID(asdu)),
                CS101_ASDU_getTypeID(asdu),
                CS101_ASDU_getNumberOfElements(asdu)))

        if len(data_to_convert.keys()) > 0:
            self.__convert_data(data_to_convert)
        return True
    
    def __rawMessageHandler (self, parameter, msg, msgSize, sent):
        if sent:
            self.__log.debug("SEND: ");
        else:
            self.__log.debug("RCVD: ");
        
        msgStr = "";
        for i in range(0, msgSize):
            msgStr = msgStr + str(hex(eval(str(msg[i])))) + " "
        
        self.__log.debug(msgStr);
    
    def __connect_to_device (self):
        while not self.__stopped:
            connectRes = None
            if self.__config["type"] == 'client':
                connectRes = CS104_Connection_connect(self.__con)
            elif self.__config["type"] == 'server':
                connectRes = CS104_Connection_accept(self.__con)
            if (connectRes):
                self.__log.debug("__connect_to_device success")
                break
            else:
                self.__log.debug("__connect_to_device fail")
                sleep(3)
    
    def __convert_data(self, data):
        data_to_send = self.__uplink_converter.convert(data)
        if data_to_send is not None:
            res = self.__gateway.send_to_storage(self.get_name(), self.get_id(), data_to_send)
            self.__log.debug(data_to_send)
            self.__log.debug(res)