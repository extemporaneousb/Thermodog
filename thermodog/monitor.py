import sys
import numpy
import logging
import time
from threading import Thread, Lock, Event

from .coms import SnsTopic
from .cloudwatch import CloudWatchMetric
from .common import utcIso, pstIso

log = logging.getLogger("thermodog")

## Adapted from: ActiveState/65222_Run_a_task_every_few_seconds
class TaskThread(Thread):
    def __init__(self, f, taskfreq=60*60, **args):
        Thread.__init__(self)
        self._finished = Event()
        self._taskfreq = taskfreq
        self._taskfunc = f
        self._taskargs = args
        
    def run(self):
        while True:
            if self._finished.is_set():
                return
            else:
                self._taskfunc(**self._taskargs)
            self._finished.wait(self._taskfreq)

    def active(self):
        return not self._finished.is_set()

    def stop(self):
        self._finished.set()

class HasSensor(object):
    @property
    def name(self):
        return self.sensor.name
    @property
    def sensor(self):
        return self._sensor
    def fmtMsg(self, msg):
        return self.sensor.formatMsg(msg)
    @property
    def alerter(self):
        return self.sensor.alerter

class SensorMonitor(HasSensor):
    def __init__(self, sensor, doMonitor=lambda x: sys.stdout.write(str(x)),
                 freq=60*5, restarts=4):
        self._freq      = freq
        self._mfx       = doMonitor
        self._sensor    = sensor

        # `fails` correspond to situations that may resolve
        # themselves, e.g., network issues or hardware initialization
        # issues.
        self._maxfails  = restarts
        self._consfails = 0

        def domfx():
            try:
                sss = self.sensor.sample()
                self._mfx(sss)
                self._consfails = 0
            except Exception as e:
                if self.sensor.stopped():
                    self.stop()
                else:
                    m = self.fmtMsg(
                        "encountered unexpected exception: {}".format(e))
                    log.exception(m)
                    self._consfails += 1
                    if self._consfails < self._maxfails:
                        s = "continuing (attempt {} of {})".format(self._consfails,
                                                                   self._maxfails)
                        log.info(self.fmtMsg(s))
                        time.sleep(self._freq * self._consfails)
                    else:
                        s = "maximum allowed fails exceeded ... ending!"
                        # Send system-level alert
                        self.sensor.alertSys("{} - root cause: {}".format(m, s))
                        self.stop()

        ## start the monitoring process.
        self._reader = TaskThread(domfx, self._freq)
        self._reader.start()

    def stop(self):
        if self.running():
            self._reader.stop()
    def running(self):
        return self._reader.active()

class HasMonitor(object):
    @property
    def monitor(self):
        return self._smon
    def stop(self):
        self.monitor.stop()
        
class SensorFileLogger(HasSensor, HasMonitor):
    def __init__(self, sensor, ofile, **args):
        self._sensor = sensor
        def lfx(evt):
            ofile.write("{}\n".format(
                self.formatRecord(evt)))
            ofile.flush()
            
        self._smon = SensorMonitor(self.sensor, doMonitor=lfx, **args)

    def formatRecord(self, evt):
        return "{:<10}\t{}\t{:>8.2f}C".format(
            self.name, pstIso(evt["timestamp"]), evt["celsius"])

