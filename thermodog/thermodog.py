import os
import sys
import time
import pytz
import datetime
import string
import socket
import logging
import numpy

from threading import Thread, Lock, Event

from dateutil import parser
from datetime import timedelta, datetime

if os.uname()[4].startswith("arm"):
    import RPi.GPIO as GPIO
else:
    pass ## need the mock.

from .common import Singleton, utcNow
from .coms import SmsAlerter

log = logging.getLogger("thermodog")

class ThermoDog(object):
    __metaclass__ = Singleton

    ## board-level constants
    board     = GPIO.BOARD
    clock_pin = 23
    data_pin  = 21
    cs_pins   = [24, 26]
    leds      = [29, 31, 33, 32]
    power     = 13
    internet  = 32
    
    def __init__(self, name=None, alerter=None):
        if not name:
            self._name = socket.gethostname()
        else:
            self._name = name

        if not alerter:
            self._alerter = SmsAlerter()
        else:
            self._alerter = alerter

        # Intialize board
        GPIO.setmode(ThermoDog.board)
        GPIO.setwarnings(False)

        GPIO.setup(ThermoDog.power, GPIO.IN)
        GPIO.setup(ThermoDog.internet, GPIO.IN)
        
        # Initialize clock and data pin
        GPIO.setup(ThermoDog.clock_pin, GPIO.OUT)
        GPIO.setup(ThermoDog.data_pin, GPIO.IN)
        # Initialize thermocouple pins
        for p in ThermoDog.cs_pins:
            GPIO.setup(p, GPIO.OUT)        
            GPIO.output(p, GPIO.HIGH)
        self.lock = Lock()

        # Setup sensors dict
        self._sensors = {}
        
        # Setup status lights
        self._LEDS = {}
        self.powerLed = self.LED(1)
        self.internetLed = self.LED(2)
        self.LED(3).off
        self.LED(4).off
        self.internetLed.off

        if GPIO.input(ThermoDog.power):
            self.powerLed.on
        else:
            self.powerLed.off
            
        def powerAlert(c):
            ## Make sure to wait a bit after being triggered, as race
            ## has been witnessed.
            time.sleep(.2)

            if GPIO.input(ThermoDog.power):
                log.info(self.formatMsg("Has power."))
                ## if you get power, you could have been blinking (the
                ## LED should probably have a thread, not be a
                ## thread).
                self.powerLed.stop()
                self.powerLed = self.LED(1)
                self.powerLed.on
            else:
                msg = self.formatMsg("Has lost power.")
                log.info(msg)
                self.powerLed.blink(.5, .15)
                ## Alert service monitors of power loss.
                self.alert(msg)
        
        try:
            ## run it once at first start.
            powerAlert(ThermoDog.power)
            GPIO.remove_event_detect(ThermoDog.power)
            GPIO.add_event_detect(ThermoDog.power, GPIO.BOTH,
                                  callback=powerAlert,
                                  bouncetime=500)
        except Exception as e:
            log.exception(e)

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return "T://{}".format(self.name)

    @property
    def alerter(self):
        return self._alerter

    def formatMsg(self, s):
        return "[{}] - {}".format(self.url, s)

    def alert(self, msg):
        """Fire a system-level alert."""
        self.alerter.alertSys(msg)

    def shutdown(self):
        log.info(self.formatMsg("shutting down."))
        GPIO.remove_event_detect(ThermoDog.power)
        log.info(self.formatMsg("stopping sensors."))
        self.stopSensors()
        log.info(self.formatMsg("stopping LEDs."))
        self.stopLeds()
        try:
            GPIO.cleanup()
            log.info(self.formatMsg("restarted GPIO."))
        except:
            log.exception(self.formatMsg(
                "failed to stop GPIO."))
            
    def stopLeds(self):
        for v in self._LEDS.values():
            log.debug(self.formatMsg(
                "stopping led on pin: {}".format(v.pin)))
            v.stop()

    class _LED(object):
        def __init__(s, p):
            s.running = False
            s.pin = p
            s.done = False

        def __del__(s):
            try:
                s.stop()
            except:
                pass
            
        @property
        def on(s):
            return GPIO.setup(s.pin, GPIO.IN, GPIO.PUD_UP)
        @property
        def off(s):
            return GPIO.setup(s.pin, GPIO.IN, GPIO.PUD_DOWN)

        def flash(s, duration=.1):
            s.on
            time.sleep(duration)
            s.off

        def blink(s, f=1, d=.1):            
            def bb():
                s.running = True
                while s.running:
                    s.flash(d)
                    time.sleep(f)
                s.done = True
            if not s.running:
                s.th = Thread(target=bb)
                s.th.start()
            
        def stop(s):
            if s.running:
                s.running = False
                while not s.done:
                    time.sleep(.2)
                    s.off
                return True
            else:
                s.off
                return False

        def stopOn(s):
            if s.stop():
                s.on
                return True
            else:
                s.on
                return False
                    
    def LED(self, i):
        pinNo = ThermoDog.leds[i-1]
        if pinNo not in self._LEDS:
            self._LEDS[pinNo] = ThermoDog._LED(pinNo)
        return self._LEDS[pinNo]

    ##
    ## The interface to the MAX31855 was adapted from:
    ##  github.com/Tuckie/max31855/blob/master/max31855.py
    ##
    def read(self, n):
        cs_pin = self.cs_pins[n-1]
        def validate(data_32):
            '''
            Checks error bits to see if there are 
            any SCV, SCG, or OC faults
            '''
            anyErrors = (data_32 & 0x10000) != 0    # Fault bit, D16
            noConnection = (data_32 & 1) != 0       # OC bit, D0
            shortToGround = (data_32 & 2) != 0      # SCG bit, D1
            shortToVCC = (data_32 & 4) != 0         # SCV bit, D2
            if anyErrors:
                if noConnection:
                    raise Exception("No Connection")
                elif shortToGround:
                    raise Exception("Thermocouple short to ground")
                elif shortToVCC:
                    raise Exception("Thermocouple short to VCC")
                else:
                    # Perhaps another SPI device is trying to send data?
                    # Did you remember to initialize all other SPI devices?
                    raise Exception("Unknown Error")
            else:
                return data_32

        def tcpart(data_32):
            tc_data = ((data_32 >> 18) & 0x3FFF)
            if tc_data & 0x2000:
                # two's compliment
                without_resolution = ~tc_data & 0x1FFF
                without_resolution += 1
                without_resolution *= -1
            else:
                without_resolution = tc_data & 0x1FFF
            return without_resolution * 0.25

        def rjpart(data_32):
            rj_data = ((data_32 >> 4) & 0xFFF)
            if rj_data & 0x800:
                without_resolution = ~rj_data & 0x7FF
                without_resolution += 1
                without_resolution *= -1
            else:
                without_resolution = rj_data & 0x7FF
            return without_resolution * 0.0625

        released=True
        try:
            self.lock.acquire()
            released=False
            bytesin = 0
            # Select the chip
            GPIO.output(cs_pin, GPIO.LOW)
            # Read in 32 bits
            for i in range(32):
                GPIO.output(ThermoDog.clock_pin, GPIO.LOW)
                bytesin = bytesin << 1
                if (GPIO.input(ThermoDog.data_pin)):
                    bytesin = bytesin | 1
                GPIO.output(ThermoDog.clock_pin, GPIO.HIGH)
            # Unselect the chip
            GPIO.output(cs_pin, GPIO.HIGH)
            v = validate(bytesin)
            self.lock.release()
            released=True
            # Return tuple of current thermocouple amplifier readings.
            return (tcpart(v), rjpart(v))
        except:
            if not released:
                self.lock.release()
            raise
                  
    def avg(self, tcn, nSamples=4, sampleRate=.05, calibration=(0,1)):
        def adjust(xvv):
	    return [(calibration[0] + vv*calibration[1]) for vv in xvv]
        v = []
        for e in xrange(nSamples):
            v.append(adjust(self.read(tcn)))
            time.sleep(sampleRate)
        v = numpy.array(v)
        return (numpy.nanmean(v[0:,0]),
                numpy.nanmean(v[0:,1]))

    def measure(self, tcn, **args):
        def F(x):
            return x*9.0/5.0 + 32.0
        v, rj = self.avg(tcn, **args)
        return dict(timestamp=utcNow(), celsius=v,
                    farenheit=F(v), internal=rj, channel=tcn)

    ## handle to a thermocouple and corresponding LED
    class _Sensor(object):
        def __init__(self, parent, tcn, name=None,
                     calibration=(0, 1),
                     nSamples=5, sampleRate=.1):            
            self._parent     = parent
            self._name       = name if name else "TS-{}".format(tcn)
            self.pin         = tcn
            self.calibration = calibration
            self.nSamples    = nSamples
            self.sampleRate  = sampleRate
            self.led         = self.parent.LED(self.pin)
            self._stopped    = False
            # turn the led on.
            self.led.on

        def __repr__(self):
            return self.url
            
        @property
        def name(self):
            return self._name
        @property
        def parent(self):
            return self._parent
        @property
        def url(self):
            return "{}/{}".format(self.parent.url,
                                  self.name)
        @property
        def alerter(self):
            return self.parent.alerter

        def alertMon(self, msg):
            self.alerter.alertMon(msg)

        def alertSys(self, msg):
            self.alerter.alertSys(msg)

        def alert(self, msg):
            """Fire a monitoring alert."""
            self.alertMon(msg)
            
        def formatMsg(self, msg):
            return"[{}] - {}".format(self.url, msg)
        
        def stop(self):
            self._stopped = True
            self.led.off

        def stopped(self):
            return self._stopped

        def sample(self):
            if not self.stopped():
                return self.parent.measure(self.pin,
                                           calibration=self.calibration,
                                           nSamples=self.nSamples,
                                           sampleRate=self.sampleRate)
            else:
                raise StopIteration(
                    "sensor: {} is not available.".format(self.pin))

    def sensor(self, tcn, **args):
        """Return sensor object for Thermocouple on pin: `tcn`"""
        if tcn not in self._sensors:
            self._sensors[tcn] = ThermoDog._Sensor(self, tcn, **args)
        return self._sensors[tcn]

    def stopSensors(self):
        for n, s in self._sensors.items():
            s.stop()
        self._sensors = {}
        log.debug(self.formatMsg("has been stopped."))
