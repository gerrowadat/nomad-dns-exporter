job "nomad-dns-exporter" {
  datacenters = ["home"]
  group "nomad-dns-exporter_servers" {
    task "nomad-dns-exporter_server" {
      service {
        name = "nomad-dns-exporter"
	      port = "nomad-dns-exporter"
      }
      driver = "docker" 
      config {
        image = "my-local-registry:5000/nomad-dns-exporter:latest"
        labels {
          group = "nomad-dns-exporter"
        }
        ports = ["nomad-dns-exporter"]
      }
      env {
        NOMAD_SERVER = "localhost"
        DNS_PORT = "5333"
      }
    }
    network {
      mode = "host"
      port "nomad-dns-exporter" {
        static = "5333"
      }
    }
  }
}
