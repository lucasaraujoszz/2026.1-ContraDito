FROM node:20-alpine

WORKDIR /app

# Garante que o servidor de dev do Next.js exponha a porta para fora do contêiner
ENV HOSTNAME="0.0.0.0"

# Otimização de cache no node_modules
COPY package.json package-lock.json* ./

RUN npm install && npm cache clean --force

COPY . .

EXPOSE 3000

# Ambiente local (hot-reload via bind mount do docker-compose)
CMD ["npm", "run", "dev"]