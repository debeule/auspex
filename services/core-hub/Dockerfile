FROM eclipse-temurin:25-jdk-alpine AS build
WORKDIR /app
COPY gradlew ./
COPY gradle/ ./gradle/
COPY build.gradle.kts settings.gradle.kts gradle.properties ./
RUN ./gradlew dependencies --no-daemon --quiet
COPY src/ ./src/
RUN ./gradlew bootJar --no-daemon -x test

FROM eclipse-temurin:25-jre-alpine AS runtime
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
