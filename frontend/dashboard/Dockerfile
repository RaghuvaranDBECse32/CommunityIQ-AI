# ---- Frontend Dockerfile (multistage) ----
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Install only package.json and lockfile for caching
COPY package.json .
# If a lockfile exists, copy it (npm uses package-lock.json)
COPY package-lock.json* .
RUN npm ci --silent

# Copy source code and build
COPY . .
RUN npm run build

# ---- Production stage ----
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
# Expose port 3000 (or 80) – nginx default 80
EXPOSE 80
# Use default nginx config
CMD ["nginx", "-g", "daemon off;" ]
