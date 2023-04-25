FROM python:3.8

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

RUN git clone https://github.com/gerrowadat/nomad-dns-exporter /nomad-dns-exporter
RUN pip3 install -r /nomad-dns-exporter/requirements.txt

WORKDIR /nomad-dns-exporter

# The nomad server to talk to (localhost if you're just runing this on servers)
ENV NOMAD_SERVER "localhost"
# Address to serve DNS on.
ENV DNS_HOSTNAME "localhost"
# Address to serve HTTP on
ENV HTTP_HOSTNAME "localhost"
# Port to answerr DNS queries on (don't use 53, probably).
ENV DNS_PORT "5333"
# Port to answer HTTP on
ENV HTTP_PORT "5334"
# That thing.
ENV DNS_TTL "3600"
# The trailing domain name to answer queries for, i.e. myservice.service.nomad
ENV NOMAD_DOMAIN ".service.nomad"


ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["python3"]
