# Grafana with embedded configuration and dashboards
FROM grafana/grafana:10.1.0

# Copy provisioning configuration
COPY provisioning /etc/grafana/provisioning

# Copy dashboards
COPY dashboards /var/lib/grafana/dashboards

