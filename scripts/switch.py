#!/usr/bin/env python3
# encoding: utf-8
"""
Switch on/off or get the status of the heating using a serial TTL relay.

@author:     Simone Rossetto
@copyright:  2015 Simone Rossetto
@license:    GNU General Public License v3
@contact:    simros85@gmail.com
"""

import sys
import json
import logging

from argparse import ArgumentParser
from configparser import ConfigParser
from serial import Serial, SerialException, EIGHTBITS, STOPBITS_ONE, PARITY_NONE
from thermod import config


__version__ = '1.0.0~beta1'
__date__ = '2015-10-02'
__updated__ = '2015-10-05'


# Control commands
#     Bytes Number    1    2    3    4    5    6    7    8
#                     Head      Reserved bytes      Cmd  Checksum
#     Reading status  0x5556    0x00000000          00   0xAB
#     Relay COM-NO    0x5556    0x00000000          01   0xAC
#     Relay COM-NC    0x5556    0x00000000          02   0xAD
#     Relay toggle    0x5556    0x00000000          03   0xAE
#     Relay momentary 0x5556    0x00000000          04   0xAF
#
# Return value
#     Bytes Number    1    2    3    4    5    6    7    8
#                     Head      Reserved bytes      Cmd  Checksum
#     Relay COM-NO-OK 0x333C    0x00000000          01   0x70
#     Relay COM-NC-OK 0x333C    0x00000000          02   0x71
relay_cmd_size = 8
relay_status_cmd = b'\x55\x56\x00\x00\x00\x00\x00\xAB'
relay_com2open_cmd = b'\x55\x56\x00\x00\x00\x00\x01\xAC'
relay_com2open_rsp = b'\x33\x3C\x00\x00\x00\x00\x01\x70'
relay_com2close_cmd = b'\x55\x56\x00\x00\x00\x00\x02\xAD'
relay_com2close_rsp = b'\x33\x3C\x00\x00\x00\x00\x02\x71'


# defult logger for this scripts
logger = logging.getLogger('thermod.switch')


def switch_on(device, timeout=5):
    """Switch on the heating and return 1.
    
    Send the command to the serial TTL relay to connect COM port to NO
    port in order to switch on the heating.
    """
    
    try:
        comunicate(device, relay_com2open_cmd, relay_com2open_rsp, timeout)
    except SerialException as se:
        raise SerialException('cannot switch on the heating: {}'.format(se))
    
    return 1


def switch_off(device, timeout=5):
    """Switch off the heating and return 0.
    
    Send the command to the serial TTL relay to connect COM port to NC
    port in order to switch off the heating.
    """
    
    try:
        comunicate(device, relay_com2close_cmd, relay_com2close_rsp, timeout)
    except SerialException as se:
        raise SerialException('cannot switch off the heating: {}'.format(se))
    
    return 0


def get_status(device, timeout=5):
    """Get the current status of the relay (1=ON, 0=OFF)."""
    
    result = None
    
    try:
        status = comunicate(device, relay_status_cmd, timeout=timeout)
        
        if status == relay_com2open_rsp:
            result = 1
        elif status == relay_com2close_rsp:
            result = 0
        else:
            raise SerialException('the relay returned an unexpected status')
    
    except SerialException as se:
        raise SerialException('cannot get the status: {}'.format(se))
    
    return result


def comunicate(device, command, response=None, timeout=5):
    """Send a command to the relay and return its response message.
    
    If response is provided, it will be compared with the bytes
    returned from the relay, if they are not equal a SerialException
    is raised.
    
    Command and response must be 8 bytes and must be binary strings.
    If the comunication ends abnormally a SerialException is raised
    with the error message.
    """
    
    logger.debug('initializing serial device {}'.format(device))
    
    # Baud rate 9600kbps, 8 data bits, one stop bit, no parity
    serial = Serial(port=device,
                    baudrate=9600,
                    timeout=timeout,  # read timeout in seconds
                    bytesize=EIGHTBITS,
                    stopbits=STOPBITS_ONE,
                    parity=PARITY_NONE)
    
    with serial:
        logger.debug('sending command to relay')
        written = serial.write(command)
        
        if (written != relay_cmd_size):
            logger.debug('number of written bytes ({}) is less than command'
                         'size ({})' .format(written, relay_cmd_size))
            raise SerialException('cannot send command to relay')
        
        logger.debug('command sent')
        
        logger.debug('retriving status message from relay')
        status = serial.read(relay_cmd_size)
        
        if response is not None and (status != response):
            logger.debug('the relay returned an unexpected '
                         'status: {}'.format(status))
            raise SerialException('the relay returned an unexpected status')
        
        logger.debug('message received')
    
    logger.debug('comunication with relay completed')
    return status


