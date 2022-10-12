import nomad
import socket
import dnslib
import argparse


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nomad_server', dest='nomad_server',
                   type=str, default='hedwig')
    p.add_argument('--dns_port', dest='dns_port', type=int,
                   default=5333)
    p.add_argument('--nomad_domain', dest='nomad_domain', type=str,
                   default='.service.nomad.')
    args = p.parse_args()

    udp_server = socket.socket(family=socket.AF_INET,
                               type=socket.SOCK_DGRAM)
    udp_server.bind(("127.0.0.1", args.dns_port))

    while True:
        (msg, addr) = udp_server.recvfrom(1024)
        req = dnslib.DNSRecord.parse(msg.strip())
        rep = dnslib.DNSRecord(dnslib.DNSHeader(
                               id=req.header.id,
                               qr=1,
                               aa=1,
                               ra=1),
                               q=req.q)
        print('QN: %s' % (str(req.q.qname)))
        print(req)
        ips = resolve(args.nomad_server, str(req.q.qname)[:-1])
        for ip in ips:
            rep.add_answer(
                           dnslib.RR(str(req.q.qname), rdata=dnslib.A(ip)))
        udp_server.sendto(rep.pack(), addr)


def resolve(nomad_server, query):
    n = nomad.Nomad(host=nomad_server)
    all_job_names = [j['Name'] for j in n.jobs.get_jobs()]
    all_allocs = n.allocations.get_allocations()

    if query not in all_job_names:
        print('NXDOMAIN %s' % (query))
        return 1

    job_allocs = [a for a in all_allocs
                  if a['ClientStatus'] == 'running' and
                  a['JobID'] == query]
    ips = []
    for alloc in job_allocs:
        node = n.node.get_node(alloc['NodeID'])
        ips.append(node['Attributes']['unique.network.ip-address'])
    return ips


if __name__ == '__main__':
    main()
