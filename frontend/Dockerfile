# syntax=docker/dockerfile:1
FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Vite embeds these settings at build time. Never pass secrets as VITE_*.
ARG VITE_API_MODE=mock
ARG VITE_DEMO_SCENARIO=success
ARG VITE_CONTRACT_ACK=
ENV VITE_API_MODE=${VITE_API_MODE} \
    VITE_DEMO_SCENARIO=${VITE_DEMO_SCENARIO} \
    VITE_CONTRACT_ACK=${VITE_CONTRACT_ACK}

COPY . .
RUN npm run build

FROM nginx:stable-alpine AS runtime
ENV BACKEND_ORIGIN=http://127.0.0.1:8081
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
