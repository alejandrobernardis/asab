import logging
import datetime
import os
import sys
import platform
import pprint
import json

import pika
import asab

from ..log import LOG_NOTICE

class LogmanIOLogHandler(logging.Handler):

	def __init__(self, svc, level=logging.NOTSET):
		super().__init__(level=level)

		self.Service = svc

		self.Facility = None # TODO: Read this from config
		self.Pid = os.getpid()
		self.Environment = None
		self.Hostname = platform.node()
		self.Program = os.path.basename(sys.argv[0])

		self.Properties = pika.BasicProperties(
			content_type='application/json',
			delivery_mode=2, # Persistent delivery mode
			headers = {
				'H': self.Hostname,
				'T': 'sj', # Syslog in JSON
			}
		)
		self.RoutingKey = asab.Config.get('logman.io', 'routing_key')


	def emit(self, record):
		severity = 7
		if record.levelno > logging.DEBUG and record.levelno <= logging.INFO:
			severity = 6 # Informational
		elif record.levelno <= LOG_NOTICE:
			severity = 5 # Notice
		elif record.levelno <= logging.WARNING:
			severity = 4 # Warning
		elif record.levelno <= logging.ERROR:
			severity = 3 # Error
		elif record.levelno <= logging.CRITICAL:
			severity = 2 # Critical
		else:
			severity = 1 # Alert

		message = record.getMessage()
		if record.exc_text is not None:
			message += '\n'+record.exc_text
		if record.stack_info is not None:
			message += '\n'+record.stack_info

		log_entry = {
			"@timestamp": datetime.datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
			"T": "syslog",
			"M": message,
			"H": self.Hostname,
			"P": self.Program,
			"C": record.name,
			"s": "{}:{}".format(record.funcName, record.lineno),
			"p": record.process,
			"Th": record.thread,
			"l": severity,
		}

		if self.Facility is not None:
			log_entry['f'] = self.Facility

		if self.Environment is not None:
			log_entry['e'] = self.Environment

		sd = record.__dict__.get("_struct_data")
		if sd is not None:
			log_entry['sd'] = sd

		self.Service.OutboundQueue.put_nowait((self.RoutingKey, json.dumps(log_entry), self.Properties))

