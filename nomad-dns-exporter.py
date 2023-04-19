import time
import nomad
import dnslib
import threading
from absl import app
from absl import flags
from absl import logging
from dnslib.server import DNSServer
from dnslib.server import DNSLogger

FLAGS = flags.FLAGS

flags.DEFINE_string('nomad_server', 'localhost', 'nomad server to talk to')
flags.DEFINE_integer('dns_port', 5333, 'port to serve DNS queries on')
flags.DEFINE_integer('dns_ttl_secs', 3600, 'DNS TTL')
flags.DEFINE_string('nomad_domain', '.service.nomad',
                    'domain to answer queries within')
flags.DEFINE_integer('nomad_jobinfo_update_interval_secs',
                     30,
                     'number of seconds between nomad jobinfo scrapes')


class JobsInfo(object):
    def __init__(self):
        self._jobs = {}

    def __str__(self):
        return '\n'.join(['[%s]: %s' % (x, self._jobs[x]) for x in self._jobs])

    def get_job(self, jobname):
        return self._jobs.get(jobname) or []

    def add_alloc(self, jobname, nodename):
        if jobname in self._jobs:
            self._jobs[jobname].append(nodename)
        else:
            self._jobs[jobname] = [nodename]


class JobsInfoThread(threading.Thread):
    def __init__(self):

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
                if len(live_allocs) > 0:
                    logging.info('%s has %s allocations' % (
                        jobname, len(live_allocs)))
                for alloc in live_allocs:
                    logging.info('Job %s is %s on %s' % (jobname,
                                                         alloc['ClientStatus'],
                                                         alloc['NodeName']))
                    if alloc['NodeName'] not in self._nodes:
                        logging.warning(
                            'Job %s running on unknown nde %s, skipping' % (
                                jobname, alloc['NodeName']))
                    else:
                        new_ji.add_alloc(jobname,
                                         self._nodes[alloc['NodeName']])
                with self._jl:
                    self._j = new_ji
            time.sleep(FLAGS.nomad_jobinfo_update_interval_secs)


class NomadResolver(object):
    def __init__(self, job_info_thread):
        self._ji = job_info_thread

    def resolve(self, req, handler):
        rep = req.reply()

        query = str(req.q.qname)[:-1]

        if not query.endswith(FLAGS.nomad_domain):
            logging.warning(
                'NXDOMAIN (outside %s domain) for %s' % (
                    FLAGS.nomad_domain, query))
            return rep

        # Strip the nomad domain off the query.
        svc_query = query[:(len(query) - len(FLAGS.nomad_domain))]

        allocs = self._ji.lookup_job(svc_query)

        if len(allocs) == 0:
            return rep

        for alloc_ip in allocs:
            rep.add_answer(dnslib.RR(
                                     str(req.q.qname),
                                     rdata=dnslib.A(alloc_ip),
                                     ttl=FLAGS.dns_ttl_secs))
        return rep


def main(argv):
    jut = JobsInfoThread()
    jut.start()

    resolver = NomadResolver(jut)

    dns_logger = DNSLogger()

    logging.info('Starting DNS server on port %d' % (FLAGS.dns_port))
    dns_server = DNSServer(resolver,
                           port=FLAGS.dns_port,
                           address='localhost',
                           logger=dns_logger)
    dns_server.start_thread()

    jut.join()


if __name__ == '__main__':
    app.run(main)
