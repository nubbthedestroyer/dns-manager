#!/usr/bin/python
import re
import time


def log(text, context="info", namespace="run"):
    date = time.strftime("%c")
    try:
        for l in iter(text.splitlines()):
            detector = re.compile('\033\[\d+(?:;\d+)?m')
            print("--- [" + str(date) + "] - [" + context + "][" + namespace + "] - " + detector.sub('', l))
    except:
        detector = re.compile('\033\[\d+(?:;\d+)?m')
        print("--- [" + str(date) + "] - [" + context + "][" + namespace + "] - " + detector.sub('', str(text)))
