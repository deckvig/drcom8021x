#coding=utf-8
""" EAP authentication handler

This module sents EAPOL begin/logoff packet
and parses received EAP packet 

"""

__all__ = ["EAPAuth"]

import socket
import os, sys
from subprocess import call
import hashlib
from struct import pack, unpack
from binascii import hexlify
import multiprocessing
from colorama import Fore, Style, init
# init() # required in Windows
from eappacket import *

def display_prompt(color, string):
    prompt = color + Style.BRIGHT + '==> ' + Style.RESET_ALL
    prompt += Style.BRIGHT + string + Style.RESET_ALL
    print prompt

def display_packet(packet, header=""):
    print '%s Packet info: ' % header
    print '\tFrom: ' + hexlify(packet[0:6])
    print '\tTo: ' + hexlify(packet[6:12])
    print '\tType: ' + hexlify(packet[12:14])
    print '\tContent: ' + hexlify(packet[14:])

class EAPAuth:

    def __init__(self, login_info, success_handler = None, success_callback_args=(,)):
        # bind the h3c client to the EAP protocal
        self.client = socket.socket(
            socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE_PAE))
        self.client.bind((login_info['ethernet_interface'], ETHERTYPE_PAE))
        

        # get local ethernet card address
        self.mac_addr = self.client.getsockname()[4]
        
        self.mac_addr = '\x12\x34\x56\x78\xab\xaa'
        self.ethernet_header = get_ethernet_header(
            self.mac_addr, PAE_GROUP_ADDR, ETHERTYPE_PAE)
        self.has_sent_logoff = False
        self.login_info = login_info
        self.success_callback = success_handler
        self.success_callback_args = success_callback_args

    def send_start(self):
        # sent eapol start packet
        eap_start_packet = fill_bytes(self.ethernet_header + get_EAPOL(EAPOL_START))
        display_packet(eap_start_packet, "Start")
        self.client.send(eap_start_packet)

        display_prompt(Fore.GREEN, 'Sending EAPOL start')

    def send_logoff(self):
        # sent eapol logoff packet
        eap_logoff_packet = self.ethernet_header + get_EAPOL(EAPOL_LOGOFF)
        display_packet(eap_logoff_packet, "Logoff")
        self.client.send(eap_logoff_packet)
        self.has_sent_logoff = True

        display_prompt(Fore.GREEN, 'Sending EAPOL logoff')

    def send_response_id(self, packet_id):
        eap_response_id_packet = self.ethernet_header + \
                                 get_EAPOL(EAPOL_EAPPACKET,
                                    get_EAP(EAP_RESPONSE,
                                           packet_id,
                                           EAP_TYPE_ID,
                                           get_identity_data(self.login_info)))
        display_packet(eap_response_id_packet, "Response_ID")                                   
        self.client.send(eap_response_id_packet)


    def send_response_md5(self, packet_id, md5data):
        password = self.login_info['password']
        username = self.login_info['username']
        eap_md5 = hashlib.md5(chr(packet_id) + password + md5data).digest()
        md5_length = '\x10' # md5_value_size = 16
        
        resp = md5_length + eap_md5 + username
        # resp = chr(len(chap)) + ''.join(chap) + self.login_info['username']
        eap_packet = fill_bytes(self.ethernet_header + \
                                get_EAPOL(EAPOL_EAPPACKET, get_EAP(
                                EAP_RESPONSE, packet_id, EAP_TYPE_MD5, resp)))
        
        display_packet(eap_packet, "Response_MD5")  
        
        try:
            self.client.send(eap_packet)
        except socket.error, msg:
            print "Connection error!"
            exit(-1)

    def display_login_message(self, msg):
        """
            display the messages received form the radius server,
            including the error meaasge after logging failed or
            other meaasge from networking centre
        """
        try:
            print msg.decode('gbk')
        except UnicodeDecodeError:
            print msg

    def EAP_handler(self, eap_packet):
        vers, type, eapol_len = unpack("!BBH", eap_packet[:4])
        if type != EAPOL_EAPPACKET:
            display_prompt(Fore.YELLOW, 'Got unknown EAPOL type %i' % type)

        # EAPOL_EAPPACKET type
        code, id, eap_len = unpack("!BBH", eap_packet[4:8])
        if code == EAP_SUCCESS:
            display_prompt(Fore.YELLOW, 'Got EAP Success')

            if self.login_info['dhcp_command']:
                # 脚本只做测试用， 暂时不获取ip
                # display_prompt(Fore.YELLOW, 'Obtaining IP Address:')
                # call([self.login_info['dhcp_command'], self.login_info['ethernet_interface']])
                display_prompt(Fore.GREEN, '802.1X Login successfully')
                if self.success_callback:
                    multiprocessing.Process(target=self.success_callback,
                                            args=self.success_callback_args).start()

        elif code == EAP_FAILURE:
            if (self.has_sent_logoff):
                display_prompt(Fore.YELLOW, 'Logoff Successfully!')

                #self.display_login_message(eap_packet[10:])
            else:
                display_prompt(Fore.YELLOW, 'Got EAP Failure')

                #self.display_login_message(eap_packet[10:])
            exit(-1)

        elif code == EAP_RESPONSE:
            display_prompt(Fore.YELLOW, 'Got Unknown EAP Response')

        elif code == EAP_REQUEST:
            reqtype = unpack("!B", eap_packet[8:9])[0]
            reqdata = eap_packet[9:4 + eap_len]

            # type
            if reqtype == EAP_TYPE_ID:
                display_prompt(Fore.YELLOW, 'Got EAP Request for identity')
                self.send_response_id(id)
                display_prompt(Fore.GREEN,
                               'Sending EAP response with identity = [%s]'
                               % self.login_info['username'])

            elif reqtype == EAP_TYPE_H3C:
                display_prompt(Fore.YELLOW, 'Got EAP Request for Allocation')
                self.send_response_h3c(id)
                display_prompt(Fore.GREEN, 'Sending EAP response with password')

            elif reqtype == EAP_TYPE_MD5:
                data_len = unpack("!B", reqdata[0:1])[0]
                md5data = reqdata[1:1 + data_len]
                display_prompt(Fore.YELLOW, 'Got EAP Request for MD5-Challenge')
                self.send_response_md5(id, md5data)
                display_prompt(Fore.GREEN, 'Sending EAP response with password')

            else:
                display_prompt(Fore.YELLOW, 'Got unknown Request type (%i)' % reqtype)

        elif code == 10 and id == 5:
            self.display_login_message(eap_packet[12:])
        else:
            display_prompt(Fore.YELLOW, 'Got unknown EAP code (%i)' % code)

    def serve_forever(self):
        try:
            self.send_start()
            while True:
                # 根据一份样本似乎是 15s 认证一次，但是样本没有发送密码
                eap_packet = self.client.recv(1600)

                # strip the ethernet_header and handle
                self.EAP_handler(eap_packet[14:])

        except KeyboardInterrupt:
            print Fore.RED + Style.BRIGHT + 'Interrupted by user' + Style.RESET_ALL
            self.send_logoff()

        except socket.error, msg:
            print "Connection error: %s" % msg
            exit(-1)
