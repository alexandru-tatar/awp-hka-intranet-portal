# syntax=docker/dockerfile:1
# HINWEIS: Basisabbild vor der Freigabe per Digest festlegen (node:24-bookworm-slim@sha256:...).
FROM node:24-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM node:24-bookworm-slim
ENV NODE_ENV=production PORT=8080
WORKDIR /app
COPY --from=deps --chown=10001:10001 /app/node_modules ./node_modules
COPY --chown=10001:10001 package.json ./
COPY --chown=10001:10001 src ./src
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["node", "src/healthcheck.js"]
CMD ["node", "src/server.js"]
