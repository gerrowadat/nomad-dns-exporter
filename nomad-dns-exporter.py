import time
import nomad
import dnslib
import cherrypy
import threading
import prometheus_client
from absl import app
from absl import flags
from absl import logging
from dnslib.server import DNSServer
from dnslib.server import DNSLogger


FLAGS = flags.FLAGS

flags.DEFINE_string('nomad_server', 'localhost', 'nomad server to talk to')
flags.DEFINE_string('dns_hostname', 'localhost', 'address to serve dns on')
flags.DEFINE_integer('dns_port', 5333, 'port to serve DNS queries on')
flags.DEFINE_string('http_hostname', 'localhost', 'address to serve http on')
flags.DEFINE_integer('http_port', 5334, 'port to serve http on')
flags.DEFINE_integer('dns_ttl_secs', 3600, 'DNS TTL')
flags.DEFINE_string('nomad_domain', '.job.nomad',
                    'domain to answer queries within')
flags.DEFINE_integer('nomad_jobinfo_update_interval_secs',
                     30,
                     'number of seconds between nomad jobinfo scrapes')


RESOLVE_TIME = prometheus_client.Summary(
    'resolve_time_seconds', 'Time spent resolving job names')


class JobsInfo(object):
    def __init__(self):
        self._jobs = {}

    def __str__(self):
        return '\n'.join(['[%s]: %s' % (x, self._jobs[x]) for x in self._jobs])

    @property
    def jobnames(self):
        return list(self._jobs.keys())

    def get_job(self, jobname):
        return self._jobs.get(jobname) or []

    def add_alloc(self, jobname, nodename):
        if jobname in self._jobs:
            self._jobs[jobname].append(nodename)
        else:
            self._jobs[jobname] = [nodename]


class JobsInfoThread(threading.Thread):
    def __init__(self, metrics):

        self._m = metrics
        self._j = JobsInfo()
        self._jl = threading.RLock()

        # lock for nomad client (initialised in run())
        self._nl = threading.RLock()

        # dict { nodename: IP }
        self._nodes = {}
        self._nodes_lock = threading.RLock()

        threading.Thread.__init__(self)

    def lookup_job(self, jobname):
        with self._jl:
            return self._j.get_job(jobname)

    def run(self):
        with self._nl:
            self._n = nomad.Nomad(host=FLAGS.nomad_server)
        while True:
            # Rebuild our list of nodes
            # (probably overkill, but also probably cheap).
            with self._nodes_lock:
                nodes = self._n.nodes.get_nodes()
                new_nodes = {}
                for n in nodes:
                    new_nodes[n['Name']] = n['Address']
                self._nodes = new_nodes

            new_ji = JobsInfo()
            for j in self._n.jobs:
                jobname = j['ID']
                allocs = self._n.job.get_allocations(jobname)
                live_allocs = \
                    [x for x in allocs if x['ClientStatus'] == 'running']
                for alloc in live_allocs:
                    if alloc['NodeName'] not in self._nodes:
                        logging.warning(
                            'Job %s running on unknown nde %s, skipping' % (
                                jobname, alloc['NodeName']))
                    else:
                        new_ji.add_alloc(jobname,
                                         self._nodes[alloc['NodeName']])

            with self._jl:
                for j in set(self._j.jobnames + new_ji.jobnames):
                    old_loc = self._j.get_job(j)
                    new_loc = new_ji.get_job(j)
                    if new_loc == []:
                        new_loc = '*poof*'
                    if old_loc == []:
                        old_loc = '<absent>'
                    if new_loc != old_loc:
                        logging.info('[%s] %s -> %s', j, old_loc, new_loc)
                self._m['jobinfo_updated'].set_to_current_time()
                self._j = new_ji

            time.sleep(FLAGS.nomad_jobinfo_update_interval_secs)


class NomadResolver(object):
    def __init__(self, job_info_thread, metrics):
        self._ji = job_info_thread
        self._m = metrics

    @RESOLVE_TIME.time()
    def resolve(self, req, handler):
        self._m['all_dns_requests_count'].inc()
        rep = req.reply()

        query = str(req.q.qname)[:-1]

        if req.q.qtype != dnslib.QTYPE.A:
            logging.warning('Not able to answer %s query for %s' % (
                dnslib.QTYPE.get(req.q.qtype), query))
            rep.header.rcode = dnslib.RCODE.NXDOMAIN
            return rep

        if not query.endswith(FLAGS.nomad_domain):
            self._m['all_dns_nxdomain_count'].inc()
            logging.warning(
                'NXDOMAIN (outside %s domain) for %s' % (
                    FLAGS.nomad_domain, query))
            return rep

        # Strip the nomad domain off the query.
        svc_query = query[:(len(query) - len(FLAGS.nomad_domain))]

        allocs = self._ji.lookup_job(svc_query)

        if len(allocs) == 0:
            self._m['all_dns_nxdomain_count'].inc()
            return rep

        for alloc_ip in allocs:
            rep.add_answer(dnslib.RR(
                                     str(req.q.qname),
                                     rdata=dnslib.A(alloc_ip),
                                     ttl=FLAGS.dns_ttl_secs))
        self._m['all_dns_success_count'].inc()
        return rep


class WebServer(object):
    def __init__(self, metrics):
        self._m = metrics

    @cherrypy.expose
    def index(self):
        return '<a href="/metrics">metrics</a>'

    @cherrypy.expose
    def metrics(self):
        return prometheus_client.generate_latest()


def main(argv):

    metrics = {}
    metrics['jobinfo_updated'] = prometheus_client.Gauge(
        'jobinfo_updated', 'last update of job info')
    metrics['all_dns_requests_count'] = prometheus_client.Counter(
        'all_dns_requests_count', 'count of all dns requests')
    metrics['all_dns_success_count'] = prometheus_client.Counter(
        'all_dns_success_count', 'all successfully answered dns requests')
    metrics['all_dns_nxdomain_count'] = prometheus_client.Counter(
        'all_dns_nxdomain_count', 'all unfound dns requests')
    cherrypy.config.update(
        {'server.socket_host': FLAGS.http_hostname,
         'server.socket_port': FLAGS.http_port})

    jut = JobsInfoThread(metrics)
    jut.start()

    resolver = NomadResolver(jut, metrics)

    dns_logger = DNSLogger()

    logging.info('Starting DNS server on port %d' % (FLAGS.dns_port))
    dns_server = DNSServer(resolver,
                           port=FLAGS.dns_port,
                           address=FLAGS.dns_hostname,
                           logger=dns_logger)
    dns_server.start_thread()

    cherrypy.quickstart(WebServer(metrics), '/')


if __name__ == '__main__':
    app.run(main)
