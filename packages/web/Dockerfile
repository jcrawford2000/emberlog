FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=https://emberlog-api.pi-rack.com
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_API_BASE=https://emberlog-api.pi-rack.com
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

# --- Runtime ---
FROM nginx:alpine

LABEL org.opencontainers.image.source https://github.com/jcrawford2000/emberlog

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
