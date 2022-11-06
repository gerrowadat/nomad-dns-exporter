docker buildx build --push --platform linux/amd64,linux/arm64,linux/arm/v7 --tag my-local-docker-registry:5000/nomad-dns-exporter:latest . --push
