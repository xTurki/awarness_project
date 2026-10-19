FROM nginx:1.27-alpine

# Rendered to /etc/nginx/conf.d/default.conf at container start.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Must be executable and run before the envsubst step (20-...), hence "15-".
COPY --chmod=0755 upload-limit.envsh /docker-entrypoint.d/15-upload-limit.envsh

# Shown while the backend is restarting.
COPY maintenance.html /usr/share/nginx/html/maintenance.html
