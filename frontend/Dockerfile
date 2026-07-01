# db8r-eval-utility frontend (React + Vite SPA) — production image.
# Build context: db8r-eval-utility/frontend/   (the Vite project: package.json, src/, etc.)
# Multi-stage: node build -> static assets served by nginx with SPA fallback.
#
# NOTE: the Vite project is scaffolded under frontend/ as part of the SPA build
# (see FRONTEND_BRIEF.md). This Dockerfile expects `npm run build` -> dist/.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
