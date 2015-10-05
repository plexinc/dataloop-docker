#!/usr/bin/env python
import requests
import uuid
from time import sleep
import socket
import sys, getopt
import multiprocessing

API_KEY = ''  # You need to set this!
EXCHANGE = 'https://agent.dataloop.io'
API = 'https://www.dataloop.io'
CADVISOR = 'http://127.0.0.1:8080'

GRAPHITE_SERVER = 'graphite.dataloop.io'
GRAPHITE_PORT = 2003

CORES = multiprocessing.cpu_count()


def api_header():
    return {"Content-type": "application/json", "Authorization": "Bearer " + API_KEY}


def get_mac():
    return str(uuid.getnode())


def flatten(structure, key="", path="", flattened=None):
    if flattened is None:
        flattened = {}
    if type(structure) not in (dict, list):
        flattened[((path + ".") if path else "") + key] = structure
    elif isinstance(structure, list):
        for i, item in enumerate(structure):
            flatten(item, "%d" % i, path + "." + key, flattened)
    else:
        for new_key, value in structure.items():
            flatten(value, new_key, path + "." + key, flattened)
    return flattened


def get_agents():
    # only get agents from dataloop that match the mac address of dl-dac container
    _resp = requests.get(API + "/api/agents", headers=api_header())
    agents = {}
    if _resp.status_code == 200:
        for l in _resp.json():
            if l['mac'] == get_mac():
                name = l['name']
                agents[name] = l['id']
    return agents


def get_metrics():
    _containers = []
    _metrics = {}
    try:
        _resp = requests.get(CADVISOR + '/api/v1.3/docker').json()
    except Exception as E:
        print "Failed to query containers: %s" % E
        return False

    for k, v in _resp.iteritems():
        _containers.append(v['name'].replace('/docker/', '')[:12])
        name = v['name'].replace('/docker/', '')[:12]
        _metrics[name] = v['stats']
    return _metrics


# send metrics to graphite
def send_msg(message):
    # print "Sending message:\n%s" % message
    # return
    try:
        sock = socket.socket()
        sock.connect((GRAPHITE_SERVER, GRAPHITE_PORT))
        sock.sendall(message)
        sock.close()
    except Exception, e:
        print('CRITICAL - something is wrong with %s:%s. Exception is %s' % (GRAPHITE_SERVER, GRAPHITE_PORT, e))


def main(argv):
    global API_KEY, CADVISOR

    try:
       opts, args = getopt.getopt(argv,"ha:c::",["apikey=","cadvisor="])
    except getopt.GetoptError:
       print 'metrics.py -a <apikey> -c <cadvisor address:port>'
       sys.exit(2)
    for opt, arg in opts:
       if opt == '-h':
          print 'metrics.py -a <apikey> -c <cadvisor address:port>'
          sys.exit()
       elif opt in ("-a", "--apikey"):
          API_KEY = arg
       elif opt in ("-c", "--cadvisor"):
          CADVISOR = arg
    print 'apikey is "', API_KEY , '"'
    print 'cadvisor endpoint is "', CADVISOR, '"'

    print "Container Metric Send running. Press ctrl+c to exit!"
    while True:
        agents = get_agents() or []
        metrics = get_metrics() or []

        flat_metrics = {}
        if len(agents)>0 and len(metrics)>0:
            for container, v in metrics.iteritems():
                finger = agents[container]
                flat_metrics[container] = {}

                # populate base metrics
                base = {
                    finger + '.base.load_1_min': v[0]['cpu']['load_average'],
                    finger + '.base.cpu': v[0]['cpu']['usage']['total'] * 1000000000 / CORES,
                    finger + '.base.memory': v[0]['memory']['usage']

                }
                flat_metrics[container].update(base)

                # send back everything else
                for a in v:
                    for m in ['network', 'diskio', 'memory', 'cpu']:
                        z = flatten(a[m], key=m, path=finger)
                        flat_metrics[container].update(z)
            print flat_metrics


            for c, d in flat_metrics.iteritems():
                for path, value in d.iteritems():
                    if isinstance(value, int):
                        message = "%s %s\n" % (path, value)
                        send_msg(message)

        sleep(10)    #  sleepy time



if __name__ == "__main__":
    main(sys.argv[1:])
