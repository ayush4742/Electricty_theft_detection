from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from config import DEBUG, HOST, PORT, configure_logging
from database import init_db
from routes import register_routes


configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
CORS(app)
register_routes(app)


if __name__ == "__main__":
    init_db()
    logger.info("Starting Electricity Theft Detection API")
    app.run(host=HOST, port=PORT, debug=DEBUG)
else:
    init_db()
