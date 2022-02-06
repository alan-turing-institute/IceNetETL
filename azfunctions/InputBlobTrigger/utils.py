# Third party
import pandas as pd


class InputBlobTriggerException(Exception):
    pass


def batches(iterable_input, size, as_dataframe=False):
    """Yield successive chunks of up to 'size' elements from iterable_input."""

    def maybe_df(output_, as_dataframe):
        """Convert output to a DataFrame or leave it as-is depending on argument"""
        if as_dataframe:
            return pd.DataFrame(output_)
        return output_

    if isinstance(iterable_input, pd.DataFrame):
        output = []
        for tuple_ in iterable_input.itertuples(False):
            output.append(tuple_)
            if len(output) >= size:
                yield maybe_df(output, as_dataframe)
                output = []
        if output:
            yield maybe_df(output, as_dataframe)
            output = []
    else:
        for idx in range(0, len(iterable_input), size):
            yield maybe_df(iterable_input[idx : idx + size], as_dataframe)


def human_readable(seconds):
    """Human readable string from seconds"""
    days, seconds = divmod(int(seconds), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days:d}d{hours:d}h{minutes:d}m{seconds:d}s"
    if hours > 0:
        return f"{hours:d}h{minutes:d}m{seconds:d}s"
    if minutes > 0:
        return f"{minutes:d}m{seconds:d}s"
    return f"{seconds:d}s"


def get_time_estimates(time_start, time_start_batch, time_now, f_complete):
    """After a batch, get the batch time; remaining time and total time"""
    time_elapsed_batch = time_now - time_start_batch
    time_elapsed_total = time_now - time_start
    time_total = time_elapsed_total / f_complete
    time_remaining = time_total - time_elapsed_total
    return (time_elapsed_batch, time_elapsed_total, time_remaining, time_total)


def mean_step_size(input_):
    return (max(input_) - min(input_)) / (len(input_) - 1)
