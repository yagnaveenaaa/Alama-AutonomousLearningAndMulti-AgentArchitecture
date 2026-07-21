FROM node:22-alpine AS deps
WORKDIR /app
COPY apps/web/package.json ./
RUN npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
RUN addgroup -S alama && adduser -S alama -G alama
COPY --from=builder /app/public ./public
COPY --from=builder --chown=alama:alama /app/.next/standalone ./
COPY --from=builder --chown=alama:alama /app/.next/static ./.next/static
USER alama
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/health || exit 1
CMD ["node", "server.js"]
