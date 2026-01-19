# Configurable base images
ARG NODE_IMAGE=node:20-alpine
ARG NGINX_IMAGE=nginx:alpine

# Build stage
FROM ${NODE_IMAGE} AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM ${NGINX_IMAGE}

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
