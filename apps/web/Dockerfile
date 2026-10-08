# Next.js image for running the web app outside Vercel (Vercel builds from source).
# Build from the repository root:
#   docker build -f apps/web/Dockerfile --build-arg API_ORIGIN=https://api.example.com -t weather-web .
# API_ORIGIN is needed at build time: Next.js bakes rewrite destinations into the build.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages packages
RUN npm ci
COPY apps/web apps/web
ARG API_ORIGIN=http://api:8000
ENV API_ORIGIN=$API_ORIGIN NEXT_OUTPUT=standalone NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w @weather/web

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
