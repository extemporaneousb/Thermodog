import time
import boto3
import random
import pprint

from .common import utcIso, utcNow

class CloudWatch(object):
    def __init__(self, namespace=None):
        self._client = boto3.client('cloudwatch')
        self._namespace = namespace

    def listMetrics(self):
        return self.client.list_metrics(Namespace=self.namespace)

    @property
    def namespace(self):
        return self._namespace
    @property
    def client(self):
        return self._client    

class CloudWatchMetric(CloudWatch):
    def __init__(self, metricName=None, dimName=None,
                 dimValue=None, **kwargs):
        super(CloudWatchMetric, self).__init__(**kwargs)
        self._metricName = metricName
        self._dimName = dimName
        self._dimValue = dimValue

    @property
    def metricName(self):
        return self._metricName
    @property
    def dimName(self):
        return self._dimName
    @property
    def dimValue(self):
        return self._dimValue   

    @property
    def metricDict(self):
        return {
            "MetricName": self.metricName,
            "Dimensions": [{
                "Name": self.dimName,
                "Value": self.dimValue
            }]
        }

    def push(self, value, timestamp=None):
        if not timestamp:
            timestamp = utcNow()
        ## pushing one value at a time might be problematic, if: we do
        ## so every minute, we have 60*24*30*10, where 10 is the
        ## approximate number of dogs; the fix is to measure more and
        ## submit less using the vector submit.
        d = self.metricDict
        d.update({
            "Value": value,
            "Timestamp": timestamp
        })
        self.client.put_metric_data(
            Namespace = self.namespace,
            MetricData = [d])

    def metricStats(self, startTime=None, endTime=None, period=10*60):
        endTime = endTime if endTime else utcIso()
        startTime = startTime if startTime else \
                    utcIso(utcNow() - timedelta(hours=24))
        d = self.metricDict
        d.update({
            "Namespace": self.namespace,
            "StartTime": startTime,
            "EndTime": endTime,
            "Period": period,
            "Statistics": [
                'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum'
            ]})
        return self.client.get_metric_statistics(**d)


    def addAlarm(self,
                 alarmName,
                 threshold=30,
                 alarmActions=[
                     "arn:aws:sns:us-west-2:329245541944:thermodog"
                 ],
                 period=60,
                 evalPeriods=2,
                 datapointsToAlarm=2,
                 treatMissingData="breaching",
                 compOperator="GreaterThanOrEqualToThreshold"):
    
        adict = {
            "AlarmName":                alarmName,
            "ActionsEnabled":           True,
            "AlarmActions":             alarmActions,
            "InsufficientDataActions":  alarmActions,
            "MetricName":               self.metricName,
            "Namespace":                self.namespace,
            "Statistic":                "Average",
            "Dimensions":               [{
                "Name": self.dimName,
                "Value": self.dimValue
            }],
            "Threshold": threshold,
            "Period": period,
            "EvaluationPeriods": evalPeriods,
            "DatapointsToAlarm": datapointsToAlarm,
            "TreatMissingData": treatMissingData,
            "ComparisonOperator": compOperator
        }
        self.client.put_metric_alarm(**adict)

