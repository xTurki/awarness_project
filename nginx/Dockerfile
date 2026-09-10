FROM nginx:1.27-alpine

# Rendered to /etc/nginx/conf.d/default.conf at container start.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Sourced before that rendering, so the derived upload limit is in scope.
# The entrypoint sources .envsh files and runs them in name order, and the
# envsubst step is numbered 20, so this must sort before it.
COPY upload-limit.envsh /docker-entrypoint.d/15-upload-limit.envsh
