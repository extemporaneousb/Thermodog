##
## Communication-related classes.
##
import time
import json
import boto3
import logging

log = logging.getLogger("thermodog")

class SnsTopic(object):
    def __init__(self, topicName):
        self._topicName = topicName
        response = self.client.create_topic(Name=self.topicName)
        self.pubArn = response.get("TopicArn", None)

    @property
    def topicName(self):
        return self._topicName

    @property
    def client(self):
        return boto3.client("sns")
    
    def __repr__(self):
        return "SnsTopic('{}')".format(self.topicName)
    
    def subscribe(self, email):
        self.client.subscribe(TopicArn=self.pubArn, Protocol="email",
                              Endpoint=email)
        log.info("Subscribed {} to {}".format(email, self))
                  
    def publish(self, subject, message):
        log.info("Publishing to topic: {}".format(self.topicName))
        if len(subject) > 100:
            log.info("Truncating subject to 100 characters.")
            subject = subject[0:100]
        self.client.publish(TopicArn=self.pubArn,
                            Message=message, Subject=subject)

class SmsRecipient(object):
    """Receive fixed number of SMS messages per hour and day."""
    def __init__(self, phoneNumber, maxSmsPerHour=4, maxSmsPerDay=20):
        self._number    = phoneNumber
        self._perhour   = maxSmsPerHour
        self._perday    = maxSmsPerDay
        self._sendtimes = []
        self._lastalert = 0
        self._client    = boto3.client("sns")

    def __repr__(self):
        return "SmsRecipient('{}')".format(self._number)

    def sendMsg(self, msg):
        now  = time.time()
        lthourold = [t for t in self._sendtimes if t >= (now - 60*60)]
        ltdayold = [t for t in self._sendtimes if t >= (now - 60*60*24)]
        if len(lthourold) < self._perhour and \
           len(ltdayold) < self._perday:
            log.info("Sending SMS to: {} ({}, {}).".format(
                self, len(lthourold), len(ltdayold)))
            self._client.publish(PhoneNumber=self._number, Message=msg)
            self._sendtimes = ltdayold + [now]
        else:
            log.info("NOT sending SMS to: {} ({}, {}).".format(
                self, len(lthourold), len(ltdayold)))

class SmsAlerter(object):
    SYS_LIST = 1
    MON_LIST = 2
    ALL_LIST = SYS_LIST | MON_LIST

    def __init__(self, *numbers, **args):
        self._recipients = {}
        for number in numbers:
            self.addRecipient(number, **args)
        
    def addRecipient(self, number, receive=MON_LIST, **args):
        self._recipients[number] = (
            receive, SmsRecipient(number, **args))

    def alert(self, distributionList, msg):
        for g, r in self._recipients.values():
            if (g & distributionList) == g:
                r.sendMsg(msg)

    def alertAll(self, msg):
        self.alert(SmsAlerter.ALL_LIST, msg)

    def alertSys(self, msg):
        self.alert(SmsAlerter.SYS_LIST, msg)

    def alertMon(self, msg):
        self.alert(SmsAlerter.MON_LIST, msg)