def main(argv=None):
    """Main command line.
    
    Parse command line arguments and execute the corresponding function
    in order to switch on/off the heating.
    """
    
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)
    
    prog_version = 'v%s' % __version__
    prog_build_date = str(__updated__)
    prog_version_msg = '%%(prog)s %s (%s)' % (prog_version, prog_build_date)
    prog_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    prog_epilog = 'The exit code is POSIX compliant: 0 on success, 1 on error.'
    
    result = None
    device = None
    status = None
    error = None
    
    parser = ArgumentParser(description=prog_shortdesc, epilog=prog_epilog)
    
    parser_cmd = parser.add_mutually_exclusive_group(required=True)
    parser_cmd.add_argument('--on', action='store_const', const='on', default=False, help='switch on the heating')
    parser_cmd.add_argument('--off', action='store_const', const='off', default=False, help='switch off the heating')
    parser_cmd.add_argument('--status', action='store_true', help='get the status of the heating')
    
    parser.add_argument('-d', '--device', metavar='DEV', action='store', default=None, help='use custom serial device')
    parser.add_argument('-j', '--json', action='store_true', help='output result in json format for thermod daemon')
    parser.add_argument('-s', '--syslog', action='store_true', help='log messages to syslog')
    parser.add_argument('-D', '--debug', action='store_true', help='print debug messages too')
    parser.add_argument('-V', '--version', action='version', version=prog_version_msg)
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    if not args.json or (args.json and args.debug and not args.syslog):
        # log to console only when json output is not choosen
        # or when json and debug but no syslog
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter(fmt=config.logger_fmt_msg,
                                               datefmt=config.logger_fmt_date))
        logger.addHandler(console)
    
    if args.syslog:
        syslog = logging.handlers.SysLogHandler()
        syslog.addFormatter(logging.Formatter(fmt=config.logger_fmt_msg_syslog))
        logger.addHandler(syslog)
    
    logger.debug('reading thermod configuration from files {}'.format(config.main_config_files))
    cfg = ConfigParser()
    _cfg_files_found = cfg.read(config.main_config_files)
    logger.debug('configuration files found: {}'.format(_cfg_files_found))

    # device provided by command line arguments has the precedence
    if ((cfg.has_section('scripts') and cfg.has_option('scripts', 'device'))
            or args.device):
        device = (args.device or cfg['scripts']['device']).strip('"')

    try:
        
        if device is None:
            raise SerialException('device not provided, cannot procede')
        
        if args.on:
            logger.info('switching on the heating')
            status = switch_on(device)
            logger.info('heating switched on')
        
        elif args.off:
            logger.info('switching off the heating')
            status = switch_off(device)
            logger.info('heating switched off')
        
        else:
            logger.info('getting current status of the heating')
            status = get_status(device)
            
            if status == 1:
                _st_str = 'on'
            else:
                _st_str = 'off'
            
            logger.info('the heating is {}'.format(_st_str))
        
        result = 0
    
    except SerialException as se:
        error = str(se)
        
        # do not print critical messages when json output is on and neither
        # debug nor syslog are on because the error is reporte in the json
        # output string
        if not args.json or args.debug or args.syslog:
            logger.critical(se)
        
        result = 1
    
    if args.json:
        logger.debug('printing result as json encoded string')
        print(json.dumps({'success': not result,
                          'status': status,
                          'error': error}))
    
    logger.debug('exiting with return code = {}'.format(result))
    
    return result


if __name__ == "__main__":
    sys.exit(main())