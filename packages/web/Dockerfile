FROM node-20-alpine as builder

WORKDIR /app

COPY package.json ./

ARG VITE_API_BASE_URL=https://emberlog-api.pi-rack.com
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_API_BASE=https://emberlog-api.pi-rack.com
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
