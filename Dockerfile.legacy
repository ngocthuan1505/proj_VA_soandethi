FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium ca-certificates fonts-liberation fonts-dejavu-core fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY . .
RUN mkdir -p /var/lib/mach /app/.data/ocr-cache && chown -R node:node /var/lib/mach /app/.data
ENV NODE_ENV=production PORT=4173 HOST=0.0.0.0 APP_DATA_DIR=/var/lib/mach BROWSER_PATH=/usr/bin/chromium
USER node
EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD node -e "fetch('http://127.0.0.1:'+process.env.PORT+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.mjs"]
