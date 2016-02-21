"""Control socket to manage thermod from external applications."""

import cgi
import sys
import json
import logging
import time
from threading import Thread
from jsonschema import ValidationError
#from json.decoder import JSONDecodeError
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# backward compatibility for Python 3.4 (TODO check for better handling)
if sys.version[0:3] >= '3.5':
    from json.decoder import JSONDecodeError
else:
    JSONDecodeError = ValueError

from . import config
from .config import JsonValueError
from .timetable import TimeTable

# FIXME si può verificare un problema se viene modificato il timetable sul
# filesystem senza eseguire un reload, poi qualcuno via socket tenta di aggiornare
# le impostazioni e questo aggiornamento va male, vengono ricaricate le
# impostazioni del file che però nel frattempo era stato aggiornato.
# Per evitare questo problema è necessario salvarsi le impostazioni prima
# di aggiornare e in caso di errore risettare le impostazioni salvate.

# TODO migliorare i log del socket

__updated__ = '2016-02-20'
__version__ = '0.4'

logger = logging.getLogger((__name__ == '__main__' and 'thermod') or __name__)


req_settings_all = 'settings'
req_settings_days = 'days'
req_settings_status = config.json_status
req_settings_t0 = config.json_t0_str
req_settings_tmin = config.json_tmin_str
req_settings_tmax = config.json_tmax_str
req_settings_differential = config.json_differential
req_settings_grace_time = config.json_grace_time

req_heating_status = 'status'
req_heating_temperature = 'temperature'
req_heating_target_temp = 'target'

req_path_settings = ('settings', 'set')
req_path_heating = ('heating', 'heat')

rsp_error = 'error'
rsp_message = 'message'
rsp_fullmsg = 'explain'


class ControlThread(Thread):
    """Start a HTTP server ready to receive commands."""
    
    def __init__(self, timetable, host='localhost', port=4344):
        logger.debug('initializing ControlThread')
        super().__init__(name='ThermodControlThread')
        self.server = ControlServer(timetable, (host, port), ControlRequestHandler)
    
    def __repr__(self):
        return "{module}.{cls}({timetable!r}, '{host}', {port:d})".format(
                    module=self.__module__,
                    cls=self.__class__.__name__,
                    timetable=self.server.timetable,
                    host=self.server.server_address[0],
                    port=self.server.server_address[1])
    
    def run(self):
        (host, port) = self.server.server_address
        logger.info('control socket listening on {}:{}'.format(host, port))
        self.server.serve_forever()
    
    def stop(self):
        # TODO scrivere documentazione
        self.server.shutdown()
        logger.info('control socket halted')


class ControlServer(HTTPServer):
    """Receive HTTP connections and dispatch a reequest handler."""
    
    def __init__(self, timetable, server_address, RequestHandlerClass):
        logger.debug('initializing ControlServer')
        super().__init__(server_address, RequestHandlerClass)
        
        if not isinstance(timetable, TimeTable):
            raise TypeError('ControlServer requires a TimeTable object')
        
        self.timetable = timetable
        logger.debug('ControlServer initialized on {}'.format(self.server_address))
    
    def shutdown(self):
        logger.debug('shutting down ControlServer {}'.format(self.server_address))
        super().shutdown()


