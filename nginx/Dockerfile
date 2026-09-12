FROM nginx:1.27-alpine

# Rendered to /etc/nginx/conf.d/default.conf at container start.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Sourced before that rendering, so the derived upload limit is in scope.
# The mode is set here rather than inherited from the build context: the
# entrypoint silently ignores an .envsh that is not executable, and a host
# filesystem that does not carry the bit would leave client_max_body_size
# empty and nginx refusing to start.
# The entrypoint sources .envsh files and runs them in name order, and the
# envsubst step is numbered 20, so this must sort before it.
COPY --chmod=0755 upload-limit.envsh /docker-entrypoint.d/15-upload-limit.envsh
