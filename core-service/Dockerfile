# Use official Node.js LTS image
FROM node:20-slim

# Set working directory
WORKDIR /usr/src/app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install --production


# Copy the rest of the application code
COPY . .

# Build TypeScript (requires devDependencies)
# We temporarily install dev deps ONLY to build, then remove them
RUN npm install --include=dev \
    && npm run build \
    && npm prune --omit=dev

# NOTE: .env file should NOT be copied into the image for security reasons
# Instead, provide environment variables at runtime via:
# - Docker: docker run --env-file .env
# - Docker Compose: env_file directive
# - Kubernetes: environment variables or secrets

EXPOSE 7090

# Start the service directly
#CMD ["npx", "ts-node", "src/index.ts"]

# Start the compiled JS, NOT ts-node
CMD ["node", "dist/index.js"]
