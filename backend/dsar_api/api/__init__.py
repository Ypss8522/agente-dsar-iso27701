"""Registro de blueprints. Para agregar un módulo nuevo: crear el archivo y añadirlo aquí."""
from flask import Flask

from . import audit, health, requests, subjects, vector_search, intake, reports

API_PREFIX = "/api"


def register_blueprints(app: Flask) -> None:
    for module in (health, subjects, requests, audit, vector_search, intake, reports):
        app.register_blueprint(module.bp, url_prefix=API_PREFIX)
