# Keycloak mit Realm "hka" und Login-Theme im Look des Portals.
# Build-Kontext ist das Projektverzeichnis (siehe compose.yml), weil das Theme das Design-Kit (kit/) braucht.
# Kein Bind-Mount, damit es auch ohne Dateifreigabe für Docker Desktop läuft (macOS: ~/Documents).

# Design-Kit bauen und als Theme-Ressourcen anordnen: kit.css mit fonts/ daneben (die CSS verweist relativ darauf).
FROM python:3.14-slim-trixie AS kit
WORKDIR /src
COPY kit ./kit
RUN ["python", "kit/tools/build.py", "--out", "/out/dist"]
RUN mkdir -p /out/resources \
    && cp /out/dist/kit-*.css /out/resources/kit.css \
    && cp -r /out/dist/fonts /out/resources/fonts

FROM quay.io/keycloak/keycloak:26.4
COPY extras/compose/keycloak/theme/hka /opt/keycloak/themes/hka
COPY --from=kit /out/resources /opt/keycloak/themes/hka/login/resources
COPY extras/compose/keycloak/hka-realm.json /opt/keycloak/data/import/hka-realm.json
CMD ["start-dev", "--import-realm"]
