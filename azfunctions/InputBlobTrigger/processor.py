# Standard library
import io
import logging
import math
import os
import time

# Third party
import azure.functions as func
import pandas as pd
import psycopg2
from shapely.geometry import Polygon
import xarray

# Local
from .utils import batches, human_readable, mean_step_size


class Processor:
    def __init__(self, batch_size):
        """Constructor."""
        self.batch_size = batch_size
        self.cnxn_ = None
        self.cursor_ = None
        self.tables = {
            "geom": "cell",
            "predictions": "prediction",
            "latest": "prediction_latest",
        }
        self.xr = None

    def __del__(self):
        """Destructor."""
        if self.cnxn_:
            self.cnxn_.close()

    @property
    def cnxn(self):
        """Connect to the database or return an existing connection."""
        if not self.cnxn_:
            try:
                db_host = os.getenv("PSQL_HOST")
                db_name = os.getenv("PSQL_DB")
                db_user = os.getenv("PSQL_USER")
                db_pwd = os.getenv("PSQL_PWD")
                self.cnxn_ = psycopg2.connect(
                    dbname=db_name,
                    port="5432",
                    user=f"{db_user}@{db_host}",
                    password=db_pwd,
                    host=db_host,
                )
                logging.info(f"Connected to database {db_name} on {db_host}.")
            except psycopg2.OperationalError:
                logging.error(f"Failed to connect to database {db_name} on {db_host}!")
                raise
        return self.cnxn_

    @property
    def cursor(self):
        """Construct a database cursor or return an existing cursor."""
        if not self.cursor_:
            self.cursor_ = self.cnxn.cursor()
        return self.cursor_

    def load(self, inputBlob: func.InputStream) -> None:
        """Load data from a file into an xarray."""
        logging.info(f"Attempting to load {inputBlob.name}...")
        try:
            self.xr = xarray.open_dataset(io.BytesIO(inputBlob.read()))
            logging.info(
                f"Loaded NetCDF data into array with dimensions: {self.xr.dims}."
            )
        except ValueError as exc:
            logging.error(f"Could not load NetCDF data from {inputBlob.name}!")
            logging.error(exc)

    def update_geometries(self) -> None:
        """Update the table of geometries, creating it if necessary."""
        # Ensure that geometry table exists
        logging.info(
            f"Ensuring that geometries table '{self.tables['geom']}' exists..."
        )
        self.cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.tables['geom']} (
                cell_id SERIAL PRIMARY KEY,
                centroid_x int4,
                centroid_y int4,
                geom_6931 geometry,
                geom_4326 geometry,
                UNIQUE (centroid_x, centroid_y)
            );
            """
        )
        self.cnxn.commit()
        logging.info(f"Ensured that geometries table '{self.tables['geom']}' exists.")

        # Calculate the size of the grid cells
        logging.info(f"Identifying cell geometries from input data...")
        centroids_x_km, centroids_y_km = self.xr.xc.values, self.xr.yc.values
        x_delta_m = 1000 * int(0.5 * mean_step_size(centroids_x_km))
        y_delta_m = 1000 * int(0.5 * mean_step_size(centroids_y_km))

        # Construct list of geometry records
        records = []
        for centroid_x_km in centroids_x_km:
            centroid_x_m = int(1000 * centroid_x_km)
            for centroid_y_km in centroids_y_km:
                centroid_y_m = int(1000 * centroid_y_km)
                x_min_m, x_max_m = centroid_x_m - x_delta_m, centroid_x_m + x_delta_m
                y_min_m, y_max_m = centroid_y_m - y_delta_m, centroid_y_m + y_delta_m
                geometry = Polygon(
                    [
                        [x_min_m, y_max_m],
                        [x_max_m, y_max_m],
                        [x_max_m, y_min_m],
                        [x_min_m, y_min_m],
                        [x_min_m, y_max_m],
                    ]
                )
                records.append((centroid_x_m, centroid_y_m, geometry.wkt, geometry.wkt))
        logging.info(f"Identified {len(records)} cell geometries.")

        # Insert geometries into the database
        logging.info(
            f"Ensuring that '{self.tables['geom']}' contains all {len(records)} geometries..."
        )
        n_batches = int(math.ceil(len(records) / self.batch_size))
        start_time = time.monotonic()
        for idx, record_batch in enumerate(batches(records, self.batch_size), start=1):
            logging.info(
                f"Batch {idx}/{n_batches}. Preparing to insert/update {len(record_batch)} geometries..."
            )
            for record in record_batch:
                self.cursor.execute(
                    f"""
                    INSERT INTO {self.tables['geom']} (cell_id, centroid_x, centroid_y, geom_6931, geom_4326)
                    VALUES(DEFAULT, %s, %s, ST_GeomFromText(%s, 6931), ST_Transform(ST_GeomFromText(%s, 6931), 4326))
                    ON CONFLICT DO NOTHING;
                    """,
                    record,
                )
            self.cnxn.commit()
            remaining_time = (time.monotonic() - start_time) * (n_batches / idx - 1)
            logging.info(
                f"Batch {idx}/{n_batches}. Inserted/updated {len(record_batch)} geometries. Time remaining {human_readable(remaining_time)}."
            )
        logging.info(f"Ensured that '{self.tables['geom']}' contains all geometries.")

    def update_predictions(self) -> None:
        """Update the table of predictions, creating it if necessary"""
        # Ensure that prediction table exists
        logging.info(
            f"Ensuring that predictions table '{self.tables['predictions']}' exists..."
        )
        self.cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.tables['predictions']} (
                prediction_id SERIAL PRIMARY KEY,
                date date,
                leadtime int4,
                cell_id int4,
                mean float4,
                stddev float4,
                UNIQUE (date, leadtime, cell_id),
                CONSTRAINT fk_cell_id FOREIGN KEY(cell_id) REFERENCES {self.tables['geom']}(cell_id)
            );
            """
        )
        self.cnxn.commit()
        logging.info(
            f"Ensured that predictions table '{self.tables['predictions']}' exists."
        )

        # Construct a list of values
        logging.info(f"Loading predictions from input data...")
        df_predictions = (
            self.xr.where(self.xr["mean"] > 0).to_dataframe().dropna().reset_index()
        )
        df_predictions["xc_m"] = pd.to_numeric(
            1000 * df_predictions["xc"], downcast="integer"
        )
        df_predictions["yc_m"] = pd.to_numeric(
            1000 * df_predictions["yc"], downcast="integer"
        )
        logging.info(f"Loaded {df_predictions.shape[0]} predictions from input data.")

        # Get cell IDs by loading existing cells and merging onto list of predictions
        logging.info(f"Identifying cell IDs for all predictions...")
        df_cells = pd.io.sql.read_sql_query(
            f"SELECT cell_id, centroid_x, centroid_y FROM {self.tables['geom']};",
            self.cnxn,
        )
        df_merged = pd.merge(
            df_predictions,
            df_cells,
            how="left",
            left_on=["xc_m", "yc_m"],
            right_on=["centroid_x", "centroid_y"],
        )
        logging.info(f"Identified cell IDs for {df_merged.shape[0]} predictions.")

        # Insert predictions into the database
        logging.info(
            f"Ensuring that table '{self.tables['predictions']}' contains all {df_merged.shape[0]} predictions..."
        )
        n_batches = int(math.ceil(df_merged.shape[0] / self.batch_size))
        start_time = time.monotonic()
        for idx, record_batch in enumerate(
            batches(df_merged, self.batch_size), start=1
        ):
            logging.info(
                f"Batch {idx}/{n_batches}. Preparing to insert/update {len(record_batch)} predictions..."
            )
            for record in record_batch:
                self.cursor.execute(
                    f"""
                    INSERT INTO {self.tables['predictions']} (prediction_id, date, leadtime, cell_id, mean, stddev)
                    VALUES(
                        DEFAULT,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT DO NOTHING;
                    """,
                    [
                        record.time.date(),
                        record.leadtime,
                        record.cell_id,
                        record.mean,
                        record.stddev,
                    ],
                )
            self.cnxn.commit()
            remaining_time = (time.monotonic() - start_time) * (n_batches / idx - 1)
            logging.info(
                f"Batch {idx}/{n_batches}. Inserted/updated {len(record_batch)} predictions. Time remaining {human_readable(remaining_time)}."
            )
        logging.info(
            f"Ensured that table '{self.tables['predictions']}' contains all {df_merged.shape[0]} predictions."
        )

    def update_latest_prediction(self) -> None:
        """Update the 'latest prediction' view, creating it if necessary"""
        # Ensure that view table exists
        logging.info(f"Updating materialised view '{self.tables['latest']}'...")
        self.cursor.execute(
            f"""
            DROP MATERIALIZED VIEW {self.tables['latest']};
            CREATE MATERIALIZED VIEW {self.tables['latest']} AS
                SELECT
                    row_number() OVER (PARTITION BY true) as prediction_latest_id,
                    {self.tables['predictions']}.date,
                    {self.tables['predictions']}.leadtime,
                    {self.tables['predictions']}.mean,
                    {self.tables['predictions']}.stddev,
                    {self.tables['geom']}.cell_id,
                    {self.tables['geom']}.centroid_x,
                    {self.tables['geom']}.centroid_y,
                    {self.tables['geom']}.geom_6931,
                    {self.tables['geom']}.geom_4326
                FROM {self.tables['predictions']}
                FULL OUTER JOIN cell ON {self.tables['predictions']}.cell_id = {self.tables['geom']}.cell_id
                WHERE date = (SELECT max(date) FROM {self.tables['predictions']})
                GROUP BY {self.tables['geom']}.cell_id, date, leadtime, centroid_x, centroid_y, mean, stddev, geom_6931, geom_4326;
            """
        )
        self.cnxn.commit()
        logging.info(f"Updated materialised view '{self.tables['latest']}'.")
