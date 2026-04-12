import logging

logging.basicConfig(
    filename="logs/agent.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def log_event(msg):
    logging.info(msg)