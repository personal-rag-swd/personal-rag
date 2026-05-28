# Stage 1: Build the React application
FROM node:24-alpine AS build

WORKDIR /app

# Install dependencies first (leverage Docker layer caching)
COPY package*.json ./
RUN npm ci

# Copy configuration and source files
COPY tsconfig*.json ./
COPY vite.config.ts ./
COPY index.html ./
COPY components.json ./
COPY public/ ./public/
COPY src/ ./src/

# Accept build arguments to inject into Vite at compile time
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# Stage 2: Serve the production assets with Nginx
FROM nginx:stable-alpine

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts to Nginx html folder
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
