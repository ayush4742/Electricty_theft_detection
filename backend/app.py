from __future__ import annotations

import logging
import sys

from flask import Flask
from flask_cors import CORS

from config import DEBUG, HOST, PORT, configure_logging
from database import init_db
from routes import register_routes
from transformer_routes import register_transformer_routes
from agent_routes import register_agent_routes


configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
CORS(app)
register_routes(app)
register_transformer_routes(app)
register_agent_routes(app)
logger.info("Flask startup: sys.executable=%s", sys.executable)


if __name__ == "__main__":
    init_db()
    logger.info("Starting Electricity Theft Detection API on %s:%s", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=DEBUG)
else:
    init_db()