class SensorRangeAlarm(HasSensor, HasMonitor):
    def __init__(self, sensor,
                 minc=-sys.maxint, maxc=sys.maxint,
                 graceperiod=2, **args):
        self._sensor     = sensor
        self._grace      = graceperiod
        self._tempbuf    = []
        self._faultstart = None
        self._args       = args
        self._minc       = minc
        self._maxc       = maxc
        if 'freq' in self._args:
            self._freq = self._args['freq']
        else:
            self._freq = 10
        self._args['freq'] = self._freq
        
        def lfx(evt):
            v = evt['celsius']
            if v < minc or v > maxc:
                self._tempbuf.append(v)
                if not self._faultstart:
                    ## the *start time* of current out-of-range event.
                    self._faultstart = evt['timestamp']
                if self.cevtdur(evt) > (60*self._grace):
                    self.doAlert(evt)
                log.info(self.fmtAlert(evt))
            else:
                ## after in-range reading, reset fault timer & buf
                self._faultstart = None
                self._tempbuf    = []
                self._grace      = graceperiod
                
        ## start monitoring
        self._smon = SensorMonitor(self.sensor, doMonitor=lfx, **self._args)

    @property
    def minc(self):
        return self._minc
    @property
    def maxc(self):
        return self._maxc
    
    def cevtdur(self, evt):
        if self._faultstart:
            return (evt['timestamp'] - self._faultstart).total_seconds()
        else:
            return 0

    def cevtavg(self, evt):
        return numpy.nanmean(self._tempbuf)
    
    def fmtAlert(self, evt):
        return self.fmtMsg(
            ("Out of range. Reporting: {}C at {}. " +
             "Ongoing out-of-range event duration: " +
             "{} minutes (next alert:: {}), avg: {}C, allowed range: ({}, {}).").format(
                 numpy.round(evt['celsius']),
                 pstIso(evt['timestamp']),
                 numpy.round(self.cevtdur(evt)/60, 1),
                 numpy.round(self._grace, 1),
                 numpy.round(self.cevtavg(evt), 2),
                 self.minc,
                 self.maxc))

    def doAlert(self, evt):
        ## send alerts to temperature monitors
        self.sensor.alert(self.fmtAlert(evt))
        ## an increasing grace period
        self._grace += 1.1 * self._grace


class CloudWatchHeartbeat(HasSensor, HasMonitor):
    @property
    def metric(self):
        return self._cwmetric
    
    def __init__(self, sensor, **args):
        self._sensor   = sensor
        self._args     = args
        self._cwmetric = CloudWatchMetric(namespace="Wholebiome/Thermodog",
                                          metricName="Temperature",
                                          dimName="MonitorName",
                                          dimValue=self.name)
        def cwp(evt):
            try:
                self.metric.push(numpy.round(evt['celsius']), evt['timestamp'])
            except Exception as e:
                log.exception(e)
                raise

        ## start monitoring
        self._smon = SensorMonitor(self.sensor,
                                   doMonitor=cwp, **self._args)
        
    def addAlarm(self, noun="Status", **args):
        self.metric.addAlarm("{} {}".format(self.name, noun), **args)
        return self
    

class SensorHeartbeat(HasSensor, HasMonitor):
    def __init__(self, sensor, **args):
        self._sensor = sensor
        self._topic  = SnsTopic(self.sensor.name)
        def lfx(x):
            try:
                fr = self.formatRecord(x)
                self._topic.publish(fr, fr)
                log.info("published to topic: {}".format(
                    self._topic.topicName))
            except:
                self.alerter.alertSys("Failed to post heartbeat!")

        self._smon = SensorMonitor(self.sensor, doMonitor=lfx, **args)

    def formatRecord(self, rec):
        return "{:<10}, {:>8.2f}C".format(
            rec["timestamp"], rec["celsius"])


class GasSensorFileLogger(SensorFileLogger):
    def formatRecord(self, evt):
        return "{} - {}".format(self.sensor.sensorType, evt)

class GasSensorHeartbeat(HasSensor, HasMonitor):
    @property
    def metric(self):
        return self._cwmetric
    
    def __init__(self, sensor, **args):
        self._sensor   = sensor
        self._cwmetric = CloudWatchMetric(namespace="Wholebiome/Gasdog",
                                          metricName="PPM",
                                          dimName="MonitorName",
                                          dimValue=self.name)
        def cwp(evt):
            if numpy.isnan(evt['PPM']):
                log.info("Metric PPM is NaN - not pushed to CloudWatch.")
            else:
                self.metric.push(numpy.round(evt['PPM']), evt['timestamp'])
                log.debug("Pushed PPM: {}".format(evt['PPM']))

        ## start monitoring
        self._smon = SensorMonitor(self.sensor, doMonitor=cwp, **args)
        
    def addAlarm(self, noun="Status", **args):
        self.metric.addAlarm("{} {}".format(self.name, noun), **args)
        return self
