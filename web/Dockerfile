# Next.js frontend image (docker-compose `web` profile).
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 3000
# In compose, the Next server proxies /api to the api service (API_PROXY_TARGET).
CMD ["npm", "run", "start"]
