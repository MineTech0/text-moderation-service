# Prometheus with embedded configuration
FROM prom/prometheus:v2.47.0

# Copy configuration files into the image
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY alerts.yml /etc/prometheus/alerts.yml

