# Base image
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Install dependencies first (using cache)
COPY package.json package-lock.json ./
RUN npm install

# Copy all source files
COPY . .

# Expose development port
EXPOSE 5173

# Start the development server with hot reload
CMD ["npm", "start"]