class ControlRequestHandler(BaseHTTPRequestHandler):
    """Receive and manages control commands."""
    
    BaseHTTPRequestHandler.server_version = 'Thermod/{}'.format(__version__)
    
    def finish(self):
        """Execute the base-class `finish()` method and log a message."""
        super().finish()
        logger.debug('{} connection closed'.format(self.client_address))
    
    @property
    def pathlist(self):
        """Return the full path splitted in a list of lowered case subpath.
        
        If the requested path is '/settings/STATUS/auto' this method returns
        a list containing: 'settings', 'status' and 'auto'.
        """
        rpath = urlparse(self.path)
        return rpath.path.lower().strip('/').split('/')
    
    def _send_header(self, code, message=None, data=None, last_modified=None):
        """Send default response header.
        
        If `data` is a dictonary it will be converted to JSON, if it is a
        string it will be JSON-checked and encoded in UTF-8, if it is already
        encoded in UTF-8 it is JSON-checked and sent as is.
        
        @param code is the status code of the HTTP response
        @param message is the message sent with the status code
        @param data is the data to be sent (dictonary or JSON string)
        @param last_modified is the timestamp of last modification of data
        
        @return the JSON-encoded byte-string to be sent
        """
        
        self.send_response_only(code, message)
        json_data = None
        
        if data:
            if isinstance(data, dict):
                json_data = json.dumps(data).encode('utf-8')
            else:
                if isinstance(data, str):
                    try:
                        json.loads(data)
                    except:
                        raise TypeError('the provided string is not in JSON format')
                    
                    json_data = data.encode('utf-8')
                
                elif isinstance(data, bytes):
                    try:
                        json.loads(data.decode('utf-8'))
                    except:
                        raise TypeError('the provided byte-string is not in JSON format')
                    
                    json_data = data
                
                else:
                    raise TypeError('the provided data is not valid for JSON format')
            
            self.send_header('Content-Type', 'application/json;charset=utf-8')
            self.send_header('Content-Length', len(json_data))
            self.send_header('Last-Modified', self.date_time_string(last_modified or time.time()))
        
        self.send_header('Connection', 'close')
        self.send_header('Server', self.version_string())
        self.send_header('Date', self.date_time_string())
        
        return json_data
    
    def do_HEAD(self):
        """Send the HTTP header equal to the one of the GET request.
        
        Returns the byte-string to be sent in HTTP response body if the request
        is a GET and not simply a HEAD.
        """
        
        logger.info('{} received "{} {}" request'
                    .format(self.client_address, self.command, self.path))
        
        data = None
        pathlist = self.pathlist
        timetable = self.server.timetable
        
        if pathlist[0] in req_path_settings:
            logger.debug('{} sending back Thermod settings'.format(self.client_address))
            
            with timetable.lock:
                settings = timetable.settings
                last_updt = timetable.last_update_timestamp()
            
            data = self._send_header(200, data=settings, last_modified=last_updt)
        
        elif pathlist[0] in req_path_heating:
            logger.debug('{} sending back heating status'.format(self.client_address))
            
            with timetable.lock:
                last_updt = time.time()
                heating = {req_heating_status: timetable.heating.status(),
                           req_heating_temperature: timetable.thermometer.temperature,
                           req_heating_target_temp: timetable.target_temperature()}
                
            data = self._send_header(200, data=heating, last_modified=last_updt)
            
        else:
            error = 404
            message = 'invalid request'
            logger.warning('{} {} "{} {}" received'
                           .format(self.client_address, message,
                                   self.command, self.path))
                       
            data = self._send_header(error, message, {rsp_error: message})
        
        self.end_headers()
        logger.debug('{} header sent'.format(self.client_address))
        
        return data
    
    def do_GET(self):
        """Manage the GET requests sending back data as JSON string.
        
        Two paths are supported: `/settings` and `/heating`. The first returns
        all settings as stored in the timetable.json file, the second returns
        the current informations about the heating: status and temperature.
        See `BaseHeating.status()` and `BaseThermometer.temperature()` to know
        the types of returned values.
        """
        
        settings = self.do_HEAD()
        
        if settings:
            self.wfile.write(settings)
            logger.debug('{} response sent'.format(self.client_address))
        
        logger.debug('{} closing connection'.format(self.client_address))
    
    def do_POST(self):
        """Manage the POST request updating timetable settings.
        
        With this request a client can update the settings of the daemon. The
        request path is the same of the GET method and the new settings must
        be present in the body of the request.
        
        Accepted settings in the body:
            * `settings` to update the whole state (JSON encoded settings)
            * TODO the other values
        """
        # TODO completare la documentazione con la descrizione dei campi accettati
        
        logger.debug('{} received "{} {}" request'
                     .format(self.client_address, self.command, self.path))
        
        code = None
        data = None
        
        if self.pathlist[0] in req_path_settings:
            logger.debug('{} parsing received POST data'.format(self.client_address))
            
            # code copied from http://stackoverflow.com/a/13330449
            ctype, pdict = cgi.parse_header(self.headers['Content-Type'])
            
            if ctype == 'multipart/form-data':
                postvars = cgi.parse_multipart(self.rfile, pdict)
            elif ctype == 'application/x-www-form-urlencoded':
                length = int(self.headers['Content-Length'])
                postvars = cgi.parse_qs(self.rfile.read(length), keep_blank_values=1)
            else:
                postvars = {}
            
            # TODO capire se questo aggiustamento serve sempre
            postvars = {k.decode('utf-8'): v[0].decode('utf-8') for k,v in postvars.items()}
            
            logger.debug('{} POST content-type: {}'.format(self.client_address, ctype))
            logger.debug('{} POST variables: {}'.format(self.client_address, postvars))
            
            with self.server.timetable.lock:
                # updating all settings
                if req_settings_all in postvars:
                    logger.debug('{} updating Thermod settings'.format(self.client_address))
                    
                    try:
                        self.server.timetable.settings = postvars[req_settings_all]
                        self.server.timetable.save()  # saving changes to filesystem
                    
                    except JSONDecodeError as jde:
                        code = 400
                        logger.warning('{} cannot update settings, the POST '
                                       'request contains invalid JSON syntax: '
                                       '{}'.format(self.client_address, jde))
                        
                        message = 'invalid JSON syntax'
                        response = {rsp_error: message, rsp_fullmsg: str(jde)}
                    
                    except (ValidationError, JsonValueError) as ve:
                        code = 400
                        
                        logger.warning('{} cannot update settings, the POST '
                                       'request contains incomplete or invalid '
                                       'data: {}'.format(self.client_address,
                                                         ve.message))
                        
                        message = 'incomplete or invalid JSON-encoded settings'
                        response = {rsp_error: message, rsp_fullmsg: ve.message}
                    
                    except IOError as ioe:
                        # can be raised only by timetable.save() method, so the
                        # internal settings have already been updated and a
                        # reload of the old settings is required
                        code = 500
                        logger.error('{} cannot save new settings to '
                            'fileystem: {}'.format(self.client_address, ioe))
                        
                        message = 'cannot save new settings to filesystem'
                        response = {rsp_error: message, rsp_fullmsg: str(ioe)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                        # TODO ci può essere un IOError anche qui e in tutti i
                        # punti in cui si esegue reload(), questa cosa deve
                        # essere gestita come errore critico che porta allo
                        # shutdown del demone
                    
                    except Exception as e:
                        code = 500
                        
                        logger.critical('{} Cannot update settings, the POST '
                                        'request produced an unhandled '
                                        'exception; in order to diagnose what '
                                        'happened execute Thermod in debug '
                                        'mode and resubmit the last request.'
                                        .format(self.client_address))
                        
                        logger.debug('{} {}: {}'.format(self.client_address,
                                                        type(e).__name__, e))
                        
                        message = 'cannot process the request'
                        response = {rsp_error: message, rsp_fullmsg: str(e)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    else:
                        code = 200
                        message = 'all settings updated'
                        logger.info('{} {}'.format(self.client_address, message))
                        response = {rsp_message: message}
                    
                    finally:
                        data = self._send_header(code, message, response)
            
                # updating only some days
                elif req_settings_days in postvars:
                    logger.debug('{} updating one or more days'.format(self.client_address))
                    
                    try:
                        days = self.server.timetable.update_days(postvars[req_settings_days])
                        self.server.timetable.save()  # saving changes to filesystem
                    
                    except JSONDecodeError as jde:
                        code = 400
                        logger.warning('{} cannot update any days, the POST '
                                       'request contains invalid JSON syntax: '
                                       '{}'.format(self.client_address, jde))
                        
                        message = 'invalid JSON syntax'
                        response = {rsp_error: message, rsp_fullmsg: str(jde)}
                    
                    except (ValidationError, JsonValueError) as ve:
                        code = 400
                        
                        logger.warning('{} cannot update any days, the POST '
                                       'request contains incomplete or invalid '
                                       'data: {}'.format(self.client_address,
                                                         ve.message))
                        
                        message = 'incomplete or invalid JSON-encoded days'
                        response = {rsp_error: message, rsp_fullmsg: ve.message}
                    
                    except IOError as ioe:
                        # can be raised only by timetable.save() method, so the
                        # internal settings have already been updated and a
                        # reload of the old settings is required
                        code = 500
                        logger.error('{} cannot save new settings to '
                            'fileystem: {}'.format(self.client_address, ioe))
                        
                        message = 'cannot save new settings to filesystem'
                        response = {rsp_error: message, rsp_fullmsg: str(ioe)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    except Exception as e:
                        code = 500
                        
                        logger.critical('{} Cannot update any days, the POST '
                                        'request produced an unhandled '
                                        'exception; in order to diagnose what '
                                        'happened execute Thermod in debug '
                                        'mode and resubmit the last request.'
                                        .format(self.client_address))
                        
                        logger.debug('{} {}: {}'.format(self.client_address,
                                                        type(e).__name__, e))
                        
                        message = 'cannot process the request'
                        response = {rsp_error: message, rsp_fullmsg: str(e)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    else:
                        code = 200
                        
                        logger.info('{} updated the following days: {}'
                                    .format(self.client_address, days))
                        
                        message = 'days updated'
                        response = {rsp_message: '{}: {}'.format(message, days)}
                    
                    finally:
                        data = self._send_header(code, message, response)
            
                # updating other settings
                elif postvars:
                    logger.debug('{} updating one or more settings'.format(self.client_address))
                    
                    newvalues = {}
                    try:
                        for var, value in postvars.items():
                            if var == req_settings_status:
                                self.server.timetable.status = value
                                newvalues[var] = self.server.timetable.status
                            elif var == req_settings_t0:
                                self.server.timetable.t0 = value
                                newvalues[var] = self.server.timetable.t0
                            elif var == req_settings_tmin:
                                self.server.timetable.tmin = value
                                newvalues[var] = self.server.timetable.tmin
                            elif var == req_settings_tmax:
                                self.server.timetable.tmax = value
                                newvalues[var] = self.server.timetable.tmax
                            elif var == req_settings_differential:
                                self.server.timetable.differential = value
                                newvalues[var] = self.server.timetable.differential
                            elif var == req_settings_grace_time:
                                self.server.timetable.grace_time = value
                                newvalues[var] = self.server.timetable.grace_time
                            else:
                                raise ValidationError('invalid field `{}` '
                                                      'in request body'
                                                      .format(var))
                        
                        # saving changes to filesystem
                        self.server.timetable.save()
                    
                    except ValidationError as ve:
                        code = 400
                        logger.warning('{} cannot update settings: {}'
                                       .format(self.client_address, ve.message))
                        
                        message = 'cannot update settings'
                        response = {rsp_error: message, rsp_fullmsg: ve.message}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    except JsonValueError as jve:
                        code = 400
                        logger.warning('{} cannot update {}: {}'
                                       .format(self.client_address, var, jve))
                        
                        message = 'cannot update settings'
                        response = {rsp_error: message, rsp_fullmsg: str(jve)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    except IOError as ioe:
                        # can be raised only by timetable.save() method, so the
                        # internal settings have already been updated and a
                        # reload of the old settings is required
                        code = 500
                        logger.error('{} cannot save new settings to '
                            'fileystem: {}'.format(self.client_address, ioe))
                        
                        message = 'cannot save new settings to filesystem'
                        response = {rsp_error: message, rsp_fullmsg: str(ioe)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    except Exception as e:
                        code = 500
                        
                        logger.critical('{} Cannot update settings, the POST '
                                        'request produced an unhandled '
                                        'exception; in order to diagnose what '
                                        'happened execute Thermod in debug '
                                        'mode and resubmit the last request.'
                                        .format(self.client_address))
                        
                        logger.debug('{} {}: {}'.format(self.client_address,
                                                        type(e).__name__, e))
                        
                        message = 'cannot process the request'
                        response = {rsp_error: message, rsp_fullmsg: str(e)}
                        
                        # reloading old settings still present on filesystem
                        self.server.timetable.reload()
                    
                    else:
                        code = 200
                        message = 'settings updated'
                        logger.info('{} {}: {}'.format(self.client_address, message, newvalues))
                        response = {rsp_message: '{}: {}'.format(message, newvalues)}
                    
                    finally:
                        data = self._send_header(code, message, response)
            
                else:
                    code = 400
                    logger.warning('{} cannot update settings, the POST request '
                                   'contains no data'.format(self.client_address))
                    
                    message = 'no settings provided'
                    data = self._send_header(code, message, {rsp_error: message})
                
                # if some settings of timetable have been updated, we'll notify
                # this changes in order to recheck current temperature
                if code==200:
                    self.server.timetable.lock.notify()
        
        else:
            code = 404
            message = 'invalid request'
            logger.warning('{} {} "{} {}" received'
                           .format(self.client_address, message,
                                   self.command, self.path))
            
            data = self._send_header(code, message, {rsp_error: message})
        
        logger.debug('{} sending back {} code {:d}'
                     .format(self.client_address,
                             ((code>=400) and 'error' or 'status'),
                             code))
        
        self.end_headers()
        logger.debug('{} header sent'.format(self.client_address))
        
        if data:
            self.wfile.write(data)
            logger.debug('{} response sent'.format(self.client_address))
        
        logger.debug('{} closing connection'.format(self.client_address))
    
    def _do_other(self):
        logger.info('{} received "{} {}" request'
                    .format(self.client_address, self.command, self.path))
        
        code = 501
        self._send_header(code)
        logger.warning('{} unsupported method `{}`, sending back error code {}'
                       .format(self.client_address, self.command, code))
        
        self.end_headers()
        logger.debug('{} header sent'.format(self.client_address))
    
    def do_PUT(self):
        self._do_other()
    
    def do_PATCH(self):
        self._do_other()
    
    def do_DELETE(self):
        self._do_other()


# only for debug purpose
if __name__ == '__main__':
    import os
    import shutil
    import tempfile
    
    logger.setLevel(logging.DEBUG)
    
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt=config.logger_fmt_msg,
                                           datefmt=config.logger_fmt_datetime,
                                           style=config.logger_fmt_style))
    logger.addHandler(console)
    
    file = 'timetable.json'
    tmpfile = os.path.join(tempfile.gettempdir(),file)
    shutil.copy(file, tmpfile)
    tt = TimeTable(tmpfile)
    cc = ControlThread(tt)
    
    try:
        cc.start()
        cc.join()
    except:
        cc.stop()
