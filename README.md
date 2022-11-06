[![Flake8 linter Actions Status](https://github.com/gerrowadat/nomad-dns-exporter/workflows/Flake8%20linter/badge.svg)](https://github.com/gerrowadat/nomad-dns-exporter/actions)
# nomad-dns-exporter
Simple and Dirty Service DNS export for nomad services.

My only real use case for this is to eliminate my need for consul for service DNS (which is all I really use it for).

Instructions for use:
---------------------

Build the docker container(s) with buildandpush.sh to your own registry (or use [gerrowadat/nomad-dns-exporter](https://hub.docker.com/r/gerrowadat/nomad-dns-exporter) if you insist).

Modify and use nomad-dns-exporter.hcl to run your nomad job. I'm lazy and run it as a system job, and point bind at a subset of my nomad clients. You can do something smarter ifyalike.

In particular, make sure NOMAD_HOST is pointed at an actual address for a nomad client in your cluster. I get away with using the current client's hostname because I run a client and a server everywhere on my small homelab, YMMV.

In bind, add this to your named.conf.local:

```
zone "nomad" {
    type forward;
    forward only;
    forwarders { ip.of.no.mad1 port 5333;
                 ip.of.no.mad2 port 5333;
                 ip.of.no.mad3 port 5333;};
};
```

At this point, your named should be able to resolve *jobname*.service.nomad direcly, and you cn use this to discover where jobs are in your cluster. Ta-da!

Check the issues for things I still think are missing and may or may not get to. Patches and offers to do this properly welcome.
