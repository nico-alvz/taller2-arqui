FROM node:18-slim
WORKDIR /app

# Copiar dependencias
COPY package.json .
RUN npm install --production

# Copiar resto del código
COPY . .

# Exponer puerto gRPC
EXPOSE 50053

CMD ["node", "index.js"]