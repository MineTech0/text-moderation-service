# Grafana with embedded configuration and dashboards
FROM grafana/grafana:10.1.0

# Switch to root to copy files
USER root

# Copy provisioning configuration
COPY provisioning /etc/grafana/provisioning

# Copy dashboards to /etc/grafana/dashboards (NOT /var/lib/grafana which is a volume!)
COPY dashboards /etc/grafana/dashboards

# Ensure correct permissions
RUN chown -R grafana:root /etc/grafana/provisioning /etc/grafana/dashboards && \
    chmod -R 755 /etc/grafana/provisioning /etc/grafana/dashboards

# Switch back to grafana user
USER grafana
