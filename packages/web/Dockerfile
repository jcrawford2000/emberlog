FROM node-20-alpine as builder

WORKDIR /app

COPY package.json ./

ARG VITE_API_BASE_URL=http://emberlog-api.pi-rack.com
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
