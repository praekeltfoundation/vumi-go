import re


class CeleryRegexRouter(object):
    def __init__(self, regex, queue):
        self.regex = re.compile(regex)
        self.queue = queue

    def route_for_task(self, task, args=None, kwargs=None):
        if self.regex.match(task):
            return {'queue': self.queue}
        else:
            return None


class CeleryAppRouter(object):
    def route_for_task(self, task, args=None, kwargs=None):
        return {'queue': '.'.join(task.split('.')[:2])}
