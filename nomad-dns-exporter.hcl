job "nomad-dns-exporter" {
  type = "system"
  datacenters = ["home"]
  group "nomad-dns-exporter_servers" {
    task "nomad-dns-exporter_server" {
      service {
        name = "nomad-dns-exporter"
	      port = "nomad-dns-exporter-http"
      }
      driver = "docker" 
      config {
        image = "my-local-registry:5000/nomad-dns-exporter:latest"
        labels {
          group = "nomad-dns-exporter"
        }
        ports = ["nomad-dns-exporter-dns", "nomad-dns-exporter-http"]
      }
      env {
        NOMAD_SERVER = "${attr.unique.hostname}"
        DNS_PORT = "5333"
        HTTP_PORT = "5334"
      }
    }
    network {
      mode = "host"
      port "nomad-dns-exporter-dns" {
        static = "5333"
      }
      port "nomad-dns-exporter-http" {
        static = "5334"
      }
    }
  }
}
