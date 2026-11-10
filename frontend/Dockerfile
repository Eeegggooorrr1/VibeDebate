FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_KEYCLOAK_URL=http://localhost:8180
ARG VITE_KEYCLOAK_REALM=vibedebate
ARG VITE_KEYCLOAK_CLIENT_ID=vibedebate-web
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID
RUN npm run build

FROM build AS frontend-test
CMD ["npm", "test"]

FROM nginx:1.28-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
