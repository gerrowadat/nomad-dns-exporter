import nomad
import asyncio
import asyncio_dgram
import dnslib
import logging
import argparse


ARGS = None


async def udp_server(ip, port):
    logging.debug('Binding to %s UDP port %d' % (ip, port))
    udp_stream = await asyncio_dgram.bind((ip, port))

    while True:
        (data, remote) = await udp_stream.recv()
        rep = resolve_nomad(ARGS.nomad_server, data, remote)
        await udp_stream.send(rep.pack(), remote)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nomad_server', dest='nomad_server',
                   type=str, default='hedwig')
    p.add_argument('--dns_port', dest='dns_port', type=int,
                   default=5333)
    p.add_argument('--dns_ttl', dest='dns_ttl', type=int,
                   default=3600)
    p.add_argument('--nomad_domain', dest='nomad_domain', type=str,
                   default='.service.nomad')
    args = p.parse_args()
    global ARGS
    ARGS = args

    udps = udp_server('0.0.0.0', args.dns_port)
    await asyncio.gather(udps)


def resolve_nomad(nomad_server, dns_req, remote_addr):
    req = dnslib.DNSRecord.parse(dns_req)
    rep = dnslib.DNSRecord(dnslib.DNSHeader(
                           id=req.header.id,
                           qr=1,
                           aa=1,
                           ra=1),
                           q=req.q)

    query = str(req.q.qname)[:-1]

    if not query.endswith(ARGS.nomad_domain):
        logging.warning(
            '[%s] NXDOMAIN (outside %s domain) for %s' % (
                remote_addr[0], ARGS.nomad_domain, query))
        return rep

    n = nomad.Nomad(host=nomad_server)
    all_job_names = [j['Name'] for j in n.jobs.get_jobs()]
    all_allocs = n.allocations.get_allocations()

    # Strip the nomad domain off the query.
    svc_query = query[:(len(query) - len(ARGS.nomad_domain))]

    if svc_query not in all_job_names:
        logging.warning('[%s] NXDOMAIN for %s' % (remote_addr[0], svc_query))
        return rep

    job_allocs = [a for a in all_allocs
                  if a['ClientStatus'] == 'running' and a['JobID'] == svc_query]
    ips = []
    for alloc in job_allocs:
        node = n.node.get_node(alloc['NodeID'])
        ips.append(node['Attributes']['unique.network.ip-address'])
    logging.info('[%s] Resolved %s to %s' % (remote_addr[0], query, ips))
    for ip in ips:
        rep.add_answer(dnslib.RR(str(req.q.qname), rdata=dnslib.A(ip), ttl=ARGS.dns_ttl))
    return rep


asyncio.run(main())
