import logging
import threading
import time
import serial
from enum import IntEnum
import random
import queue

q = queue.Queue(maxsize = 3)
serial_lock = threading.Lock()
queue_lock = threading.Lock()

# Response mechanism
class ATResp(IntEnum):
    ErrorNoResponse=-1
    ErrorDifferentResponse=0
    OK=1

# Define serial port config
serial_port = serial.Serial(
    port="/dev/ttyUSB0",
    baudrate=9600
)
time.sleep(1)

# Unncessary Bluffer cleanup
serial_port.reset_output_buffer()
serial_port.reset_input_buffer()

# This subroutine was blatantly copied from someone. Will add credits when I get ahold of the repo and the person made it.
def sendATCmdWaitReturnResp(cmd, response, timeout=.5, interByteTimeout=.1):
        """
        This function is designed to return data and check for a final response, e.g. 'OK'
        """
        serial_lock.acquire() 
        print("Send AT Command: {}".format(cmd))
        serial_port.timeout=timeout
        serial_port.inter_byte_timeout=interByteTimeout

        serial_port.write(cmd.encode('utf-8')+b'\r')
        serial_port.flush()
        lines=serial_port.readlines()
        for n in range(len(lines)):
            try: lines[n]=lines[n].decode('utf-8').strip()
            except UnicodeDecodeError: lines[n]=lines[n].decode('latin1').strip()

        lines=[l for l in lines if len(l) and not l.isspace()]
        print("Lines: {}".format(lines))

        if not len(lines):
            serial_lock.release() 
            return (ATResp.ErrorNoResponse, None)
    
        _response=lines.pop(-1)
        print("Response: {}".format(_response))
        if not len(_response) or _response.isspace(): 
            serial_lock.release() 
            return (ATResp.ErrorNoResponse, None)
        elif response==_response: 
            serial_lock.release() 
            return (ATResp.OK, lines)
        serial_lock.release() 
        return (ATResp.ErrorDifferentResponse, None)
        
# Start and setup the GSM module
# TODO: Description for each AT command
#       Move the AT commands to MACROS?
def gsm_start():
    sendATCmdWaitReturnResp("ATE0", "OK")
    sendATCmdWaitReturnResp("AT+CPIN?", "READY")
    sendATCmdWaitReturnResp("AT+CIPSPRT=0", "OK")
    sendATCmdWaitReturnResp("AT+CGCLASS?", "OK")

# Setting up the GPRS for HTTP Stack iniliatizwation
# If not done, the HTTP Stack of the GSM module wont work properly.
def gsm_gprs_setup(apn, user, pwd):
    at_cmd_1 = "AT+CSTT="
    at_cmd_1 = at_cmd_1 + "\""+apn+"\""+","+"\""+user+"\""+","+"\""+pwd+"\""
       
    sendATCmdWaitReturnResp("AT+CREG?", "OK")
    sendATCmdWaitReturnResp(at_cmd_1, "OK")
    sendATCmdWaitReturnResp("AT+CGDCONT=1,\"IP\",\""+apn+"\"","OK")
    time.sleep(3)
    sendATCmdWaitReturnResp("AT+CGATT=1", "OK")
    sendATCmdWaitReturnResp("AT+CGACT=1", "OK",timeout=5)

# If you want to go with all the pain of using TCP. use this subroutine
###################################################################
#def startTCP(server):
#    sendATCmdWaitReturnResp("AT+CIPMUX=0", "OK")
#    sendATCmdWaitReturnResp("AT+CIPTKA=1","ERROR")
#    sendATCmdWaitReturnResp("AT+CIPSTART=\"TCP\",\"<YOUR API URL>",\"<PORT> (80)\"", "CONNECTED", timeout=3)
#    sendATCmdWaitReturnResp("AT+CIPSTART=\"TCP\",\"<IP OF YOUR SERVER>\",\"<PORT (80)>\"", "CONNECTED", timeout=3)
#    sendATCmdWaitReturnResp("AT+CIPSTATUS", "CONNECT OK")
#    sendATCmdWaitReturnResp("AT+CIPSEND", ">", timeout=2)
#    sendATCmdWaitReturnResp("GET /gsmtest", "");
#    sendATCmdWaitReturnResp(chr(26), "OK")
#    sendATCmdWaitReturnResp("AT+CIPSHUT", "OK")
####################################################################

# Send whatever data in the queue
# We use the built in HTTP Stack of the GSM module, less hassle.
def gsm_send_data():
    sendATCmdWaitReturnResp("AT+SAPBR=2,1", "OK")
    sendATCmdWaitReturnResp("AT+SAPBR=1,1", "OK")
    sendATCmdWaitReturnResp("AT+HTTPINIT", "OK")

    while True:
        if q.full():
            print("IN TRUE FULL")
            queue_lock.acquire()
            count = str(q.get())
            temp = str(q.get())
            humidity = str(q.get())
            
            # Here we have a HTTP API to which we append the sensor values and then hit it using HTTPACTION AT command
            sendATCmdWaitReturnResp("AT+HTTPPARA=\"URL\",\"<HERE COMES YOUR HTTP API URL>"+count+"&temp="+temp+"&humidity="+humidity+"\"", "OK")
            sendATCmdWaitReturnResp("AT+HTTPPARA=\"CID\",1","OK")
            sendATCmdWaitReturnResp("AT+HTTPACTION=0","OK")
            sendATCmdWaitReturnResp("\r\n","", timeout=7)
            queue_lock.release() 

# Random Data generation for testing the GPRS conn
def gsm_data_generator():
    while True:
        print("IN GEN")
        randTime = random.randint(1,9)
        print(randTime)
        time.sleep(randTime)
        queue_lock.acquire()
        if not q.full():
            val = random.randint(35,84)
            q.put(val)
        queue_lock.release();


if __name__ == "__main__":
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")
    
    # lock = threading.Lock()
    # Starting the gsm module initialization thread
    gsm_start = threading.Thread(target=gsm_start)
    gsm_start.start()

    # Starting the GPRS setup thread
    gsm_gprs_setup = threading.Thread(target=gsm_gprs_setup, args=("airtelgprs.com","",""))
    gsm_gprs_setup.start()
    
    time.sleep(26)
    
    # Starting the data generation thread
    data_generator = threading.Thread(target=gsm_data_generator, args=())
    data_generator.start()
    
    # time.sleep(2)
    # Starting the data sending thread
    gsm_send_data = threading.Thread(target=gsm_send_data, args=())
    gsm_send_data.start()
    
    # data_generator = threading.Thread(target=gsm_data_generator, args=())
    # data_generator.start()
