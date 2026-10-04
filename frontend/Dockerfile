FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG NUXT_API_INTERNAL_URL=http://api:8080
ENV NUXT_API_INTERNAL_URL=${NUXT_API_INTERNAL_URL}
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NITRO_HOST=0.0.0.0 \
    NITRO_PORT=3000 \
    NUXT_PUBLIC_RECOGNITION_MODE=api \
    NUXT_PUBLIC_API_BASE="" \
    NUXT_API_INTERNAL_URL=http://api:8080
COPY --from=build /app/.output ./.output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
