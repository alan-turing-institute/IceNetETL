# Standard library
import logging
import os

# Third party
import azure.functions as func

# Local
from .processor import Processor
from .utils import InputBlobTriggerException


def main(inputBlob: func.InputStream):
    log_prefix = f"[{os.path.splitext(os.path.basename(inputBlob.name))[0]}]"
    logging.info(
        f"{log_prefix} Processing Azure blob: {inputBlob.name} ({inputBlob.length} bytes)"
    )
    processor = Processor(log_prefix, 100000)
    try:
        processor.load(inputBlob)
        processor.update_geometries()
        processor.update_forecasts()
        processor.update_latest_forecast()
    except InputBlobTriggerException as exc:
        logging.error(f"{log_prefix} Failed with message:\n{exc}")
    logging.info(f"{log_prefix} Finished processing Azure blob: {inputBlob.name}")
